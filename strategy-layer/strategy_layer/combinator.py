from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum

import structlog

from .base import Signal, SignalDirection

log = structlog.get_logger()


class CombineMode(str, Enum):
    WEIGHTED_SUM  = "weighted_sum"
    MAJORITY_VOTE = "majority_vote"
    UNANIMOUS     = "unanimous"
    VETO          = "veto"


@dataclass
class StrategyWeight:
    strategy_id:        str
    base_weight:        float = 1.0
    llm_factor:         float = 1.0
    performance_factor: float = 1.0

    @property
    def effective(self) -> float:
        return self.base_weight * self.llm_factor * self.performance_factor


@dataclass
class CombinedSignal:
    symbol:       str
    direction:    SignalDirection
    strength:     float
    confidence:   float
    contributors: list[str]
    timestamp_ns: int = field(default_factory=time.time_ns)


class SignalCombinator:
    def __init__(self, mode: CombineMode = CombineMode.WEIGHTED_SUM,
                 conflict_threshold: float = 0.3) -> None:
        self.mode               = mode
        self.conflict_threshold = conflict_threshold
        self._weights:  dict[str, list[StrategyWeight]] = {}
        self._buffer:   dict[str, list[Signal]]         = {}
        self._lock = asyncio.Lock()

    def configure(self, symbol: str, weights: list[StrategyWeight]) -> None:
        self._weights[symbol] = weights
        self._buffer[symbol]  = []

    async def update_llm_weights(self, symbol: str, llm_score: float) -> None:
        """Called by LLM weight consumer on every new weight message."""
        async with self._lock:
            for w in self._weights.get(symbol, []):
                # Map [-1,1] → [0.5, 2.0]
                w.llm_factor = max(0.5, min(2.0, 1.0 + llm_score * 0.5))
        log.debug("llm_weight_applied", symbol=symbol, score=llm_score)

    async def ingest(self, signal: Signal) -> None:
        async with self._lock:
            buf = self._buffer.setdefault(signal.symbol, [])
            buf[:] = [s for s in buf if s.strategy_id != signal.strategy_id]
            buf.append(signal)

    async def combine(self, symbol: str) -> CombinedSignal | None:
        async with self._lock:
            signals = [s for s in self._buffer.get(symbol, []) if not s.is_expired]
            weights = self._weights.get(symbol, [])

        if not signals:
            return None

        match self.mode:
            case CombineMode.WEIGHTED_SUM:  return self._weighted_sum(symbol, signals, weights)
            case CombineMode.MAJORITY_VOTE: return self._majority_vote(symbol, signals, weights)
            case CombineMode.UNANIMOUS:     return self._unanimous(symbol, signals)
            case CombineMode.VETO:          return self._veto(symbol, signals, weights)

    def _weighted_sum(self, symbol, signals, weights) -> CombinedSignal | None:
        wmap = {w.strategy_id: w.effective for w in weights}
        total_w = weighted_sum = weighted_conf = 0.0
        contributors = []
        for sig in signals:
            w = wmap.get(sig.strategy_id, 1.0)
            num = {SignalDirection.LONG: sig.strength, SignalDirection.SHORT: -sig.strength,
                   SignalDirection.EXIT: 0.0, SignalDirection.HOLD: 0.0}[sig.direction]
            weighted_sum  += num * w * sig.confidence
            weighted_conf += sig.confidence * w
            total_w       += w
            contributors.append(sig.strategy_id)
        if not total_w:
            return None
        net  = weighted_sum / total_w
        conf = weighted_conf / total_w
        if abs(net) < self.conflict_threshold:
            return CombinedSignal(symbol, SignalDirection.HOLD, 0.0, conf, contributors)
        return CombinedSignal(symbol,
            SignalDirection.LONG if net > 0 else SignalDirection.SHORT,
            abs(net), conf, contributors)

    def _majority_vote(self, symbol, signals, weights) -> CombinedSignal | None:
        wmap  = {w.strategy_id: w.effective for w in weights}
        long_w  = sum(wmap.get(s.strategy_id, 1.0) for s in signals if s.direction == SignalDirection.LONG)
        short_w = sum(wmap.get(s.strategy_id, 1.0) for s in signals if s.direction == SignalDirection.SHORT)
        exit_w  = sum(wmap.get(s.strategy_id, 1.0) for s in signals if s.direction == SignalDirection.EXIT)
        total   = long_w + short_w + exit_w or 1.0
        if long_w >= short_w and long_w >= exit_w:
            d, s = SignalDirection.LONG, long_w / total
        elif short_w >= long_w and short_w >= exit_w:
            d, s = SignalDirection.SHORT, short_w / total
        else:
            d, s = SignalDirection.EXIT, exit_w / total
        conf = sum(x.confidence for x in signals) / len(signals)
        return CombinedSignal(symbol, d, s, conf, [x.strategy_id for x in signals])

    def _unanimous(self, symbol, signals) -> CombinedSignal | None:
        dirs = {s.direction for s in signals if s.direction not in (SignalDirection.HOLD,)}
        if len(dirs) != 1:
            return None
        d = dirs.pop()
        return CombinedSignal(symbol, d,
            sum(s.strength for s in signals) / len(signals),
            sum(s.confidence for s in signals) / len(signals),
            [s.strategy_id for s in signals])

    def _veto(self, symbol, signals, weights) -> CombinedSignal | None:
        if any(s.direction == SignalDirection.SHORT for s in signals):
            ss = [s for s in signals if s.direction == SignalDirection.SHORT]
            return CombinedSignal(symbol, SignalDirection.SHORT,
                sum(s.strength for s in ss) / len(ss), 1.0,
                [s.strategy_id for s in ss])
        return self._weighted_sum(symbol, signals, weights)
