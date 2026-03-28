"""
端到端集成测试
验证 Nautilus 与 Redis 桥接的完整数据流
"""
import asyncio
import json
import time
from decimal import Decimal

import pytest
import redis.asyncio as aioredis
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.objects import Price, Quantity


@pytest.fixture
async def redis_client():
    """Redis 客户端 fixture"""
    client = await aioredis.from_url(
        "redis://localhost:6379",
        encoding="utf-8",
        decode_responses=True,
    )
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_redis_bridge_tick_format(redis_client):
    """
    测试 RedisBridgeActor 发布的 tick 格式是否符合规范
    
    验证点：
    1. topic 格式：market.tick.{exchange}.{symbol}
    2. JSON 字段名与 SYSTEM_SPEC.md 4.5 节一致
    3. 价格字段为字符串类型
    """
    # 等待 RedisBridgeActor 发布数据
    await asyncio.sleep(2)
    
    # 读取最新的 tick
    entries = await redis_client.xread(
        streams={"market.tick.binance.btcusdt": "0"},
        count=1,
    )
    
    if not entries:
        pytest.skip("No tick data available, RedisBridgeActor may not be running")
    
    stream_name, messages = entries[0]
    message_id, fields = messages[0]
    
    # 解析 JSON
    data = json.loads(fields["data"])
    
    # 验证必需字段
    required_fields = [
        "symbol", "exchange", "timestamp_ns", "received_ns",
        "bid", "ask", "last", "latency_us"
    ]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"
    
    # 验证字段类型
    assert isinstance(data["symbol"], str)
    assert isinstance(data["exchange"], str)
    assert isinstance(data["timestamp_ns"], int)
    assert isinstance(data["received_ns"], int)
    
    # 验证价格字段为字符串（关键！）
    assert isinstance(data["bid"], str)
    assert isinstance(data["ask"], str)
    assert isinstance(data["last"], str)
    
    # 验证可以转换为 Decimal
    bid = Decimal(data["bid"])
    ask = Decimal(data["ask"])
    assert bid > 0
    assert ask > bid or ask == bid
    
    print(f"✓ Tick format validated: {data['symbol']} @ {data['bid']}")


@pytest.mark.asyncio
async def test_llm_weight_injection(redis_client):
    """
    测试 LLM 权重注入流程
    
    流程：
    1. 发布 LLM 权重到 Redis
    2. LLMWeightActor 消费并注入到策略
    3. 策略调整仓位大小
    """
    # 构造 LLM 权重消息
    llm_weight = {
        "symbol": "BTC-USDT",
        "llm_score": 0.6,
        "confidence": 0.8,
        "horizon": "short",
        "key_drivers": ["Fed pause expected", "ETF inflows"],
        "risk_events": ["FOMC Thursday"],
        "model_used": "ollama/mistral:7b-instruct-q4_K_M",
        "ts_ns": time.time_ns(),
        "ttl_ms": 300000,
    }
    
    # 发布到 Redis
    await redis_client.xadd(
        "llm.weight",
        fields={"data": json.dumps(llm_weight)},
        maxlen=1000,
        approximate=True,
    )
    
    print(f"✓ Published LLM weight: score={llm_weight['llm_score']}")
    
    # 等待 LLMWeightActor 处理
    await asyncio.sleep(1)
    
    # 验证消息被消费（通过检查 consumer group）
    groups = await redis_client.xinfo_groups("llm.weight")
    
    nautilus_group = None
    for group in groups:
        if group["name"] == "nautilus-llm-cg":
            nautilus_group = group
            break
    
    if nautilus_group:
        # 检查是否有消费者
        consumers = await redis_client.xinfo_consumers("llm.weight", "nautilus-llm-cg")
        assert len(consumers) > 0, "No consumers in nautilus-llm-cg group"
        print(f"✓ LLM weight consumed by {len(consumers)} consumer(s)")
    else:
        pytest.skip("LLMWeightActor not running")


@pytest.mark.asyncio
async def test_order_event_bridge(redis_client):
    """
    测试订单事件桥接
    
    验证 RedisBridgeActor 正确转换 Nautilus 订单事件
    """
    # 等待订单事件
    await asyncio.sleep(2)
    
    # 读取最新的订单事件
    entries = await redis_client.xread(
        streams={"order.event": "0"},
        count=10,
    )
    
    if not entries:
        pytest.skip("No order events available")
    
    stream_name, messages = entries[0]
    
    for message_id, fields in messages:
        data = json.loads(fields["data"])
        
        # 验证必需字段
        assert "event_id" in data
        assert "order_id" in data
        assert "symbol" in data
        assert "kind" in data
        assert "timestamp" in data
        
        # 验证状态值
        valid_statuses = [
            "submitted", "accepted", "partial_filled",
            "filled", "cancelled", "rejected"
        ]
        assert data["kind"] in valid_statuses
        
        print(f"✓ Order event validated: {data['order_id']} - {data['kind']}")


@pytest.mark.asyncio
async def test_symbol_conversion():
    """
    测试 symbol 格式转换
    
    Nautilus: BTCUSDT.BINANCE
    我们的格式: BTC-USDT
    """
    from nautilus_core.actors.redis_bridge import RedisBridgeActor
    
    actor = RedisBridgeActor(config={"redis_url": "redis://localhost:6379"})
    
    # 测试常见格式
    test_cases = [
        ("BTCUSDT", "BTC-USDT"),
        ("ETHUSDT", "ETH-USDT"),
        ("BTCUSDC", "BTC-USDC"),
    ]
    
    for nautilus_symbol, expected in test_cases:
        instrument_id = InstrumentId(
            symbol=Symbol(nautilus_symbol),
            venue=Venue("BINANCE"),
        )
        result = actor._convert_symbol(instrument_id)
        assert result == expected, f"Expected {expected}, got {result}"
    
    print("✓ Symbol conversion validated")


@pytest.mark.asyncio
async def test_time_decay_fusion():
    """
    测试 LLM 权重时间衰减融合
    
    验证 SYSTEM_SPEC.md 7.5 节的衰减公式
    """
    from nautilus_core.actors.llm_weight_actor import LLMWeightActor
    
    actor = LLMWeightActor(config={
        "redis_url": "redis://localhost:6379",
        "half_life_s": 1800,  # 30分钟
    })
    
    symbol = "BTC-USDT"
    
    # 第一次权重
    score1 = actor._apply_time_decay_fusion(
        symbol=symbol,
        new_score=0.5,
        new_confidence=0.8,
        ts_ns=time.time_ns(),
    )
    assert abs(score1 - 0.5) < 0.01  # 第一次应该接近原值
    
    # 等待一秒
    await asyncio.sleep(1)
    
    # 第二次权重（相反方向）
    score2 = actor._apply_time_decay_fusion(
        symbol=symbol,
        new_score=-0.3,
        new_confidence=0.9,
        ts_ns=time.time_ns(),
    )
    
    # 应该是融合后的值，介于 -0.3 和 0.5 之间
    assert -0.3 <= score2 <= 0.5
    
    print(f"✓ Time decay fusion: {score1:.3f} → {score2:.3f}")


def test_strategy_llm_factor():
    """
    测试策略的 LLM 影响因子计算
    
    验证：
    - score = -1 → factor = 0.5 (强烈看跌)
    - score = 0 → factor = 1.0 (中性)
    - score = 1 → factor = 2.0 (强烈看涨)
    """
    from nautilus_core.strategies.base_strategy import MirrorQuantStrategy, MirrorQuantStrategyConfig
    
    config = MirrorQuantStrategyConfig(
        strategy_id="test",
        enable_llm=True,
        llm_weight_factor=1.0,  # 100% 影响
    )
    
    class TestStrategy(MirrorQuantStrategy):
        def calculate_signal_strength(self, tick):
            return 0.5
        
        def calculate_signal_direction(self, tick):
            return "long"
    
    strategy = TestStrategy(config)
    
    # 测试不同的 LLM 评分
    test_cases = [
        ((-1.0, 1.0), 0.5),   # 强烈看跌
        ((0.0, 1.0), 1.0),    # 中性
        ((1.0, 1.0), 2.0),    # 强烈看涨
        ((0.5, 0.8), 1.4),    # 温和看涨
        ((-0.5, 0.8), 0.6),   # 温和看跌
    ]
    
    for (score, confidence), expected_factor in test_cases:
        strategy._llm_weights["BTC-USDT"] = (score, confidence, {})
        factor = strategy.get_effective_llm_factor("BTC-USDT")
        assert abs(factor - expected_factor) < 0.01, \
            f"Score {score}, conf {confidence}: expected {expected_factor}, got {factor}"
    
    print("✓ LLM factor calculation validated")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
