"""
Nifty 200 universe with sector tags.

Source: NSE's Nifty 200 index constituents list (snapshot).
SURVIVORSHIP BIAS CAVEAT: this is today's membership applied across the
full 2-year window. Point-in-time membership is not freely available,
so backtested results are biased upward; treat absolute performance
figures with caution and use the strategy *ranking* (relative ordering
between strategies) as the primary signal.
"""
from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "nifty200.csv"

SECTORS = [
    "Nifty IT",
    "Nifty Pharma",
    "Nifty Healthcare",
    "Nifty Bank",
    "Nifty Auto",
    "Nifty FMCG",
    "Nifty Energy",
    "Nifty Metal",
    "Nifty Realty",
    "Nifty Infra",
    "Nifty PSU Bank",
    "Nifty Media",
    "Nifty Financial Services",
    "Nifty Consumer Durables",
    "Nifty Oil & Gas",
    "Nifty MNC",
    "Diversified",
]


@dataclass(frozen=True)
class Symbol:
    symbol: str           # Dhan security id-less ticker, e.g. "RELIANCE"
    name: str             # Display name
    sector: str           # One of SECTORS


def _load() -> list[Symbol]:
    out: list[Symbol] = []
    with DATA_FILE.open() as f:
        for row in csv.DictReader(f):
            out.append(Symbol(row["symbol"].strip().upper(),
                              row["name"].strip(),
                              row["sector"].strip()))
    return out


def all_symbols() -> list[Symbol]:
    return _load()


def by_sector(sector: str) -> list[Symbol]:
    return [s for s in _load() if s.sector == sector]


def sector_indices() -> list[str]:
    """Index proxies for the sector-rotation strategy (CNX/NSM tickers)."""
    return [
        "NIFTY_IT",
        "NIFTY_PHARMA",
        "NIFTY_HEALTHCARE",
        "NIFTY_BANK",
        "NIFTY_AUTO",
        "NIFTY_FMCG",
        "NIFTY_ENERGY",
        "NIFTY_METAL",
        "NIFTY_REALTY",
        "NIFTY_INFRA",
        "NIFTY_PSUBANK",
        "NIFTY_MEDIA",
        "NIFTY_FIN_SERVICE",
        "NIFTY_CONSUM_DUR",
    ]


def benchmark_symbols() -> dict[str, str]:
    return {"Nifty 50": "NIFTY_50", "Nifty 200": "NIFTY_200"}
