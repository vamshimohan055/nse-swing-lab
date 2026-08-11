"""
Orchestrator: load data, build signals, run backtest, return metrics.
"""
from __future__ import annotations
import datetime as dt
import pandas as pd

from . import data, strategies, universe, backtest
from .backtest import BacktestResult, CostModel, RiskRules


def load_universe_close(only_sector: str | None = None) -> tuple[pd.DataFrame, dict[str, str]]:
    syms = (universe.by_sector(only_sector)
            if only_sector else universe.all_symbols())
    frames = []
    sector_map: dict[str, str] = {}
    for s in syms:
        df = data.fetch_ohlcv(s.symbol, s.sector)
        df = df.set_index("date")
        frames.append(df["close"].rename(s.symbol))
        sector_map[s.symbol] = s.sector
    close = pd.concat(frames, axis=1).sort_index().ffill()
    # synthesize open from prior close for mock — backtester uses prices_open
    open_ = close.shift(1)
    return close, open_, sector_map


def load_index_closes(symbols: list[str]) -> dict[str, pd.Series]:
    return {s: data.fetch_index(s).set_index("date")["close"] for s in symbols}


def run_strategy(strategy_id: str, only_sector: str | None = None
                 ) -> BacktestResult:
    close, open_, sector_map = load_universe_close(only_sector)
    if strategy_id == "sector_rotate":
        idx_closes = load_index_closes(universe.sector_indices())
        common = close.index.intersection(idx_closes[list(idx_closes)[0]].index)
        u_close = close.loc[common]
        idx_aligned = {k: v.reindex(common) for k, v in idx_closes.items()}
        strategies.attach_sector_map(list(sector_map.items()))
        sig = strategies.relative_strength_sector(u_close, idx_aligned,
                                                  n=20, top_k=3)
        sig = sig.reindex(close.index).fillna(0)
    elif strategy_id == "pairs_rel":
        # Long the top N stocks by 60d return across the universe, short-free
        # (long-only). Acts as a "relative-strength" basket.
        ret = close.pct_change(60)
        sig = (ret.rank(axis=1, ascending=False) <= 10).astype(int)
        sig = sig.shift(1).fillna(0)
    else:
        sig = pd.DataFrame(0, index=close.index, columns=close.columns)
        _, fn, params = strategies.STRATEGIES[strategy_id]
        for col in close.columns:
            df_one = pd.DataFrame({"high": close[col] * 1.005,
                                   "low": close[col] * 0.995,
                                   "close": close[col]})
            if strategy_id == "rsi2":
                s = fn(close[col])
            elif strategy_id == "boll_fade":
                s = fn(close[col], **params)
            elif strategy_id == "zscore":
                s = fn(close[col], **params)
            elif strategy_id == "momentum":
                s = fn(close[col], **params)
            elif strategy_id == "squeeze":
                s = fn(df_one, **params)
            elif strategy_id == "vola_adaptive":
                s = fn(df_one)
            else:
                s = pd.Series(0, index=close.index)
            sig[col] = s.fillna(0)

    return backtest.backtest_long_only(
        prices_open=open_, prices_close=close, signals=sig,
        sector_map=sector_map,
    )
