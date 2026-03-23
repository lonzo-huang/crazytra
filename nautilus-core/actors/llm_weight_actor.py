"""
LLMWeightActor - 从 Redis 读取 LLM 权重并注入到 Nautilus 策略
遵循 SYSTEM_SPEC.md 第 7.4 节规范

职责：
1. 订阅 Redis llm.weight topic
2. 解析 LLM 权重消息
3. 调用策略的 update_llm_weight() 方法
4. 支持时间衰减融合（SYSTEM_SPEC.md 7.5）
"""
import asyncio
import json
import time
from decimal import Decimal
from typing import Any

import redis.asyncio as aioredis
from nautilus_trader.common.actor import Actor
from nautilus_trader.trading.strategy import Strategy


class LLMWeightActor(Actor):
    """
    LLM 权重注入 Actor
    
    从 Redis llm.weight topic 消费权重更新，并注入到所有策略实例
    """
    
    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._redis: aioredis.Redis | None = None
        self._redis_url = config.get("redis_url", "redis://localhost:6379") if config else "redis://localhost:6379"
        self._consumer_group = "nautilus-llm-cg"
        self._consumer_name = "llm-weight-actor-1"
        self._poll_task: asyncio.Task | None = None
        
        # 权重历史（用于时间衰减融合）
        self._weight_history: dict[str, list[dict]] = {}  # symbol -> [{score, conf, ts}, ...]
        self._half_life_s = config.get("half_life_s", 1800) if config else 1800  # 30分钟
        
    async def on_start(self) -> None:
        """启动时建立 Redis 连接并开始消费"""
        try:
            self._redis = await aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            self.log.info(f"LLMWeightActor connected to Redis at {self._redis_url}")
            
            # 创建消费者组（如果不存在）
            try:
                await self._redis.xgroup_create(
                    name="llm.weight",
                    groupname=self._consumer_group,
                    id="$",
                    mkstream=True,
                )
            except Exception:
                # 消费者组已存在
                pass
            
            # 启动轮询任务
            self._poll_task = asyncio.create_task(self._poll_loop())
            
        except Exception as e:
            self.log.error(f"Failed to start LLMWeightActor: {e}")
            raise
    
    async def on_stop(self) -> None:
        """停止时取消轮询任务并关闭连接"""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        
        if self._redis:
            await self._redis.close()
            self.log.info("LLMWeightActor disconnected from Redis")
    
    async def _poll_loop(self) -> None:
        """轮询 Redis Stream 消费 LLM 权重更新"""
        while True:
            try:
                # 从 llm.weight stream 读取消息
                entries = await self._redis.xreadgroup(
                    groupname=self._consumer_group,
                    consumername=self._consumer_name,
                    streams={"llm.weight": ">"},
                    count=10,
                    block=100,  # 100ms 阻塞
                )
                
                if not entries:
                    await asyncio.sleep(0.1)
                    continue
                
                # 处理消息
                ack_ids = []
                for stream_name, messages in entries:
                    for message_id, fields in messages:
                        try:
                            await self._process_weight_message(fields)
                            ack_ids.append(message_id)
                        except Exception as e:
                            self.log.warning(f"Failed to process weight message: {e}")
                            ack_ids.append(message_id)  # 仍然 ACK，避免重复处理
                
                # 批量 ACK
                if ack_ids:
                    await self._redis.xack("llm.weight", self._consumer_group, *ack_ids)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"Error in poll loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_weight_message(self, fields: dict) -> None:
        """
        处理 LLM 权重消息
        
        消息格式（SYSTEM_SPEC.md 7.4）:
        {
          "symbol": "BTC-USDT",
          "llm_score": 0.28,
          "confidence": 0.65,
          "horizon": "short",
          "key_drivers": [...],
          "risk_events": [...],
          "model_used": "...",
          "ts_ns": 1700000000000000000,
          "ttl_ms": 300000
        }
        """
        # 解析 JSON
        data_str = fields.get("data")
        if not data_str:
            return
        
        data = json.loads(data_str)
        
        symbol = data.get("symbol")
        llm_score = data.get("llm_score", 0.0)
        confidence = data.get("confidence", 0.0)
        ts_ns = data.get("ts_ns", time.time_ns())
        
        if not symbol:
            return
        
        # 时间衰减融合（SYSTEM_SPEC.md 7.5）
        effective_score = self._apply_time_decay_fusion(
            symbol=symbol,
            new_score=llm_score,
            new_confidence=confidence,
            ts_ns=ts_ns,
        )
        
        # 注入到所有策略
        self._inject_to_strategies(symbol, effective_score, data)
    
    def _apply_time_decay_fusion(
        self,
        symbol: str,
        new_score: float,
        new_confidence: float,
        ts_ns: int,
    ) -> float:
        """
        时间衰减融合
        
        公式（SYSTEM_SPEC.md 7.5）:
        score = (new×conf_new + Σ old_i×conf_i×decay_i) / Z
        decay_i = exp(-age_s × ln(2) / half_life_s)
        """
        import math
        
        now_ns = time.time_ns()
        
        # 初始化历史
        if symbol not in self._weight_history:
            self._weight_history[symbol] = []
        
        history = self._weight_history[symbol]
        
        # 计算加权和
        weighted_sum = new_score * new_confidence
        weight_sum = new_confidence
        
        # 遍历历史权重，应用衰减
        for old_entry in history:
            age_s = (now_ns - old_entry["ts_ns"]) / 1e9
            decay = math.exp(-age_s * math.log(2) / self._half_life_s)
            
            weighted_sum += old_entry["score"] * old_entry["confidence"] * decay
            weight_sum += old_entry["confidence"] * decay
        
        # 归一化
        effective_score = weighted_sum / weight_sum if weight_sum > 0 else 0.0
        
        # 添加到历史
        history.append({
            "score": new_score,
            "confidence": new_confidence,
            "ts_ns": ts_ns,
        })
        
        # 只保留最近 10 条（避免内存泄漏）
        if len(history) > 10:
            history.pop(0)
        
        self.log.debug(
            f"LLM weight fusion for {symbol}: "
            f"new={new_score:.3f}, effective={effective_score:.3f}"
        )
        
        return effective_score
    
    def _inject_to_strategies(
        self,
        symbol: str,
        effective_score: float,
        raw_data: dict,
    ) -> None:
        """
        将权重注入到所有策略
        
        假设策略实现了 update_llm_weight(symbol, score, metadata) 方法
        """
        # 获取所有策略实例
        # Nautilus 的策略通过 StrategyManager 管理
        # 这里需要访问 TradingNode 的 trader.strategy_states()
        
        # 注意：这需要在策略基类中实现 update_llm_weight 方法
        # 我们在后续步骤中会创建自定义策略基类
        
        try:
            # 通过 Actor 的 msgbus 访问策略
            # 这是一个简化实现，实际需要根据 Nautilus API 调整
            
            # 发送权重更新消息到所有策略
            # 策略需要订阅这个消息类型
            from nautilus_trader.core.message import Event
            
            class LLMWeightUpdate(Event):
                """LLM 权重更新事件"""
                def __init__(
                    self,
                    symbol: str,
                    score: float,
                    confidence: float,
                    metadata: dict,
                    event_id: str,
                    ts_event: int,
                    ts_init: int,
                ):
                    super().__init__(event_id, ts_event, ts_init)
                    self.symbol = symbol
                    self.score = score
                    self.confidence = confidence
                    self.metadata = metadata
            
            # 创建事件
            event = LLMWeightUpdate(
                symbol=symbol,
                score=effective_score,
                confidence=raw_data.get("confidence", 0.0),
                metadata={
                    "horizon": raw_data.get("horizon"),
                    "key_drivers": raw_data.get("key_drivers", []),
                    "risk_events": raw_data.get("risk_events", []),
                    "model_used": raw_data.get("model_used"),
                },
                event_id=f"llm-weight-{symbol}-{time.time_ns()}",
                ts_event=raw_data.get("ts_ns", time.time_ns()),
                ts_init=time.time_ns(),
            )
            
            # 发布到消息总线
            self.publish_data(data_type=LLMWeightUpdate, data=event)
            
            self.log.info(
                f"Injected LLM weight for {symbol}: score={effective_score:.3f}"
            )
            
        except Exception as e:
            self.log.warning(f"Failed to inject LLM weight: {e}")
