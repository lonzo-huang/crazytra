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


class MACrossParams(StrategyParams):
    fast_period:    int   = Field(default=10,  ge=2,  le=200)
    slow_period:    int   = Field(default=30,  ge=5,  le=500)
    atr_period:     int   = Field(default=14,  ge=5,  le=100)
    atr_multiplier: float = Field(default=2.0, gt=0)

    def model_post_init(self, __context):
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be < slow_period")


@register
class MACrossStrategy(BaseStrategy):
    STRATEGY_ID   = "ma_cross_v1"
    STRATEGY_NAME = "均线交叉策略"

    def __init__(self, params: MACrossParams) -> None:
        super().__init__(params)
        self.p = params
        maxlen = params.slow_period + params.atr_period + 10
        self._prices: dict[str, deque] = {}
        self._highs:  dict[str, deque] = {}
        self._lows:   dict[str, deque] = {}
        self._prev_cross: dict[str, str] = {}

    @classmethod
    def get_params_schema(cls) -> type[MACrossParams]:
        return MACrossParams

    def _ensure(self, sym: str) -> None:
        if sym not in self._prices:
            n = self.p.slow_period + self.p.atr_period + 10
            self._prices[sym] = deque(maxlen=n)
            self._highs[sym]  = deque(maxlen=n)
            self._lows[sym]   = deque(maxlen=n)
            self._prev_cross[sym] = ""

    def on_tick(self, tick: Tick) -> list[Signal]:
        self._ensure(tick.symbol)
        mid = float(tick.mid)
        self._prices[tick.symbol].append(mid)
        self._highs[tick.symbol].append(float(tick.ask))
        self._lows[tick.symbol].append(float(tick.bid))

        prices = np.array(self._prices[tick.symbol])
        if len(prices) < self.p.slow_period:
            return []

        fast_ma = float(np.mean(prices[-self.p.fast_period:]))
        slow_ma = float(np.mean(prices[-self.p.slow_period:]))
        atr     = self._calc_atr(tick.symbol)
        if atr == 0:
            return []

        cross = "golden" if fast_ma > slow_ma else "death"
        prev  = self._prev_cross[tick.symbol]
        self._prev_cross[tick.symbol] = cross

        signals = []
        if cross == "golden" and prev != "golden":
            gap_atr  = (fast_ma - slow_ma) / atr
            strength = min(gap_atr / 2.0, 1.0)
            signals.append(Signal(
                symbol    = tick.symbol,
                direction = SignalDirection.LONG,
                strength  = strength,
                confidence= self._confidence(prices),
                stop_loss = Decimal(str(round(mid - atr * self.p.atr_multiplier, 6))),
                reason    = f"golden_cross fast={fast_ma:.4f} slow={slow_ma:.4f}",
                ttl_ms    = 10_000,
            ))
        elif cross == "death" and prev == "golden":
            signals.append(Signal(
                symbol    = tick.symbol,
                direction = SignalDirection.EXIT,
                strength  = 1.0,
                confidence= 0.9,
                reason    = "death_cross",
            ))
        return signals

    def _calc_atr(self, sym: str) -> float:
        h = np.array(self._highs[sym])
        l = np.array(self._lows[sym])
        c = np.array(self._prices[sym])
        n = min(self.p.atr_period, len(c) - 1)
        if n < 2:
            return 0.0
        tr = np.maximum(h[-n:] - l[-n:],
             np.maximum(np.abs(h[-n:] - c[-(n+1):-1]),
                        np.abs(l[-n:] - c[-(n+1):-1])))
        return float(np.mean(tr))

    def _confidence(self, prices: np.ndarray) -> float:
        n = min(self.p.slow_period, len(prices))
        x = np.arange(n); y = prices[-n:]
        slope, intercept = np.polyfit(x, y, 1)
        y_hat  = slope * x + intercept
        ss_res = np.sum((y - y_hat) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    def on_order_event(self, event: OrderEvent) -> None:
        if event.kind == OrderEvent.Kind.FILLED:
            self.state.trade_count += 1
            self.state.position    += event.filled_qty
            self.state.entry_price  = event.filled_px
