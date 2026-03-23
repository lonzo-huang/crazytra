"""
RedisBridgeActor - Nautilus 事件到 Redis Streams 的桥接
遵循 SYSTEM_SPEC.md 第 13.3 节规范

职责：
1. 订阅 Nautilus 的所有 tick 事件
2. 订阅 Nautilus 的订单事件
3. 将事件转换为与自建数据层完全相同的 JSON 格式
4. 写入 Redis Streams，确保前端和 API 网关代码零修改
"""
import asyncio
import json
from decimal import Decimal
from typing import Any

import redis.asyncio as aioredis
from nautilus_trader.common.actor import Actor
from nautilus_trader.core.data import Data
from nautilus_trader.model.data import QuoteTick, TradeTick
from nautilus_trader.model.events import OrderFilled, OrderEvent
from nautilus_trader.model.identifiers import InstrumentId


class RedisBridgeActor(Actor):
    """
    Nautilus 到 Redis 的桥接 Actor
    
    关键设计：
    - 所有 Redis 操作使用 asyncio.create_task()（不阻塞 Nautilus 主循环）
    - 消息格式必须与 SYSTEM_SPEC.md 第 4.5 节完全一致
    - 错误处理：捕获所有异常，记录警告，不向上抛出
    """
    
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._redis: aioredis.Redis | None = None
        self._redis_url = config.get("redis_url", "redis://localhost:6379") if config else "redis://localhost:6379"
        self._maxlen = config.get("maxlen", 50000) if config else 50000
        
    async def on_start(self) -> None:
        """Actor 启动时建立 Redis 连接"""
        try:
            self._redis = await aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            self.log.info(f"RedisBridgeActor connected to Redis at {self._redis_url}")
            
            # 订阅所有 quote ticks（实时行情）
            self.subscribe_quote_ticks(instrument_id=None)  # None = 订阅所有
            
            # 订阅所有 trade ticks
            self.subscribe_trade_ticks(instrument_id=None)
            
            # 订阅所有订单事件
            self.subscribe_order_events()
            
        except Exception as e:
            self.log.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def on_stop(self) -> None:
        """Actor 停止时关闭 Redis 连接"""
        if self._redis:
            await self._redis.close()
            self.log.info("RedisBridgeActor disconnected from Redis")
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        """
        处理 quote tick 事件
        
        关键：必须与 SYSTEM_SPEC.md 第 4.5 节的 JSON 格式完全一致
        """
        # 异步发布，不阻塞主循环
        asyncio.create_task(self._publish_quote_tick(tick))
    
    def on_trade_tick(self, tick: TradeTick) -> None:
        """处理 trade tick 事件"""
        asyncio.create_task(self._publish_trade_tick(tick))
    
    def on_event(self, event: Data) -> None:
        """处理订单事件"""
        if isinstance(event, OrderEvent):
            asyncio.create_task(self._publish_order_event(event))
    
    async def _publish_quote_tick(self, tick: QuoteTick) -> None:
        """
        发布 quote tick 到 Redis
        
        格式必须与自建数据层完全一致（SYSTEM_SPEC.md 4.5）
        """
        if not self._redis:
            return
        
        try:
            # 转换 Nautilus 标的 ID 格式
            # Nautilus: BTCUSDT.BINANCE → 我们的格式: BTC-USDT
            symbol = self._convert_symbol(tick.instrument_id)
            exchange = tick.instrument_id.venue.value.lower()
            
            # 构建与自建数据层完全相同的 JSON
            payload = {
                "symbol": symbol,
                "exchange": exchange,
                "timestamp_ns": tick.ts_event,
                "received_ns": tick.ts_init,
                "bid": str(tick.bid_price),  # 必须字符串
                "ask": str(tick.ask_price),
                "bid_size": str(tick.bid_size),
                "ask_size": str(tick.ask_size),
                "last": str((tick.bid_price + tick.ask_price) / 2),  # 中间价
                "volume_24h": "0",  # QuoteTick 不含成交量
                "latency_us": (tick.ts_init - tick.ts_event) // 1000,
            }
            
            # Redis Stream topic: market.tick.{exchange}.{symbol_lower}
            # 例如: market.tick.binance.btcusdt
            topic = f"market.tick.{exchange}.{symbol.lower().replace('-', '')}"
            
            # 写入 Redis Stream
            await self._redis.xadd(
                topic,
                fields={
                    "data": json.dumps(payload),
                    "sym": symbol,
                },
                maxlen=self._maxlen,
                approximate=True,  # 使用近似裁剪（性能优化）
            )
            
            self.log.debug(f"Published tick to {topic}: {symbol}")
            
        except Exception as e:
            # 捕获所有异常，不影响 Nautilus 主进程
            self.log.warning(f"Failed to publish quote tick: {e}")
    
    async def _publish_trade_tick(self, tick: TradeTick) -> None:
        """发布 trade tick 到 Redis"""
        if not self._redis:
            return
        
        try:
            symbol = self._convert_symbol(tick.instrument_id)
            exchange = tick.instrument_id.venue.value.lower()
            
            payload = {
                "symbol": symbol,
                "exchange": exchange,
                "timestamp_ns": tick.ts_event,
                "received_ns": tick.ts_init,
                "price": str(tick.price),
                "size": str(tick.size),
                "side": tick.aggressor_side.name.lower(),
                "trade_id": tick.trade_id.value,
            }
            
            topic = f"market.trade.{exchange}.{symbol.lower().replace('-', '')}"
            
            await self._redis.xadd(
                topic,
                fields={"data": json.dumps(payload)},
                maxlen=10000,
                approximate=True,
            )
            
        except Exception as e:
            self.log.warning(f"Failed to publish trade tick: {e}")
    
    async def _publish_order_event(self, event: OrderEvent) -> None:
        """
        发布订单事件到 Redis
        
        格式必须与 Go 交易层输出的 OrderEvent 一致
        """
        if not self._redis:
            return
        
        try:
            # 构建订单事件 JSON
            payload = {
                "event_id": event.event_id.value,
                "order_id": event.client_order_id.value,
                "symbol": self._convert_symbol(event.instrument_id),
                "kind": self._map_order_status(event),
                "timestamp": event.ts_event,
                "mode": "live" if hasattr(event, "venue_order_id") else "paper",
            }
            
            # 如果是成交事件，添加成交信息
            if isinstance(event, OrderFilled):
                payload.update({
                    "filled_qty": str(event.last_qty),
                    "filled_px": str(event.last_px),
                    "fee": str(event.commission.as_decimal()) if event.commission else "0",
                    "fee_asset": event.commission.currency.code if event.commission else "USDT",
                })
            
            # 写入 order.event stream
            await self._redis.xadd(
                "order.event",
                fields={
                    "data": json.dumps(payload),
                    "order_id": event.client_order_id.value,
                    "symbol": payload["symbol"],
                    "kind": payload["kind"],
                },
                maxlen=100000,
                approximate=True,
            )
            
            self.log.debug(f"Published order event: {event.client_order_id.value}")
            
        except Exception as e:
            self.log.warning(f"Failed to publish order event: {e}")
    
    def _convert_symbol(self, instrument_id: InstrumentId) -> str:
        """
        转换 Nautilus 标的 ID 为我们的格式
        
        Nautilus: BTCUSDT.BINANCE
        我们的格式: BTC-USDT
        """
        symbol_str = instrument_id.symbol.value
        
        # 处理常见格式
        if "USDT" in symbol_str:
            base = symbol_str.replace("USDT", "")
            return f"{base}-USDT"
        elif "USDC" in symbol_str:
            base = symbol_str.replace("USDC", "")
            return f"{base}-USDC"
        elif "USD" in symbol_str:
            base = symbol_str.replace("USD", "")
            return f"{base}-USD"
        else:
            # 其他格式保持原样
            return symbol_str
    
    def _map_order_status(self, event: OrderEvent) -> str:
        """映射 Nautilus 订单状态到我们的格式"""
        from nautilus_trader.model.events import (
            OrderAccepted,
            OrderCanceled,
            OrderFilled,
            OrderPartiallyFilled,
            OrderRejected,
            OrderSubmitted,
        )
        
        if isinstance(event, OrderSubmitted):
            return "submitted"
        elif isinstance(event, OrderAccepted):
            return "accepted"
        elif isinstance(event, OrderPartiallyFilled):
            return "partial_filled"
        elif isinstance(event, OrderFilled):
            return "filled"
        elif isinstance(event, OrderCanceled):
            return "cancelled"
        elif isinstance(event, OrderRejected):
            return "rejected"
        else:
            return "unknown"
