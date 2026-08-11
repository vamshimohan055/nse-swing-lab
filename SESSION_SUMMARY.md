# Session summary — NSE Swing Lab (Aug 10–11, 2026)

## Goal
Build a public, NSE-focused, walk-forward backtester replicating the dropdown-driven
UX of https://backtest.architmittal.in (the reference site was crypto-only; the
NSE Swing Lab is original work on the Indian Nifty 200 universe).

## What was built

### Project scaffold
`C:\Users\Admin\Documents\nse-swing-lab\`

```
src/nse_swing_lab/
├── universe.py      # Nifty 200 membership + sector tags (280 symbols, 17 sector tags)
├── data.py          # DhanHQ daily-history client + parquet cache + deterministic mock
├── strategies.py    # 8 signal generators
├── backtest.py      # Walk-forward backtester, Indian cost model, ATR stop/target
├── metrics.py       # CAGR / Sharpe / Sortino / Calmar / max DD / win-rate / avg hold
├── regime.py        # Realized vol, ADX, drawdown, cross-sector dispersion verdict
├── pipeline.py      # Orchestrator (load → signals → backtest)
├── app.py           # Streamlit UI (6 pages)
└── report.py        # Writes reports/leaderboard.csv, REPORT.md, equity_top3.html
```

### 8 strategies implemented
RSI-2 Mean Reversion, Bollinger Band Fade, Z-Score, Momentum (benchmark),
Squeeze Breakout, Vol-Adaptive (MR/Mom switcher), Sector Rotation + RS-2,
Pairs-Relative (sector-relative long-only).

### Portfolio rules
Max 10 concurrent positions, ≤3 per sector, equal-weight slot sizing,
2×ATR stop, 4×ATR target, 15-trading-day time stop.

### Cost model (Indian, round-trip ≈ 0.13%)
Brokerage + STT + exchange/SEBI/GST + stamp + 7 bps/side slippage.

### Data
Mock fallback (no Dhan creds available in session): deterministic
sector-correlated GBM with regime shifts. 280 stock parquets + 17 sector
indices under `data/cache/`. Reproducible from a per-symbol seed.

### Streamlit UI (6 pages)
Analytics · Leaderboard · OG Symbols · Commodities · US Stock Futs · Sector deep-dive.

### Reports generated
`reports/REPORT.md`, `reports/leaderboard.csv`, `reports/equity_top3.html`,
plus per-strategy `equity_<strategy>.csv`.

### Headline result
No strategy hit Sharpe ≥ 1.0 on mock data. Best: Bollinger Band Fade
(Sharpe 0.35, max DD -9.4%, 415 trades). Honest academic finding,
documented in `REPORT.md`.

## What was deployed

| Asset | URL | Status |
|---|---|---|
| GitHub repo | https://github.com/vamshimohan055/nse-swing-lab | ✅ public, all 30 files committed |
| Streamlit Community Cloud | https://nse-swing-lab-i6cepredvexpuv3uu3sygyj.streamlit.app | ✅ live, dropdowns work |
| Cloudflare Pages (worker proxy) | https://nse-swing-lab.pages.dev | ⚠️ abandoned (WebSocket CORS issue) |
| Cloudflare Workers (your existing) | https://bold-heart-859e.vamshimohan055.workers.dev | ✅ yours, untouched |

## What was wasted (so we don't repeat it)

- **3 hours** trying to expose the local Streamlit through a Cloudflare
  Pages worker + cloudflared quick tunnel. The Streamlit 1.61 WebSocket
  auth checks `Host` vs `Origin` headers; the proxy can't rewrite them
  in a way that survives the upstream `fetch()`. **The right answer is
  Streamlit Community Cloud** — purpose-built, no proxy, free.
- **Python 3.14** was a broken install (no `python.exe` in the install
  root). Switched to Python 3.13.5 at
  `C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe`.
- `python.exe` in `PATH` is a Microsoft Store stub; always invoke the
  real interpreter at the full path.

## Next steps (when Dhan creds are available)

1. Sign up at https://dhan.co → API dashboard → generate
   `DHAN_CLIENT_ID` + `DHAN_ACCESS_TOKEN`.
2. Create `C:\Users\Admin\Documents\nse-swing-lab\.env`:
   ```
   DHAN_CLIENT_ID=...
   DHAN_ACCESS_TOKEN=...
   DHAN_FORCE_MOCK=0
   ```
3. Run `python -m nse_swing_lab.report` to regenerate the leaderboard
   with live data.
4. Push the new `.env`-derived behaviour via `git push` (or update the
   Streamlit Cloud secrets panel); the public app redeploys in ~2 min.
5. Dhan tokens expire daily — automate a daily refresh + push, or
   rotate manually before each run.

The only file likely to need a tweak is `src/nse_swing_lab/data.py`
(DhanClient.fetch). Everything downstream — backtester, strategies,
cost model, UI, reports — consumes whatever `data.py` returns and
needs no changes.

## Reproducing this build from scratch

```bash
cd C:\Users\Admin\Documents\nse-swing-lab
python -m pip install -e .   # or pip install pandas numpy streamlit plotly pyarrow requests python-dotenv tqdm
python -m streamlit run src\nse_swing_lab\app.py
# open http://localhost:8501
```

To regenerate the static report:
```bash
python -m nse_swing_lab.report
```

## Key files for mentor review

- `README.md` — architecture, quickstart, methodology
- `reports/REPORT.md` — auto-generated writeup
- `reports/leaderboard.csv` — strategy metrics
- `src/nse_swing_lab/backtest.py` — walk-forward engine
- `src/nse_swing_lab/strategies.py` — 8 signal generators
- `src/nse_swing_lab/data.py` — data layer (mock + Dhan)
