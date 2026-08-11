"""
Regime diagnosis: characterize the 2y window (Aug 2024 -> Aug 2026) so we
can pick the right strategy family with evidence rather than intuition.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from . import data, strategies, universe


def diagnose(proxy_symbol: str = "NIFTY_50") -> dict:
    """Use the Nifty-50 mock/index as a market proxy. Returns a dict of
    metrics that we render in the UI."""
    df = data.fetch_index(proxy_symbol).set_index("date")
    close = df["close"]
    ret = close.pct_change().dropna()

    rv = ret.rolling(20).std() * np.sqrt(252)
    adx_ = pd.Series(0.0, index=close.index)
    # reuse strategies.adx on a fake OHLC frame
    fake = pd.DataFrame({"high": close * 1.005, "low": close * 0.995, "close": close})
    adx_ = strategies.adx(fake, 14)

    cum = close / close.iloc[0] - 1
    dd = close / close.cummax() - 1

    # cross-sector dispersion: stdev of N-day returns across sector indices
    secs = universe.sector_indices()
    sec_rets = pd.DataFrame({s: data.fetch_index(s).set_index("date")["close"]
                             for s in secs}).pct_change()
    dispersion = sec_rets.std(axis=1).rolling(20).mean() * np.sqrt(252)

    return {
        "realized_vol_median": float(rv.median()),
        "realized_vol_p90": float(rv.quantile(0.9)),
        "adx_median": float(adx_.median()),
        "max_drawdown": float(dd.min()),
        "drawdown_days": int(((dd < 0).sum())),
        "annualized_return": float((close.iloc[-1] / close.iloc[0]) **
                                   (252 / max(len(close), 1)) - 1),
        "dispersion_median": float(dispersion.median()),
        "verdict": _verdict(rv.median(), adx_.median(), dd.min(),
                            dispersion.median()),
    }


def _verdict(rv_med, adx_med, max_dd, disp_med) -> str:
    """Plain-language summary used in the UI."""
    pieces = []
    if rv_med > 0.15:
        pieces.append(f"realized vol {rv_med:.0%} is elevated")
    else:
        pieces.append(f"realized vol {rv_med:.0%} is moderate")
    if adx_med < 18:
        pieces.append(f"ADX {adx_med:.1f} indicates a **non-trending / choppy** tape")
    else:
        pieces.append(f"ADX {adx_med:.1f} indicates a trending tape")
    if max_dd < -0.10:
        pieces.append(f"peak drawdown of {max_dd:.0%} — meaningful drawdown phase")
    if disp_med > 0.05:
        pieces.append(f"sector dispersion {disp_med:.0%} favors stock-picking over beta")
    return "; ".join(pieces)
