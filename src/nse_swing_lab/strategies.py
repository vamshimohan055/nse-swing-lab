"""
Strategy library.

Each strategy returns a pd.Series of desired position weights per symbol,
indexed by date, with values in {-1, 0, +1} (long-only in this swing system,
so values are {0, +1}). Signal generated on close(T), executed at open(T+1).
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class Signal:
    name: str
    description: str
    params: dict


# ---------- indicator helpers ----------

def rsi(close: pd.Series, n: int = 2) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(n).mean()
    loss = (-delta.clip(upper=0)).rolling(n).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def zscore(close: pd.Series, n: int = 20) -> pd.Series:
    return (close - close.rolling(n).mean()) / close.rolling(n).std()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up = high.diff()
    dn = -low.diff()
    plus_dm = ((up > dn) & (up > 0)) * up
    minus_dm = ((dn > up) & (dn > 0)) * dn
    tr = pd.concat([(high - low), (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    plus_di = 100 * plus_dm.rolling(n).mean() / atr
    minus_di = 100 * minus_dm.rolling(n).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.rolling(n).mean()


def realized_vol(close: pd.Series, n: int = 20) -> pd.Series:
    return close.pct_change().rolling(n).std() * np.sqrt(252)


def keltner_squeeze(df: pd.DataFrame, n: int = 20, n_atr: float = 1.5) -> pd.Series:
    """True Range Bollinger Squeeze: returns 1 when in squeeze (low vol)."""
    tr = pd.concat([(df["high"] - df["low"]),
                    (df["high"] - df["close"].shift()).abs(),
                    (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(n).mean()
    sma = df["close"].rolling(n).mean()
    bbw = (df["close"].rolling(n).std() * 2) * n_atr
    return (bbw < atr * n_atr).astype(int)


# ---------- per-stock signal generators ----------

def sig_rsi2(close: pd.Series) -> pd.Series:
    """Mean-reversion: long when RSI-2 < 10, exit next day."""
    r = rsi(close, 2)
    sig = pd.Series(0, index=close.index)
    sig[r < 10] = 1
    sig = sig.shift(1).fillna(0)  # hold next day
    return sig


def sig_boll_fade(close: pd.Series, n: int = 20) -> pd.Series:
    """Long when close < lower Bollinger band, exit next day."""
    sma = close.rolling(n).mean()
    sd = close.rolling(n).std()
    sig = pd.Series(0, index=close.index)
    sig[close < sma - 2 * sd] = 1
    return sig.shift(1).fillna(0)


def sig_zscore(close: pd.Series, n: int = 20, thr: float = -1.5) -> pd.Series:
    z = zscore(close, n)
    sig = pd.Series(0, index=close.index)
    sig[z < thr] = 1
    return sig.shift(1).fillna(0)


def sig_momentum(close: pd.Series, n: int = 60) -> pd.Series:
    """Benchmark momentum: long top by 6m return, rebalanced weekly."""
    ret = close.pct_change(n)
    sig = pd.Series(0, index=close.index)
    sig[ret > 0] = 1
    return sig.shift(1).fillna(0)


def sig_squeeze_breakout(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """Volatility-contraction breakout: long when squeeze just released + close > SMA."""
    sq = keltner_squeeze(df, n)
    sma = df["close"].rolling(n).mean()
    released = (sq.shift(1) == 1) & (sq == 0)
    sig = pd.Series(0, index=df.index)
    sig[released & (df["close"] > sma)] = 1
    return sig.shift(1).fillna(0)


def sig_vola_adaptive(df: pd.DataFrame) -> pd.Series:
    """Regime switcher: momentum in trending, mean-reversion in choppy."""
    a = adx(df, 14)
    r = realized_vol(df["close"], 20)
    trending = a > 20
    high_vol = r > r.rolling(120).median()
    sig = pd.Series(0, index=df.index)
    # trending: momentum
    ret = df["close"].pct_change(60)
    sig[trending & (ret > 0)] = 1
    # choppy high-vol: mean reversion via z-score
    z = zscore(df["close"], 20)
    sig[(~trending) & high_vol & (z < -1.5)] = 1
    return sig.shift(1).fillna(0)


def sig_pairs_relative(close_a: pd.Series, close_b: pd.Series,
                       n: int = 60) -> pd.Series:
    """Long-only relative value: long A, short B (we cap at long-only = take
    spread>0). Spread = z-score of (A/B) over n days."""
    spread = (close_a / close_b).pct_change(n)
    sig = pd.Series(0, index=close_a.index)
    sig[spread > 0] = 1
    return sig.shift(1).fillna(0)


# ---------- universe-level signal routers ----------

def relative_strength_sector(universe_close: pd.DataFrame,
                              index_close_dict: dict[str, pd.Series],
                              n: int = 20, top_k: int = 3) -> pd.DataFrame:
    """Rank NSE sector indices by N-day return; rotate universe to stocks
    inside the top_k sectors, picked by RSI-2 mean-reversion."""
    rs = pd.DataFrame({k: v.pct_change(n) for k, v in index_close_dict.items()})
    top_idx = rs.rank(axis=1, ascending=False) <= top_k
    sig = pd.DataFrame(0, index=universe_close.index, columns=universe_close.columns)
    for col in universe_close.columns:
        sec = _sector_of(col)
        idx_name = SECTOR_TO_INDEX.get(sec)
        if idx_name is None or idx_name not in top_idx.columns:
            continue
        in_top = top_idx[idx_name]
        r = rsi(universe_close[col], 2)
        sig[col] = ((r < 15) & in_top).astype(int)
    return sig


SECTOR_TO_INDEX = {
    "Nifty IT": "NIFTY_IT",
    "Nifty Pharma": "NIFTY_PHARMA",
    "Nifty Healthcare": "NIFTY_HEALTHCARE",
    "Nifty Bank": "NIFTY_BANK",
    "Nifty Auto": "NIFTY_AUTO",
    "Nifty FMCG": "NIFTY_FMCG",
    "Nifty Energy": "NIFTY_ENERGY",
    "Nifty Metal": "NIFTY_METAL",
    "Nifty Realty": "NIFTY_REALTY",
    "Nifty Infra": "NIFTY_INFRA",
    "Nifty PSU Bank": "NIFTY_PSUBANK",
    "Nifty Media": "NIFTY_MEDIA",
    "Nifty Financial Services": "NIFTY_FIN_SERVICE",
    "Nifty Consumer Durables": "NIFTY_CONSUM_DUR",
}


_SECTOR_OF = {}  # populated by universe.attach_sector_map


def _sector_of(sym: str) -> str:
    return _SECTOR_OF.get(sym, "Diversified")


def attach_sector_map(symbols_with_sector: list[tuple[str, str]]) -> None:
    _SECTOR_OF.update(dict(symbols_with_sector))


# ---------- registry ----------

STRATEGIES = {
    "rsi2":          ("RSI-2 Mean Reversion", sig_rsi2, {"n": 2}),
    "boll_fade":     ("Bollinger Band Fade",  sig_boll_fade, {"n": 20}),
    "zscore":        ("Z-Score Mean Reversion", sig_zscore, {"n": 20}),
    "momentum":      ("60d Momentum (benchmark)", sig_momentum, {"n": 60}),
    "squeeze":       ("Squeeze Breakout", sig_squeeze_breakout, {"n": 20}),
    "vola_adaptive": ("Volatility-Adaptive (MR/Mom switch)", sig_vola_adaptive, {}),
    "sector_rotate": ("Sector Rotation + RS-2", "special", {"n": 20, "top_k": 3}),
    "pairs_rel":     ("Sector-Relative Long-Only", "special", {"n": 60}),
}


def list_strategies() -> list[str]:
    return list(STRATEGIES.keys())
