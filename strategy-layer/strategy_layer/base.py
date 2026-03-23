"""
Base classes and data models for the strategy layer.
All strategy plugins must inherit BaseStrategy.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar

import structlog
from pydantic import BaseModel, field_validator

log = structlog.get_logger()


class SignalDirection(str, Enum):
    LONG  = "long"
    SHORT = "short"
    EXIT  = "exit"
    HOLD  = "hold"


@dataclass(frozen=True, slots=True)
class Tick:
    symbol:       str
    timestamp_ns: int
    bid:          Decimal
    ask:          Decimal
    last:         Decimal
    bid_size:     Decimal
    ask_size:     Decimal
    volume_24h:   Decimal

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / 2

    @property
    def spread_bps(self) -> Decimal:
        return (self.ask - self.bid) / self.mid * 10000 if self.mid else Decimal(0)

    @classmethod
    def from_redis(cls, fields: dict) -> "Tick":
        d = fields if isinstance(fields, dict) else {}
        return cls(
            symbol       = d.get("sym", "UNKNOWN"),
            timestamp_ns = int(d.get("timestamp_ns", 0)),
            bid          = Decimal(d.get("bid", "0")),
            ask          = Decimal(d.get("ask", "0")),
            last         = Decimal(d.get("last", "0")),
            bid_size     = Decimal(d.get("bid_size", "0")),
            ask_size     = Decimal(d.get("ask_size", "0")),
            volume_24h   = Decimal(d.get("volume_24h", "0")),
        )


@dataclass
class Signal:
    signal_id:    str          = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id:  str          = ""
    symbol:       str          = ""
    direction:    SignalDirection = SignalDirection.HOLD
    strength:     float        = 0.0
    confidence:   float        = 0.0
    target_price: Decimal | None = None
    target_size:  Decimal | None = None
    stop_loss:    Decimal | None = None
    take_profit:  Decimal | None = None
    timestamp_ns: int  = field(default_factory=time.time_ns)
    ttl_ms:       int  = 5000
    reason:       str  = ""

    @property
    def is_expired(self) -> bool:
        return (time.time_ns() - self.timestamp_ns) / 1_000_000 > self.ttl_ms

    def to_dict(self) -> dict:
        return {
            "signal_id":   self.signal_id,
            "strategy_id": self.strategy_id,
            "symbol":      self.symbol,
            "direction":   self.direction.value,
            "strength":    self.strength,
            "confidence":  self.confidence,
            "target_price": str(self.target_price) if self.target_price else None,
            "stop_loss":   str(self.stop_loss)    if self.stop_loss    else None,
            "take_profit": str(self.take_profit)  if self.take_profit  else None,
            "timestamp_ns": self.timestamp_ns,
            "ttl_ms":       self.ttl_ms,
            "reason":       self.reason,
        }


@dataclass
class OrderEvent:
    class Kind(str, Enum):
        FILLED         = "filled"
        PARTIAL_FILLED = "partial_filled"
        CANCELLED      = "cancelled"
        REJECTED       = "rejected"

    order_id:   str
    signal_id:  str
    symbol:     str
    kind:       "OrderEvent.Kind"
    filled_qty: Decimal
    filled_px:  Decimal
    timestamp:  int


@dataclass
class StrategyState:
    position:    Decimal = Decimal("0")
    entry_price: Decimal | None = None
    pnl:         Decimal = Decimal("0")
    trade_count: int = 0
    extra:       dict = field(default_factory=dict)


class StrategyParams(BaseModel):
    model_config = {"frozen": True}

    symbols:             list[str]
    position_limit:      Decimal = Decimal("1.0")
    min_signal_strength: float   = 0.3

    @field_validator("symbols")
    @classmethod
    def symbols_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("symbols list cannot be empty")
        return [s.upper() for s in v]


class BaseStrategy(ABC):
    """
    Abstract base class for all strategy plugins.
    Framework handles: logging, lifecycle, param validation, timing.
    Strategy handles: signal generation, order event processing.
    """
    STRATEGY_ID:   ClassVar[str]
    STRATEGY_NAME: ClassVar[str]

    def __init__(self, params: StrategyParams) -> None:
        self.params  = params
        self.state   = StrategyState()
        self._active = False
        self.log     = log.bind(strategy=self.STRATEGY_ID)

    @classmethod
    @abstractmethod
    def get_params_schema(cls) -> type[StrategyParams]: ...

    @abstractmethod
    def on_tick(self, tick: Tick) -> list[Signal]: ...

    @abstractmethod
    def on_order_event(self, event: OrderEvent) -> None: ...

    def export_state(self) -> dict:
        return {
            "position":    str(self.state.position),
            "entry_price": str(self.state.entry_price) if self.state.entry_price else None,
            "pnl":         str(self.state.pnl),
            "trade_count": self.state.trade_count,
            "extra":       self.state.extra,
        }

    def import_state(self, state_dict: dict) -> None:
        self.state.position    = Decimal(state_dict.get("position", "0"))
        ep = state_dict.get("entry_price")
        self.state.entry_price = Decimal(ep) if ep else None
        self.state.pnl         = Decimal(state_dict.get("pnl", "0"))
        self.state.trade_count = int(state_dict.get("trade_count", 0))
        self.state.extra       = state_dict.get("extra", {})

    async def on_start(self) -> None: pass
    async def on_stop(self)  -> None: pass

    async def start(self) -> None:
        self._active = True
        self.log.info("started", symbols=self.params.symbols)
        await self.on_start()

    async def stop(self) -> None:
        self._active = False
        await self.on_stop()
        self.log.info("stopped", pnl=str(self.state.pnl))

    def process_tick(self, tick: Tick) -> list[Signal]:
        if not self._active or tick.symbol not in self.params.symbols:
            return []
        t0 = time.perf_counter_ns()
        try:
            signals = self.on_tick(tick)
        except Exception:
            self.log.exception("on_tick_error", symbol=tick.symbol)
            return []
        finally:
            us = (time.perf_counter_ns() - t0) / 1000
            if us > 1000:
                self.log.warning("slow_on_tick", us=us)
        out = []
        for sig in signals:
            sig.strategy_id = self.STRATEGY_ID
            if abs(sig.strength) >= self.params.min_signal_strength:
                out.append(sig)
        return out
