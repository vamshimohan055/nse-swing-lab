"""Streamlit app replicating the ARCHIT backtest dropdowns (Strategy /
Timeframe / Symbol) plus sector headings (Nifty IT / Pharma / Healthcare,
etc) and per-strategy performance metrics + equity curve + drawdown.

Run: `streamlit run src/nse_swing_lab/app.py`
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from nse_swing_lab import strategies, universe, pipeline, regime, metrics

st.set_page_config(page_title="NSE Swing Lab", layout="wide")

st.title("NSE Swing Lab — Backtesting Intelligence")
st.caption("Nifty 200, 2024-08 → 2026-08. No Dhan credentials? Mock OHLCV is used "
           "(toggle DHAN_FORCE_MOCK=0 in .env to call the live API).")

# ---------------- Sidebar ----------------
st.sidebar.header("Regime diagnosis")
with st.sidebar.expander("Market regime (last 2y)", expanded=True):
    diag = regime.diagnose()
    st.metric("Realized vol (median)", f"{diag['realized_vol_median']:.1%}")
    st.metric("ADX (median)", f"{diag['adx_median']:.1f}")
    st.metric("Max drawdown", f"{diag['max_drawdown']:.1%}")
    st.metric("Annualized return", f"{diag['annualized_return']:.1%}")
    st.write(diag["verdict"])

# ---------------- Tabs ----------------
tabs = st.tabs(["Analytics", "Leaderboard", "OG Symbols",
                "Commodities", "US Stock Futs", "Sector deep-dive"])

# --- Analytics tab ---
with tabs[0]:
    st.subheader("Analytics")
    col1, col2, col3 = st.columns(3)
    strat_id = col1.selectbox(
        "Strategy",
        strategies.list_strategies(),
        format_func=lambda s: strategies.STRATEGIES[s][0])
    timeframe = col2.selectbox("Timeframe", ["Daily (swing)"])
    sym_options = ["Nifty 200 (basket)"] + [s.symbol for s in universe.all_symbols()[:50]]
    symbol = col3.selectbox("Symbol", sym_options)

    if st.button("Run backtest", type="primary"):
        with st.spinner("Running backtest…"):
            try:
                if symbol == "Nifty 200 (basket)":
                    res = pipeline.run_strategy(strat_id)
                else:
                    res = pipeline.run_strategy(strat_id, only_sector=None)
                perf = metrics.perf_stats(res.equity)
                trd = metrics.trade_stats(res.trades)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Sharpe", f"{perf['sharpe']:.2f}")
                m2.metric("Max DD", f"{perf['max_dd']:.1%}")
                m3.metric("Win %", f"{trd['win_rate']:.1%}")
                m4.metric("Loss %", f"{1 - trd['win_rate']:.1%}")
                m5, m6, m7, m8 = st.columns(4)
                m5.metric("CAGR", f"{perf['cagr']:.1%}")
                m6.metric("Trades", int(trd['trades']))
                m7.metric("Avg hold (d)", f"{trd['avg_hold']:.1f}")
                m8.metric("Calmar", f"{perf['calmar']:.2f}")
                eq_fig = go.Figure()
                eq_fig.add_trace(go.Scatter(x=res.equity.index, y=res.equity,
                                            name="Equity"))
                eq_fig.update_layout(title="Equity curve", height=320)
                st.plotly_chart(eq_fig, use_container_width=True)
                dd_fig = go.Figure()
                dd_fig.add_trace(go.Scatter(x=res.drawdown.index, y=res.drawdown,
                                            fill="tozeroy", name="Drawdown"))
                dd_fig.update_layout(title="Drawdown", height=220)
                st.plotly_chart(dd_fig, use_container_width=True)
                st.subheader("Trade log (tail)")
                st.dataframe(res.trades.tail(25), use_container_width=True)
            except Exception as ex:
                st.error(f"Backtest failed: {ex}")

# --- Leaderboard tab ---
with tabs[1]:
    st.subheader("Strategy leaderboard")
    if st.button("Compute leaderboard"):
        rows = []
        progress = st.progress(0.0)
        for i, sid in enumerate(strategies.list_strategies()):
            try:
                res = pipeline.run_strategy(sid)
                p = metrics.perf_stats(res.equity)
                t = metrics.trade_stats(res.trades)
                rows.append({
                    "Strategy": strategies.STRATEGIES[sid][0],
                    "Sharpe": round(p["sharpe"], 2),
                    "MaxDD": round(p["max_dd"], 3),
                    "CAGR": round(p["cagr"], 3),
                    "Calmar": round(p["calmar"], 2),
                    "Trades": t["trades"],
                    "Win%": round(t["win_rate"], 3),
                })
            except Exception as ex:
                rows.append({"Strategy": strategies.STRATEGIES[sid][0],
                             "Error": str(ex)[:50]})
            progress.progress((i + 1) / len(strategies.list_strategies()))
        df = pd.DataFrame(rows).sort_values("Sharpe", ascending=False)
        st.dataframe(df, use_container_width=True)

# --- Sector deep-dive tab ---
with tabs[5]:
    st.subheader("Sector deep-dive")
    sector = st.selectbox("Sector", universe.SECTORS)
    sid = st.selectbox("Strategy", strategies.list_strategies(),
                       format_func=lambda s: strategies.STRATEGIES[s][0],
                       key="sector_sid")
    if st.button("Run on sector", key="sector_run"):
        with st.spinner(f"Running on {sector}…"):
            res = pipeline.run_strategy(sid, only_sector=sector)
            perf = metrics.perf_stats(res.equity)
            st.metric("Sharpe", f"{perf['sharpe']:.2f}")
            st.metric("Max DD", f"{perf['max_dd']:.1%}")
            st.line_chart(res.equity)
            st.line_chart(res.drawdown)

# Other tabs: placeholders
for t in (tabs[2], tabs[3], tabs[4]):
    with t:
        st.info("Coming soon.")
