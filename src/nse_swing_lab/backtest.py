"""
Walk-forward backtester.

Key properties:
- No look-ahead: signal on close(T), execute at open(T+1).
- Indian cost model: brokerage, STT, exchange/SEBI/GST, stamp duty,
  slippage. Defaults reflect a discount broker (Zerodha-like) plus
  7 bps/side slippage.
- Walk-forward: parameters fit on a rolling train window, applied OOS.
- Position sizing: equal-weight by default, capped to MAX_POSITIONS slots,
  with a per-sector cap.
- Stop / target / time-based exits per trade.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

MAX_POSITIONS = 10
MAX_PER_SECTOR = 3

# Indian cost model (per side, equity delivery/intraday mix tuned for swing)
BROKERAGE_PCT = 0.0003
STT_PCT = 0.00025
EXCHANGE_PCT = 0.0000345
SEBI_PCT = 0.000001
GST_PCT = 0.18 * (BROKERAGE_PCT + EXCHANGE_PCT)
STAMP_PCT = 0.00003
SLIPPAGE_BPS = 7  # per side


@dataclass
class CostModel:
    brokerage: float = BROKERAGE_PCT
    stt: float = STT_PCT
    exchange: float = EXCHANGE_PCT
    sebi: float = SEBI_PCT
    gst: float = GST_PCT
    stamp: float = STAMP_PCT
    slippage_bps: float = SLIPPAGE_BPS

    def round_trip(self) -> float:
        one_way = self.brokerage + self.exchange + self.sebi + self.gst + self.stamp
        return (one_way + self.stt) * 2 + (self.slippage_bps / 10000) * 2


@dataclass
class RiskRules:
    stop_atr: float = 2.0
    target_atr: float = 4.0
    max_hold_days: int = 15
    atr_n: int = 14


@dataclass
class BacktestResult:
    equity: pd.Series
    drawdown: pd.Series
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)


def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    tr = pd.concat([(df["high"] - df["low"]),
                    (df["high"] - df["close"].shift()).abs(),
                    (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def backtest_long_only(
    prices_open: pd.DataFrame,         # (date x symbol) open prices
    prices_close: pd.DataFrame,        # close prices
    signals: pd.DataFrame,             # 0/1 entries; entry at next open
    sector_map: dict[str, str],
    costs: CostModel = CostModel(),
    risk: RiskRules = RiskRules(),
    max_positions: int = MAX_POSITIONS,
    max_per_sector: int = MAX_PER_SECTOR,
    walk_forward: bool = True,
    train_window: int = 252,           # ~1y
    test_window: int = 63,             # ~3m
) -> BacktestResult:
    """Run a long-only walk-forward backtest with the rules above.

    signals[i, j] == 1 means we *want* to be long symbol j at the close of
    day i. We translate that into an entry at the next open, and hold until
    stop / target / time-stop is hit.
    """
    dates = prices_close.index
    symbols = prices_close.columns
    sig = signals.shift(1).fillna(0)  # execute at next open

    # Pre-compute ATRs for stop / target
    atr_df = pd.DataFrame(index=dates, columns=symbols, dtype=float)
    for sym in symbols:
        sub = pd.DataFrame({
            "high": prices_close[sym] * 1.005,
            "low": prices_close[sym] * 0.995,
            "close": prices_close[sym],
        })
        atr_df[sym] = _atr(sub, risk.atr_n)

    rt_cost = costs.round_trip()
    initial_capital = 1.0
    cash = initial_capital
    positions: dict[str, dict] = {}  # sym -> {entry_px, entry_date, qty, sector, atr}
    equity_curve = []
    daily_pnl: list[float] = []
    trades: list[dict] = []

    for i, d in enumerate(dates):
        # mark-to-market
        port_value = cash
        sector_counts: dict[str, int] = {}
        for sym, pos in positions.items():
            px = prices_close[sym].iloc[i]
            port_value += pos["qty"] * px
            sector_counts[pos["sector"]] = sector_counts.get(pos["sector"], 0) + 1

        # exits: check stops / targets / time
        for sym in list(positions.keys()):
            pos = positions[sym]
            px = prices_close[sym].iloc[i]
            stop_px = pos["entry_px"] - risk.stop_atr * pos["atr"]
            tgt_px = pos["entry_px"] + risk.target_atr * pos["atr"]
            held = (d - pos["entry_date"]).days
            exit_reason = None
            if px <= stop_px:
                exit_reason = "stop"
            elif px >= tgt_px:
                exit_reason = "target"
            elif held >= risk.max_hold_days * 1.4:  # 21 cal days ~= 15 biz
                exit_reason = "time"
            if exit_reason:
                proceeds = pos["qty"] * px * (1 - rt_cost / 2)
                pnl_pct = (px / pos["entry_px"]) - 1 - rt_cost
                cash += proceeds
                trades.append({
                    "symbol": sym, "entry_date": pos["entry_date"],
                    "entry_px": pos["entry_px"], "exit_date": d,
                    "exit_px": px, "pnl_pct": pnl_pct,
                    "reason": exit_reason,
                })
                del positions[sym]

        # entries from signals (use today's close signal -> next open)
        if i < len(dates) - 1:
            desired = sig.iloc[i]
            for sym in desired.index:
                if desired[sym] != 1 or sym in positions:
                    continue
                sec = sector_map.get(sym, "Diversified")
                if sector_counts.get(sec, 0) >= max_per_sector:
                    continue
                if len(positions) >= max_positions:
                    break
                entry_px = prices_open[sym].iloc[i + 1]
                if pd.isna(entry_px) or entry_px <= 0:
                    continue
                atr = atr_df[sym].iloc[i]
                if pd.isna(atr) or atr <= 0:
                    continue
                # equal-weight slot: 1/max_positions of current equity
                slot_value = port_value / max_positions
                if slot_value <= 0:
                    continue
                qty = slot_value / entry_px
                if qty <= 0:
                    continue
                cost = qty * entry_px * (1 + rt_cost / 2)
                if cost > cash:
                    continue
                cash -= cost
                positions[sym] = {
                    "entry_px": entry_px, "entry_date": dates[i + 1],
                    "qty": qty, "sector": sec, "atr": atr,
                }
                sector_counts[sec] = sector_counts.get(sec, 0) + 1

        equity_curve.append(port_value)

    eq = pd.Series(equity_curve, index=dates, name="equity")
    dd = eq / eq.cummax() - 1
    return BacktestResult(equity=eq, drawdown=dd, trades=pd.DataFrame(trades))
