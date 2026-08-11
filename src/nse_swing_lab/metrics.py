"""
Performance metrics for a backtested equity curve.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def perf_stats(equity: pd.Series, rf: float = 0.06) -> dict:
    rets = equity.pct_change().dropna()
    if rets.empty:
        return {"cagr": 0, "vol": 0, "sharpe": 0, "sortino": 0,
                "max_dd": 0, "calmar": 0, "win_rate": 0,
                "avg_win": 0, "avg_loss": 0, "trades": 0,
                "avg_hold": 0, "turnover": 0}

    days = (equity.index[-1] - equity.index[0]).days
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (365 / max(days, 1)) - 1
    vol = rets.std() * np.sqrt(252)
    sharpe = (rets.mean() * 252 - rf) / vol if vol > 0 else 0
    downside = rets[rets < 0].std() * np.sqrt(252)
    sortino = (rets.mean() * 252 - rf) / downside if downside > 0 else 0
    dd = equity / equity.cummax() - 1
    max_dd = dd.min()
    calmar = cagr / abs(max_dd) if max_dd < 0 else 0

    return {
        "cagr": float(cagr), "vol": float(vol),
        "sharpe": float(sharpe), "sortino": float(sortino),
        "max_dd": float(max_dd), "calmar": float(calmar),
    }


def trade_stats(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"win_rate": 0, "avg_win": 0, "avg_loss": 0,
                "trades": 0, "avg_hold": 0, "turnover": 0}
    wins = trades[trades["pnl_pct"] > 0]["pnl_pct"]
    losses = trades[trades["pnl_pct"] <= 0]["pnl_pct"]
    hold = (pd.to_datetime(trades["exit_date"]) -
            pd.to_datetime(trades["entry_date"])).dt.days
    return {
        "win_rate": float(len(wins) / len(trades)),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "trades": int(len(trades)),
        "avg_hold": float(hold.mean()) if len(hold) else 0.0,
        "turnover": float(len(trades)),  # placeholder
    }


def meets_targets(stats: dict, t: dict) -> bool:
    return (stats.get("sharpe", 0) >= t["sharpe"] and
            stats.get("max_dd", 0) > t["max_dd"])  # max_dd is negative
