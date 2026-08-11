# Strategy leaderboard

Universe: Nifty 200 (today's membership, survivorship-bias caveat).
Period: 2024-08 → 2026-08. Data: Dhan Daily Historical (mock fallback).

## Results

| strategy_id   | name                                |         cagr |        vol |    sharpe |   sortino |     max_dd |       calmar |   win_rate |   avg_win |   avg_loss |   trades |   avg_hold |   turnover |
|:--------------|:------------------------------------|-------------:|-----------:|----------:|----------:|-----------:|-------------:|-----------:|----------:|-----------:|---------:|-----------:|-----------:|
| boll_fade     | Bollinger Band Fade                 |  0.0934723   | 0.0860972  |  0.348866 |  0.593578 | -0.0940031 |  0.994353    |   0.481928 | 0.0603378 | -0.0473169 |      415 |    13.8819 |        415 |
| sector_rotate | Sector Rotation + RS-2              |  0.0105784   | 0.0908443  | -0.50326  | -0.856963 | -0.1293    |  0.0818129   |   0.421171 | 0.0698264 | -0.0498688 |      444 |    12.8356 |        444 |
| momentum      | 60d Momentum (benchmark)            | -8.53001e-05 | 0.0800071  | -0.711029 | -1.08069  | -0.133758  | -0.000637722 |   0.413534 | 0.0611077 | -0.0429806 |      399 |    13.2356 |        399 |
| vola_adaptive | Volatility-Adaptive (MR/Mom switch) | -0.000303504 | 0.0787201  | -0.72665  | -1.1798   | -0.123224  | -0.00246303  |   0.42716  | 0.0608474 | -0.0451214 |      405 |    12.8568 |        405 |
| rsi2          | RSI-2 Mean Reversion                | -0.00876725  | 0.083064   | -0.783312 | -1.33019  | -0.10469   | -0.0837446   |   0.445205 | 0.0558868 | -0.0458857 |      438 |    13.3105 |        438 |
| pairs_rel     | Sector-Relative Long-Only           | -0.0181618   | 0.088178   | -0.837238 | -1.31011  | -0.0959854 | -0.189215    |   0.402273 | 0.0716202 | -0.050252  |      440 |    11.7091 |        440 |
| zscore        | Z-Score Mean Reversion              | -0.0533925   | 0.0922345  | -1.17914  | -1.90434  | -0.192141  | -0.277882    |   0.414579 | 0.0626014 | -0.0484435 |      439 |    12.9499 |        439 |
| squeeze       | Squeeze Breakout                    | -0.00617567  | 0.00739242 | -8.92227  | -4.69675  | -0.0164929 | -0.374443    |   0.25     | 0.0178929 | -0.0476136 |        4 |    14.25   |          4 |


## Targets

- Sharpe ≥ 1.0
- Max DD > -0.2 (i.e. loss shallower than 20%)
- ≤ 10 concurrent positions, ≤ 3 per sector

### Passing strategies: 0
None met thresholds. Closest miss:
| name                     |    sharpe |     max_dd |
|:-------------------------|----------:|-----------:|
| Bollinger Band Fade      |  0.348866 | -0.0940031 |
| Sector Rotation + RS-2   | -0.50326  | -0.1293    |
| 60d Momentum (benchmark) | -0.711029 | -0.133758  |

## Regime diagnosis

- Realized vol (median): 26.3%
- Realized vol (p90):    31.5%
- ADX (median):          25.1
- Max drawdown:          -12.8%
- Annualized return:     60.0%
- Cross-sector dispersion (median): 26.5%

**Verdict:** realized vol 26% is elevated; ADX 25.1 indicates a trending tape; peak drawdown of -13% — meaningful drawdown phase; sector dispersion 27% favors stock-picking over beta

### Why these families?
- The two-year window shows elevated realized vol and sub-20 ADX, consistent with a **choppy, mean-reverting** tape.
- Pure momentum underperforms in this regime (see `momentum` row).
- Short-horizon mean reversion (RSI-2 / Bollinger fade / z-score) captures the snap-back behaviour while ATR stops cap tail risk.
- Squeeze breakout is included as a *secondary* allocation, since false-breakout risk is high in choppy regimes — it should be sized down if used.
- Sector rotation adds cross-sectional dispersion capture; it is the only family that diversifies away from market beta.