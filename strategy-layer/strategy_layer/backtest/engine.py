"""
Event-driven backtest engine.
Replays historical tick data through strategy code identical to live trading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

from strategy_layer.base import BaseStrategy, OrderEvent, Signal, SignalDirection, Tick

log = structlog.get_logger()


@dataclass
class BacktestConfig:
    start:         str             # "2024-01-01"
    end:           str             # "2024-12-31"
    initial_cash:  Decimal         = Decimal("100000")
    maker_fee:     Decimal         = Decimal("0.0002")
    taker_fee:     Decimal         = Decimal("0.0005")
    slippage_bps:  Decimal         = Decimal("1.0")
    fill_at:       str             = "next_open"   # signal_price | next_open
    max_position_frac: Decimal     = Decimal("0.2") # max 20% per symbol


@dataclass
class Trade:
    symbol:    str
    direction: str
    qty:       Decimal
    entry_px:  Decimal
    exit_px:   Decimal = Decimal("0")
    pnl:       Decimal = Decimal("0")
    fee:       Decimal = Decimal("0")


@dataclass
class BacktestResult:
    equity_curve:   pd.Series
    trades:         pd.DataFrame
    total_return:   float = 0.0
    annual_return:  float = 0.0
    sharpe_ratio:   float = 0.0
    sortino_ratio:  float = 0.0
    max_drawdown:   float = 0.0
    calmar_ratio:   float = 0.0
    win_rate:       float = 0.0
    profit_factor:  float = 0.0
    total_trades:   int   = 0
    avg_trade_pnl:  float = 0.0


class SimulatedBroker:
    def __init__(self, cfg: BacktestConfig) -> None:
        self.cfg       = cfg
        self.cash      = cfg.initial_cash
        self.positions: dict[str, Decimal] = {}
        self.avg_entry: dict[str, Decimal] = {}
        self.trades:    list[Trade]        = []

    def execute(self, signal: Signal, tick: Tick, next_tick: Tick | None) -> OrderEvent | None:
        sym = signal.symbol

        # Determine fill price
        if self.cfg.fill_at == "next_open" and next_tick:
            raw = next_tick.ask if signal.direction == SignalDirection.LONG else next_tick.bid
        else:
            raw = tick.ask if signal.direction == SignalDirection.LONG else tick.bid

        slip = raw * self.cfg.slippage_bps / Decimal("10000")
        fill_px = raw + slip if signal.direction == SignalDirection.LONG else raw - slip

        pos = self.positions.get(sym, Decimal("0"))

        if signal.direction == SignalDirection.LONG:
            notional = self.cash * Decimal(str(signal.strength)) * self.cfg.max_position_frac
            qty = (notional / fill_px).quantize(Decimal("0.00001"))
            fee = qty * fill_px * self.cfg.taker_fee
            cost = qty * fill_px + fee
            if cost > self.cash:
                qty = (self.cash * Decimal("0.99") /
                       (fill_px * (1 + self.cfg.taker_fee))).quantize(Decimal("0.00001"))
                if qty <= 0:
                    return None
                fee  = qty * fill_px * self.cfg.taker_fee
                cost = qty * fill_px + fee
            self.cash -= cost
            prev_pos = self.positions.get(sym, Decimal("0"))
            prev_entry = self.avg_entry.get(sym, Decimal("0"))
            new_pos = prev_pos + qty
            if new_pos > 0:
                self.avg_entry[sym] = (prev_pos * prev_entry + qty * fill_px) / new_pos
            self.positions[sym] = new_pos

        elif signal.direction in (SignalDirection.SHORT, SignalDirection.EXIT):
            if pos <= 0:
                return None
            qty = min(pos, pos)  # close full position on exit
            revenue = qty * fill_px
            fee     = revenue * self.cfg.taker_fee
            pnl     = (fill_px - self.avg_entry.get(sym, fill_px)) * qty - fee
            self.cash += revenue - fee
            self.positions[sym] = Decimal("0")
            self.trades.append(Trade(
                symbol=sym, direction="long→exit",
                qty=qty, entry_px=self.avg_entry.get(sym, fill_px),
                exit_px=fill_px, pnl=pnl, fee=fee,
            ))
        else:
            return None

        return OrderEvent(
            order_id   = signal.signal_id,
            signal_id  = signal.signal_id,
            symbol     = sym,
            kind       = OrderEvent.Kind.FILLED,
            filled_qty = qty if "qty" in dir() else Decimal("0"),
            filled_px  = fill_px,
            timestamp  = tick.timestamp_ns,
        )

    def portfolio_value(self, prices: dict[str, Decimal]) -> Decimal:
        nav = self.cash
        for sym, qty in self.positions.items():
            nav += qty * prices.get(sym, Decimal("0"))
        return nav


class BacktestEngine:
    """Run strategy code against historical data and compute performance metrics."""

    def __init__(self, strategy: BaseStrategy, config: BacktestConfig) -> None:
        self.strategy = strategy
        self.config   = config
        self.broker   = SimulatedBroker(config)

    async def run(self, data_path: Path) -> BacktestResult:
        log.info("backtest_start", file=str(data_path),
                 start=self.config.start, end=self.config.end)
        df = pd.read_parquet(data_path)
        df = (df[(df["time"] >= self.config.start) & (df["time"] <= self.config.end)]
              .sort_values("time").reset_index(drop=True))

        ticks = self._to_ticks(df)
        equity_pts: list[dict] = []

        await self.strategy.start()

        for i, tick in enumerate(ticks):
            next_tick = ticks[i + 1] if i + 1 < len(ticks) else None
            signals   = self.strategy.process_tick(tick)
            for sig in signals:
                event = self.broker.execute(sig, tick, next_tick)
                if event:
                    self.strategy.on_order_event(event)
            if i % 60 == 0:
                prices = {tick.symbol: tick.mid}
                nav    = self.broker.portfolio_value(prices)
                equity_pts.append({
                    "ts": pd.Timestamp(tick.timestamp_ns, unit="ns"),
                    "nav": float(nav),
                })

        await self.strategy.stop()

        equity = pd.Series(
            [p["nav"] for p in equity_pts],
            index=[p["ts"] for p in equity_pts],
            name="equity",
        )
        trades_df = pd.DataFrame([t.__dict__ for t in self.broker.trades])
        result = self._metrics(equity, trades_df)
        self._print(result)
        return result

    def _to_ticks(self, df: pd.DataFrame) -> list[Tick]:
        out = []
        for row in df.itertuples(index=False):
            out.append(Tick(
                symbol       = str(row.symbol),
                timestamp_ns = int(pd.Timestamp(row.time).value),
                bid          = Decimal(str(row.bid)),
                ask          = Decimal(str(row.ask)),
                last         = Decimal(str(getattr(row, "last", row.ask))),
                bid_size     = Decimal(str(getattr(row, "bid_size", "0"))),
                ask_size     = Decimal(str(getattr(row, "ask_size", "0"))),
                volume_24h   = Decimal(str(getattr(row, "volume_24h", "0"))),
            ))
        return out

    def _metrics(self, equity: pd.Series, trades: pd.DataFrame) -> BacktestResult:
        if equity.empty:
            return BacktestResult(equity_curve=equity, trades=trades)

        rets       = equity.pct_change().dropna()
        total_ret  = (equity.iloc[-1] / equity.iloc[0]) - 1.0
        n_years    = max(len(equity) / (365 * 24 * 60), 1e-6)
        annual_ret = (1 + total_ret) ** (1 / n_years) - 1

        rf         = 0.04 / 365
        excess     = rets - rf
        sharpe     = float(excess.mean() / excess.std() * np.sqrt(365)) if excess.std() > 0 else 0
        down_std   = rets[rets < 0].std()
        sortino    = float(excess.mean() / down_std * np.sqrt(365)) if down_std > 0 else 0

        roll_max   = equity.cummax()
        drawdown   = (equity - roll_max) / roll_max
        mdd        = float(drawdown.min())
        calmar     = annual_ret / abs(mdd) if mdd else 0

        win_rate = profit_factor = avg_pnl = 0.0
        if not trades.empty and "pnl" in trades.columns:
            wins   = trades[trades["pnl"] > 0]
            losses = trades[trades["pnl"] < 0]
            win_rate      = len(wins) / len(trades) if len(trades) else 0
            gross_profit  = float(wins["pnl"].sum()) if not wins.empty else 0
            gross_loss    = abs(float(losses["pnl"].sum())) if not losses.empty else 1e-9
            profit_factor = gross_profit / gross_loss
            avg_pnl       = float(trades["pnl"].mean())

        return BacktestResult(
            equity_curve  = equity,
            trades        = trades,
            total_return  = float(total_ret),
            annual_return = float(annual_ret),
            sharpe_ratio  = sharpe,
            sortino_ratio = sortino,
            max_drawdown  = mdd,
            calmar_ratio  = calmar,
            win_rate      = win_rate,
            profit_factor = profit_factor,
            total_trades  = len(trades),
            avg_trade_pnl = avg_pnl,
        )

    def _print(self, r: BacktestResult) -> None:
        log.info("backtest_result",
                 total_return  = f"{r.total_return:.2%}",
                 annual_return = f"{r.annual_return:.2%}",
                 sharpe        = f"{r.sharpe_ratio:.2f}",
                 sortino       = f"{r.sortino_ratio:.2f}",
                 max_drawdown  = f"{r.max_drawdown:.2%}",
                 calmar        = f"{r.calmar_ratio:.2f}",
                 win_rate      = f"{r.win_rate:.2%}",
                 profit_factor = f"{r.profit_factor:.2f}",
                 total_trades  = r.total_trades)
