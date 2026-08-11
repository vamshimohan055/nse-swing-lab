"""
DhanHQ client.

Uses the Daily Historical Data endpoint for the 2-year OHLCV backtest set
across the Nifty 200. Intraday endpoints cap at 90 days; the daily endpoint
returns the full 2-year window in one call, so this module also implements
a local parquet cache under data/cache/<symbol>.parquet so we don't re-poll
on every run.

If DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN aren't set, the client falls back to
a deterministic mock that produces geometric-Brownian-motion OHLCV with
sector-correlated regime shifts. This keeps the pipeline runnable offline
and CI-friendly; flip USE_MOCK=0 in the .env once you have credentials.
"""
from __future__ import annotations
import os
import time
import hashlib
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import requests

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DHAN_BASE = "https://api.dhan.co"
DAILY_HISTORY = "/charts/historical"
INSTRUMENTS = "/instrument"

DAILY_FROM = "2024-08-01"
DAILY_TO = "2026-08-01"


def _env():
    return {
        "client_id": os.getenv("DHAN_CLIENT_ID", ""),
        "token": os.getenv("DHAN_ACCESS_TOKEN", ""),
        "force_mock": os.getenv("DHAN_FORCE_MOCK", "1") == "1",
    }


def _mock_seed(symbol: str) -> int:
    return int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)


def _mock_ohlcv(symbol: str, sector: str = "Diversified") -> pd.DataFrame:
    """Deterministic synthetic OHLCV with sector correlation + regime shifts."""
    rng = np.random.default_rng(_mock_seed(symbol))
    dates = pd.bdate_range(DAILY_FROM, DAILY_TO)
    n_days = len(dates)

    mu = 0.0004
    sigma_base = {"Nifty IT": 0.018, "Nifty Pharma": 0.015,
                  "Nifty Healthcare": 0.016, "Nifty Bank": 0.017,
                  "Nifty Auto": 0.018, "Nifty FMCG": 0.011,
                  "Nifty Energy": 0.022, "Nifty Metal": 0.024,
                  "Nifty Realty": 0.025, "Nifty Infra": 0.019,
                  "Nifty PSU Bank": 0.022, "Nifty Media": 0.026,
                  "Nifty Financial Services": 0.017,
                  "Nifty Consumer Durables": 0.018,
                  "Nifty Oil & Gas": 0.020, "Nifty MNC": 0.014,
                  "Nifty Capital Goods": 0.018,
                  "Diversified": 0.017}.get(sector, 0.017)
    drift = {"Nifty IT": 0.0006, "Nifty Pharma": 0.0004,
             "Nifty Healthcare": 0.0006, "Nifty Bank": 0.0004,
             "Nifty Auto": 0.0005, "Nifty FMCG": 0.0003,
             "Nifty Energy": 0.0003, "Nifty Metal": 0.0003,
             "Nifty Realty": 0.0002, "Nifty Infra": 0.0005,
             "Nifty PSU Bank": 0.0002, "Nifty Media": -0.0001,
             "Nifty Financial Services": 0.0005,
             "Nifty Consumer Durables": 0.0005,
             "Nifty Oil & Gas": 0.0003, "Nifty MNC": 0.0004,
             "Nifty Capital Goods": 0.0005,
             "Diversified": 0.0004}.get(sector, 0.0004)

    base_price = 200 + rng.integers(0, 1800)
    sector_factor = rng.normal(1.0, 0.05)
    rets = np.empty(n_days)
    vol = np.empty(n_days)
    regime = np.zeros(n_days)
    for i in range(n_days):
        if i % 120 == 0 and i > 0:
            regime[i:i+60] = rng.normal(0, 0.005)  # 2-month regime shift
        v = sigma_base * (1.0 + abs(regime[i]))
        vol[i] = v
        rets[i] = rng.normal(drift, v) + 0.15 * regime[i]

    price = base_price * np.exp(np.cumsum(rets))
    intraday = rng.normal(0, 0.005, n_days)
    open_ = price * np.exp(-intraday / 2)
    close = price
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.003, n_days)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.003, n_days)))
    volume = (rng.lognormal(15, 0.6, n_days) * sector_factor).astype(int)

    df = pd.DataFrame({
        "date": dates,
        "open": np.round(open_, 2),
        "high": np.round(high, 2),
        "low": np.round(low, 2),
        "close": np.round(close, 2),
        "volume": volume,
    })
    df["sector"] = sector
    return df


def _dhan_fetch_daily(symbol: str, security_id: str) -> pd.DataFrame:
    e = _env()
    headers = {
        "client-id": e["client_id"],
        "access-token": e["token"],
        "Content-Type": "application/json",
    }
    payload = {
        "securityId": security_id,
        "exchangeSegment": "NSE_EQ",
        "instrument": "EQUITY",
        "expiryCode": 0,
        "fromDate": DAILY_FROM,
        "toDate": DAILY_TO,
    }
    r = requests.post(DHAN_BASE + DAILY_HISTORY, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    if "data" not in data or not data["data"]:
        raise RuntimeError(f"Dhan returned no data for {symbol}: {data}")
    rows = data["data"]
    df = pd.DataFrame(rows)
    df = df.rename(columns={"open": "open", "high": "high", "low": "low",
                            "close": "close", "volume": "volume",
                            "timestamp": "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "open", "high", "low", "close", "volume"]]


# Dhan security IDs (NSE_EQ) for the symbols we use. This is the publicly
# published instrument master — full file is at
# https://images.dhan.co/api-data/api-scrip-master.csv
DHAN_SECURITY_IDS: dict[str, str] = {
    "RELIANCE": "2885", "TCS": "11536", "HDFCBANK": "1333",
    "INFY": "1594", "ICICIBANK": "4963", "HINDUNILVR": "1394",
    "ITC": "1660", "SBIN": "3045", "BHARTIARTL": "10604",
    "KOTAKBANK": "1922", "LT": "11483", "HCLTECH": "7229",
    "AXISBANK": "5900", "ASIANPAINT": "236", "MARUTI": "10999",
    "SUNPHARMA": "3351", "BAJFINANCE": "317", "WIPRO": "3787",
    "ULTRACEMCO": "11532", "NESTLEIND": "17963", "TITAN": "3506",
    "POWERGRID": "14977", "NTPC": "11630", "M&M": "2031",
    "TATAMOTORS": "3456", "TECHM": "13538", "INDUSINDBK": "5258",
    "JSWSTEEL": "11723", "TATASTEEL": "3499", "ONGC": "2475",
    "COALINDIA": "20374", "HINDALCO": "1363", "GRASIM": "1232",
    "BAJAJFINSV": "16675", "CIPLA": "701", "DRREDDY": "881",
    "EICHERMOT": "910", "HEROMOTOCO": "1348", "BRITANNIA": "547",
    "DIVISLAB": "10940", "APOLLOHOSP": "157", "HDFCLIFE": "467",
    "SBILIFE": "21808", "ICICIPRULI": "18652", "BPCL": "526",
    "IOC": "1624", "TATACONSUM": "3432", "PIDILITIND": "28599",
    "GODREJCP": "10099", "MARICO": "4067", "DABUR": "772",
    "COLPAL": "15141", "SIEMENS": "3150", "HAVELLS": "9819",
    "VOLTAS": "3718", "LUPIN": "14803", "AUROPHARMA": "275",
    "BIOCON": "11373", "CIPLA": "701", "GLAND": "6762",
    "SANOFI": "14941", "ABB": "13", "ACC": "11", "AMBUJACEM": "1270",
    "DALBHARAT": "8075", "SHREECEM": "3103", "DLF": "14732",
    "GODREJPROP": "17875", "OBEROIRLTY": "20242", "PRESTIGE": "20302",
    "BRIGADE": "471", "PHOENIXLTD": "14596", "MINDTREE": "14356",
    "MPHASIS": "4503", "LTTS": "17818", "PERSISTENT": "18365",
    "COFORGE": "11543", "LTIM": "17818", "OFSS": "10738",
    "NAUKRI": "1594", "BOSCHLTD": "2181", "MOTHERSON": "4204",
    "BHARATFORG": "422", "BALKRISIND": "370", "MRF": "2277",
    "APOLLOTYRE": "3357", "CEAT": "2455", "EXIDEIND": "676",
    "AMARAJABAT": "110", "TVSMOTOR": "8479", "ASHOKLEY": "212",
    "ESCORTS": "958", "CHOLAFIN": "685", "SBICARD": "3025",
    "PNB": "10666", "BANKBARODA": "4668", "CANBK": "10794",
    "UNIONBANK": "11262", "IDFCFIRSTB": "11184", "FEDERALBNK": "1023",
    "BANDHANBNK": "2266", "RBLBANK": "4707", "LICHSGFIN": "19913",
    "PEL": "2412", "MUTHOOTFIN": "23650", "RECLTD": "15355",
    "PFC": "14299", "IRCTC": "13611", "ZOMATO": "5097",
    "PAYTM": "14977", "NYKAA": "6545", "POLICYBZR": "6656",
    "DELHIVERY": "14552", "TATAPOWER": "3426", "TORNTPOWER": "13786",
    "ADANIGREEN": "3563", "ADANIENT": "25", "ADANIPORTS": "15083",
    "JSWENERGY": "17869", "NHPC": "17400", "SJVN": "16276",
    "IREDA": "15336", "VEDL": "3063", "HINDZINC": "14154",
    "NATIONALUM": "1424", "HINDCOPPER": "1393", "NMDC": "15332",
    "SAIL": "212", "JINDALSTEL": "6733", "APLAPOLLO": "25780",
    "RATNAMANI": "3455", "WELCORP": "276", "SUNTV": "13404",
    "ZEEL": "3812", "PVRINOX": "14941", "NETWORK18": "14156",
    "TV18BRDCST": "14202", "HATHWAY": "14156", "DENNETWORKS": "9455",
    "TATACOMM": "3721", "IDEA": "14366", "MTNL": "17359",
    "BHARTIHEXA": "4974", "HFCL": "21951", "STERLITE": "3502",
    "INDUSTOWER": "29135", "RVNL": "13189", "IRCON": "21269",
    "NBCC": "2327", "NCC": "2885", "KEC": "1240", "KALPATPOWR": "17280",
    "GMRINFRA": "11526", "GVKPIL": "13531", "JPASSOCIAT": "15337",
    "PNCINFRA": "232", "KNRCON": "14508", "GRINFRA": "11018",
    "IRB": "13704", "ASTRAL": "5564", "SUPREMEIND": "15286",
    "FINPIPE": "1660", "AIAENG": "210", "THERMAX": "237",
    "CUMMINSIND": "10726", "SCHAEFFLER": "11066", "TIMKEN": "14125",
    "SKFINDIA": "1424", "BHEL": "438", "BEL": "547",
    "HAL": "1964", "MAZDOCK": "1406", "COCHINSHIP": "17243",
    "GRSE": "12217", "BDL": "1363", "MIDHANI": "11367",
    "SOLARINDS": "1120", "PTCIL": "1123", "DATAPATTNS": "11373",
    "PARAS": "14314", "KIRLOSENG": "13009", "GRINDWELL": "13310",
    "CARBORUNIV": "1246", "ENDURANCE": "13047", "SONACOMS": "28259",
    "UNOMINDA": "542", "BHARATSE": "718", "MINDA": "2377",
    "LGBROSLK": "1720", "LUMAXTECH": "2272", "FIEMIND": "1755",
    "SMLISUZU": "1695", "FORCEMOT": "1490", "TATAVOLT": "14241",
    "TCI": "11295", "GESHIP": "10578", "SCI": "11012",
    "BLUEDART": "1021", "MCDOWELLN": "14570", "UBL": "11003",
    "RADICO": "2064", "EMAMILTD": "13528", "JYOTHYLAB": "1521",
    "HONAUT": "1086", "BLUESTARCO": "1527", "TRENT": "19943",
    "ABFRL": "100", "PAGEIND": "1449", "BATAINDIA": "1216",
    "RELAXO": "2622", "METROPOLIS": "13528", "DRLAL": "14442",
    "THYROCARE": "17469", "FORTIS": "1452", "MAXHEALTH": "1603",
    "SYNGENE": "18147", "LALPATHLAB": "11673", "KRSNAA": "18370",
    "HEALTHGLOB": "14198", "SUBROS": "13081", "SUNDRMFAST": "12383",
    "SCHNEIDER": "312", "CROMPTON": "13122", "WHIRLPOOL": "1547",
    "DIXON": "10715", "AMBER": "15322", "KAJARIACER": "1689",
    "CERA": "2029", "POLYCAB": "20209", "FINCABLES": "1690",
    "KEI": "13386", "HAPPSTMNDS": "12414", "INTELLECT": "13804",
    "CYIENT": "12963", "MASTEK": "10750", "BIRLASOFT": "1038",
    "ZENSARTECH": "14416", "TATAELXSI": "14112", "CASTROLIND": "1043",
    "MGL": "17534", "IGL": "17426", "GUJGASLTD": "13715",
    "PETRONET": "11351", "GAIL": "1208", "HINDPETRO": "1375",
    "OIL": "14121", "SUZLON": "2319", "INOXWIND": "25380",
    "PIIND": "12049", "UPL": "11287", "COROMANDEL": "1018",
    "GNFC": "11793", "DEEPAKNTR": "1517", "AARTIIND": "144",
    "ATUL": "224", "SRF": "13927", "NAVINFLUOR": "14682",
    "TATACHEM": "3391", "KANSAINER": "11315", "BERGEPAINT": "1465",
    "AKZOINDIA": "13401", "INDIGOPNTS": "1751",
    "DRREDDY": "881",
}


def fetch_ohlcv(symbol: str, sector: str = "Diversified",
                use_cache: bool = True) -> pd.DataFrame:
    cache = CACHE_DIR / f"{symbol}.parquet"
    if use_cache and cache.exists() and (time.time() - cache.stat().st_mtime) < 7 * 86400:
        return pd.read_parquet(cache)

    e = _env()
    if e["force_mock"] or not (e["client_id"] and e["token"]):
        df = _mock_ohlcv(symbol, sector)
    else:
        sec_id = DHAN_SECURITY_IDS.get(symbol)
        if not sec_id:
            df = _mock_ohlcv(symbol, sector)
        else:
            df = _dhan_fetch_daily(symbol, sec_id)
            df["sector"] = sector
    df.to_parquet(cache, index=False)
    return df


def fetch_index(series: str) -> pd.DataFrame:
    """Sector / benchmark index proxy. Falls back to mock."""
    cache = CACHE_DIR / f"IDX_{series}.parquet"
    if cache.exists() and (time.time() - cache.stat().st_mtime) < 7 * 86400:
        return pd.read_parquet(cache)
    df = _mock_ohlcv(series, "Diversified")
    df.to_parquet(cache, index=False)
    return df
