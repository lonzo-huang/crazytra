"""
Strategy layer entrypoint.
Consumes ticks from Redis Streams, runs strategies, publishes signals.
"""
from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal
from pathlib import Path

import redis.asyncio as aioredis
import structlog
from dotenv import load_dotenv

from strategy_layer.base import Tick
from strategy_layer.combinator import CombineMode, SignalCombinator, StrategyWeight
from strategy_layer.runner import StrategyRunner

load_dotenv()
log = structlog.get_logger()

REDIS_URL    = os.getenv("REDIS_URL", "redis://localhost:6379")
TICK_TOPIC   = "market.tick.binance.*"
WEIGHT_TOPIC = "llm.weight"
SIGNAL_TOPIC = "strategy.signal"


async def llm_weight_listener(redis, combinator: SignalCombinator) -> None:
    """Background task: consume llm.weight and update combinator."""
    group = "strategy-llm-cg"
    try:
        await redis.xgroup_create(WEIGHT_TOPIC, group, id="$", mkstream=True)
    except Exception:
        pass
    while True:
        try:
            entries = await redis.xreadgroup(
                groupname=group, consumername="strategy-1",
                streams={WEIGHT_TOPIC: ">"}, count=10, block=1000,
            )
            for _, msgs in (entries or []):
                ack_ids = []
                for mid, fields in msgs:
                    try:
                        data = json.loads(fields.get("data", "{}"))
                        sym  = data.get("symbol", "")
                        sc   = float(data.get("llm_score", 0)) * float(data.get("confidence", 1))
                        if sym:
                            await combinator.update_llm_weights(sym, sc)
                    except Exception:
                        pass
                    ack_ids.append(mid)
                if ack_ids:
                    await redis.xack(WEIGHT_TOPIC, group, *ack_ids)
        except Exception as e:
            log.warning("llm_weight_error", err=str(e))
            await asyncio.sleep(2)


async def tick_consumer(redis, runner: StrategyRunner) -> None:
    """Consume tick data from all Binance market topics."""
    group = "strategy-tick-cg"
    topics = [f"market.tick.binance.btcusdt", f"market.tick.binance.ethusdt"]
    for t in topics:
        try:
            await redis.xgroup_create(t, group, id="$", mkstream=True)
        except Exception:
            pass

    while True:
        try:
            entries = await redis.xreadgroup(
                groupname=group, consumername="strategy-1",
                streams={t: ">" for t in topics},
                count=50, block=100,
            )
            for stream, msgs in (entries or []):
                ack_ids = []
                for mid, fields in msgs:
                    try:
                        raw = json.loads(fields.get("data", "{}"))
                        tick = Tick(
                            symbol       = raw.get("symbol", ""),
                            timestamp_ns = int(raw.get("timestamp_ns", 0)),
                            bid          = Decimal(raw.get("bid", "0")),
                            ask          = Decimal(raw.get("ask", "0")),
                            last         = Decimal(raw.get("last", "0")),
                            bid_size     = Decimal(raw.get("bid_size", "0")),
                            ask_size     = Decimal(raw.get("ask_size", "0")),
                            volume_24h   = Decimal(raw.get("volume_24h", "0")),
                        )
                        await runner.dispatch_tick(tick)
                    except Exception:
                        log.exception("tick_dispatch_error")
                    ack_ids.append(mid)
                if ack_ids:
                    await redis.xack(stream, group, *ack_ids)
        except Exception as e:
            log.warning("tick_consumer_error", err=str(e))
            await asyncio.sleep(0.1)


async def main() -> None:
    structlog.configure(processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ])
    log.info("strategy_layer_starting")

    redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    combinator = SignalCombinator(mode=CombineMode.WEIGHTED_SUM)
    combinator.configure("BTC-USDT", weights=[
        StrategyWeight("ma_cross_v1",       base_weight=1.0),
        StrategyWeight("mean_reversion_v1", base_weight=0.7),
    ])
    combinator.configure("ETH-USDT", weights=[
        StrategyWeight("ma_cross_v1",       base_weight=0.8),
        StrategyWeight("mean_reversion_v1", base_weight=0.9),
    ])

    runner = StrategyRunner(
        plugin_dir = Path(__file__).parent / "strategies",
        combinator = combinator,
    )
    await runner.start()

    await runner.add_strategy("ma_cross_v1", {
        "symbols": ["BTC-USDT", "ETH-USDT"],
        "fast_period": 10, "slow_period": 30,
    })
    await runner.add_strategy("mean_reversion_v1", {
        "symbols": ["BTC-USDT", "ETH-USDT"],
        "lookback": 20, "z_entry": 2.0,
    })

    log.info("strategies_loaded", active=list(runner._strategies))

    await asyncio.gather(
        tick_consumer(redis, runner),
        llm_weight_listener(redis, combinator),
    )


if __name__ == "__main__":
    asyncio.run(main())
