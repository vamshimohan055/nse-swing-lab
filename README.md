# NSE Swing Lab

A systematic swing-trading research platform for Indian equities (Nifty 200).
Long-only, 3–15 trading day holds, max 10 concurrent positions, sector cap 3,
ATR-based stop / target, custom walk-forward backtester, Indian cost model,
and a Streamlit UI modeled on the dropdown UX of the architmittal.in
backtesting site.

> **Reference-site mismatch note.** The site you linked
> (https://backtest.architmittal.in) is a *crypto* strategy leaderboard for
> the window 2025-01-01 → 2026-05-15. The brief was NSE equities over
> 2024-08 → 2026-08. Per your decision, this codebase replicates the
> *functionality* (Strategy / Timeframe / Symbol dropdowns, plus the per-
> sector "Nifty IT / Pharma / Healthcare / …" deep-dive) on the NSE
> universe, **not** the visual layout. The deliverables therefore are an
> original NSE backtester, not a clone of the crypto site.

## Quickstart

```bash
cd nse-swing-lab
python -m pip install -e .          # or: pip install pandas numpy streamlit plotly pyarrow requests python-dotenv tqdm
python -m streamlit run src/nse_swing_lab/app.py
# open http://localhost:8501
```

To regenerate the static report (leaderboard CSV, REPORT.md, top-3 chart):

```bash
python -m nse_swing_lab.report
```

## Architecture

```
src/nse_swing_lab/
├── universe.py      # Nifty 200 membership + sector tags (today's list — survivorship-bias caveat)
├── data.py          # DhanHQ daily-history client + parquet cache + deterministic mock fallback
├── strategies.py    # 8 signal generators (RSI-2, Bollinger fade, z-score, momentum,
│                    #   squeeze breakout, vol-adaptive switcher, sector rotation, pairs-relative)
├── backtest.py      # Walk-forward backtester, Indian cost model, ATR stop/target, time stop,
│                    #   max-10 positions, max-3 per sector, equal-weight sizing
├── metrics.py       # CAGR / Sharpe / Sortino / Calmar / max DD / win-rate / avg hold
├── regime.py        # Realized vol, ADX, drawdown, cross-sector dispersion verdict
├── pipeline.py      # Orchestrator: load data -> build signals -> backtest
├── app.py           # Streamlit UI (Analytics / Leaderboard / OG Symbols / Commodities /
│                    #   US Stock Futs / Sector deep-dive)
└── report.py        # Writes reports/leaderboard.csv, REPORT.md, equity_top3.html
```

## Configuration

Copy `.env.example` to `.env` and fill in Dhan credentials when available:

```
DHAN_CLIENT_ID=...
DHAN_ACCESS_TOKEN=...
DHAN_FORCE_MOCK=0   # 1 = always use the synthetic fallback
```

Without credentials the client serves a deterministic mock dataset
(sector-correlated geometric Brownian motion with regime shifts) so the
entire pipeline runs offline and reproducibly.

## Strategies

| ID            | Name                              | Family           |
| ------------- | --------------------------------- | ---------------- |
| `rsi2`        | RSI-2 Mean Reversion              | MR               |
| `boll_fade`   | Bollinger Band Fade               | MR               |
| `zscore`      | Z-Score Mean Reversion            | MR               |
| `momentum`    | 60d Momentum (benchmark)          | Trend            |
| `squeeze`     | Squeeze Breakout (TTM-style)      | Vol contraction  |
| `vola_adaptive` | Vol-Adaptive (MR/Mom switcher)   | Regime switch    |
| `sector_rotate` | Sector Rotation + RS-2 filter   | Cross-sectional  |
| `pairs_rel`   | Sector-relative long-only         | Relative value   |

## Data

- **Universe:** Nifty 200 (current membership). Point-in-time membership is
  not freely available, so the backtest is biased upward — treat absolute
  numbers with caution and use *strategy ranking* as the primary signal.
- **Window:** 2024-08-01 → 2026-08-01, daily OHLCV.
- **Source:** DhanHQ `/charts/historical` (daily endpoint) with a parquet
  cache under `data/cache/`. Falls back to a deterministic mock when no
  credentials are configured.

## Risk & portfolio rules

- Max 10 concurrent positions
- Max 3 positions per sector
- Equal-weight slot sizing (1/10 of current equity)
- 2×ATR stop, 4×ATR target, 15-trading-day time stop
- Round-trip cost ≈ 0.13% (brokerage + STT + exchange/SEBI/GST + stamp
  + 7 bps/side slippage)

## Targets

- Preferred Sharpe ≥ 1.5, acceptable 1.0–1.5
- Max drawdown strictly < 20%
- The static report flags which strategies meet the thresholds and which
  fall just short, with the trade-off explained.
