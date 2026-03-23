from __future__ import annotations

from collections import deque
from decimal import Decimal

import numpy as np
from pydantic import Field

from strategy_layer.base import (
    BaseStrategy, OrderEvent, Signal, SignalDirection,
    StrategyParams, Tick,
)
from strategy_layer.registry import register


class MeanReversionParams(StrategyParams):
    lookback:       int   = Field(default=20, ge=5, le=200)
    z_entry:        float = Field(default=2.0, gt=0)   # enter when |z| > this
    z_exit:         float = Field(default=0.5, gt=0)   # exit when |z| < this
    bb_multiplier:  float = Field(default=2.0, gt=0)   # Bollinger Band width


@register
class MeanReversionStrategy(BaseStrategy):
    STRATEGY_ID   = "mean_reversion_v1"
    STRATEGY_NAME = "均值回归策略"

    def __init__(self, params: MeanReversionParams) -> None:
        super().__init__(params)
        self.p = params
        self._prices: dict[str, deque] = {}
        self._in_trade: dict[str, str] = {}  # symbol → "long" | "short" | ""

    @classmethod
    def get_params_schema(cls) -> type[MeanReversionParams]:
        return MeanReversionParams

    def _ensure(self, sym: str) -> None:
        if sym not in self._prices:
            self._prices[sym]   = deque(maxlen=self.p.lookback + 5)
            self._in_trade[sym] = ""

    def on_tick(self, tick: Tick) -> list[Signal]:
        self._ensure(tick.symbol)
        mid = float(tick.mid)
        self._prices[tick.symbol].append(mid)

        arr = np.array(self._prices[tick.symbol])
        if len(arr) < self.p.lookback:
            return []

        mu  = float(np.mean(arr))
        std = float(np.std(arr))
        if std < 1e-10:
            return []

        z        = (mid - mu) / std
        in_trade = self._in_trade[tick.symbol]
        signals  = []

        # Entry: price deviates significantly from mean
        if abs(z) > self.p.z_entry and not in_trade:
            direction = SignalDirection.SHORT if z > 0 else SignalDirection.LONG
            self._in_trade[tick.symbol] = direction.value
            signals.append(Signal(
                symbol    = tick.symbol,
                direction = direction,
                strength  = min(abs(z) / (self.p.z_entry * 2), 1.0),
                confidence= 0.7,
                reason    = f"z_score={z:.2f} mu={mu:.4f} std={std:.4f}",
                ttl_ms    = 30_000,
            ))

        # Exit: price reverted to near mean
        elif in_trade and abs(z) < self.p.z_exit:
            self._in_trade[tick.symbol] = ""
            signals.append(Signal(
                symbol    = tick.symbol,
                direction = SignalDirection.EXIT,
                strength  = 1.0,
                confidence= 0.95,
                reason    = f"reversion_complete z={z:.2f}",
            ))

        return signals

    def on_order_event(self, event: OrderEvent) -> None:
        if event.kind in (OrderEvent.Kind.FILLED, OrderEvent.Kind.PARTIAL_FILLED):
            self.state.trade_count += 1
            self.state.position    += event.filled_qty
