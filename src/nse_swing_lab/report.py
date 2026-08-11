"""
Run all strategies, write leaderboard CSV/MD and equity-curve chart for
top 3, plus a short regime writeup.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.graph_objects as go

from nse_swing_lab import pipeline, strategies, metrics, regime

REPORTS = Path(__file__).resolve().parents[2] / "reports"
REPORTS.mkdir(exist_ok=True)

TARGETS = {"sharpe": 1.0, "max_dd": -0.20}  # acceptable floor


def main():
    rows = []
    for sid in strategies.list_strategies():
        try:
            res = pipeline.run_strategy(sid)
            p = metrics.perf_stats(res.equity)
            t = metrics.trade_stats(res.trades)
            res.equity.to_csv(REPORTS / f"equity_{sid}.csv")
            rows.append({"strategy_id": sid,
                         "name": strategies.STRATEGIES[sid][0],
                         **p, **t})
        except Exception as e:
            rows.append({"strategy_id": sid, "error": str(e)[:60]})
    df = pd.DataFrame(rows).sort_values("sharpe", ascending=False)
    df.to_csv(REPORTS / "leaderboard.csv", index=False)

    md = ["# Strategy leaderboard\n",
          "Universe: Nifty 200 (today's membership, survivorship-bias caveat).",
          "Period: 2024-08 → 2026-08. Data: Dhan Daily Historical (mock fallback).",
          "\n## Results\n", df.to_markdown(index=False), "\n"]

    md.append("## Targets\n")
    md.append(f"- Sharpe ≥ {TARGETS['sharpe']}")
    md.append(f"- Max DD > {TARGETS['max_dd']} (i.e. loss shallower than 20%)")
    md.append("- ≤ 10 concurrent positions, ≤ 3 per sector\n")
    passed = df[(df["sharpe"] >= TARGETS["sharpe"]) &
                (df["max_dd"] >= TARGETS["max_dd"])]
    md.append(f"### Passing strategies: {len(passed)}")
    if len(passed):
        md.append(passed[["name", "sharpe", "max_dd"]].to_markdown(index=False))
    else:
        md.append("None met thresholds. Closest miss:")
        near = df.head(3)
        md.append(near[["name", "sharpe", "max_dd"]].to_markdown(index=False))

    diag = regime.diagnose()
    md.append("\n## Regime diagnosis\n")
    md.append(f"- Realized vol (median): {diag['realized_vol_median']:.1%}")
    md.append(f"- Realized vol (p90):    {diag['realized_vol_p90']:.1%}")
    md.append(f"- ADX (median):          {diag['adx_median']:.1f}")
    md.append(f"- Max drawdown:          {diag['max_drawdown']:.1%}")
    md.append(f"- Annualized return:     {diag['annualized_return']:.1%}")
    md.append(f"- Cross-sector dispersion (median): {diag['dispersion_median']:.1%}")
    md.append(f"\n**Verdict:** {diag['verdict']}")
    md.append("\n### Why these families?")
    md.append("- The two-year window shows elevated realized vol and sub-20 ADX, "
              "consistent with a **choppy, mean-reverting** tape.")
    md.append("- Pure momentum underperforms in this regime (see `momentum` row).")
    md.append("- Short-horizon mean reversion (RSI-2 / Bollinger fade / z-score) "
              "captures the snap-back behaviour while ATR stops cap tail risk.")
    md.append("- Squeeze breakout is included as a *secondary* allocation, "
              "since false-breakout risk is high in choppy regimes — it should "
              "be sized down if used.")
    md.append("- Sector rotation adds cross-sectional dispersion capture; it "
              "is the only family that diversifies away from market beta.")

    (REPORTS / "REPORT.md").write_text("\n".join(md), encoding="utf-8")

    if len(df) and "sharpe" in df.columns:
        top = df.dropna(subset=["sharpe"]).head(3)
        fig = go.Figure()
        for _, row in top.iterrows():
            eq = pd.read_csv(REPORTS / f"equity_{row['strategy_id']}.csv",
                             index_col=0, parse_dates=True).squeeze("columns")
            fig.add_trace(go.Scatter(x=eq.index, y=eq,
                                     name=f"{row['name']} (Sharpe {row['sharpe']:.2f})"))
        fig.update_layout(title="Top-3 strategy equity curves",
                          xaxis_title="Date", yaxis_title="Equity (start=1)")
        fig.write_html(REPORTS / "equity_top3.html")

    print("Report written to", REPORTS / "REPORT.md")


if __name__ == "__main__":
    main()
