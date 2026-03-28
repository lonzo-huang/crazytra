# NautilusTrader → MirrorQuant 桥接层设计文档

## 🎯 核心原则

**NautilusTrader 和 MirrorQuant 必须通过标准化事件流解耦，而不是直接共享数据结构。**

### ❌ 错误做法
```
MirrorQuant StrategyEngine → 直接使用 NT 的 Tick 对象
```

### ✅ 正确做法
```
NT Polymarket Connector → 桥接层 → MQ Tick JSON → Redis Streams → MQ StrategyEngine
```

---

## 🏗️ 架构层次

```
┌──────────────────────────────────────────────────────────────┐
│                    Polymarket WebSocket                      │
└────────────────────────┬─────────────────────────────────────┘
                         │ Raw OrderBook / Trades
                         ▼
┌──────────────────────────────────────────────────────────────┐
│        NautilusTrader PolymarketConnector (官方)             │
│  - 连接 Polymarket WS                                         │
│  - 解析 OrderBook / Trades                                    │
│  - 维护内部订单簿                                             │
│  - 生成 NT Tick（Rust/Python 对象）                           │
└────────────────────────┬─────────────────────────────────────┘
                         │ NT Tick（内部结构）
                         ▼
┌──────────────────────────────────────────────────────────────┐
│              NautilusTrader Runner（桥接层）                  │
│  - 订阅 NT 的 Tick 事件                                       │
│  - 转换为 MQ Tick JSON（标准格式）                            │
│  - 写入 Redis Streams: market.tick.polymarket.{marketId}     │
└────────────────────────┬─────────────────────────────────────┘
                         │ MQ Tick JSON（标准格式）
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                Redis Streams 事件总线                         │
│  - market.tick.polymarket.*                                  │
│  - order.request.{accountId}                                 │
│  - order.event.{accountId}                                   │
└────────────────────────┬─────────────────────────────────────┘
                         │ 订阅事件流
                         ▼
┌──────────────────────────────────────────────────────────────┐
│             MirrorQuant StrategyEngine（Actor）               │
│  - 订阅 MQ Tick JSON                                          │
│  - 事件驱动策略                                               │
│  - 多语言支持（Python/JS/LLM）                                │
│  - 沙箱隔离                                                   │
│  - 多租户                                                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 📋 MQ Tick 标准格式

### 完整事件结构

```json
{
  "type": "market_tick",
  "ts_event": 1710000000123,
  "ts_exchange": 1710000000100,
  "source": "polymarket",
  "payload": {
    "symbol": "POLY:TRUMP_WIN",
    "market_id": "0xabc123",
    "instrument_type": "prediction",
    "exchange": "polymarket",
    "bid": 0.62,
    "ask": 0.63,
    "mid": 0.625,
    "bid_size": 1200,
    "ask_size": 900,
    "last_price": 0.63,
    "last_size": 100,
    "last_side": "buy",
    "volume_24h": 120000,
    "polymarket": {
      "outcome": "YES",
      "probability": 0.63,
      "market_type": "binary"
    }
  }
}
```

### 关键特性

1. **跨语言**: 纯 JSON，任何语言都可解析
2. **可扩展**: 可添加新字段而不破坏现有系统
3. **多租户**: 不包含用户信息，通过 Redis key 隔离
4. **可沙箱**: 策略不依赖内部对象
5. **可 LLM**: 结构清晰，LLM 可理解
6. **可回放**: 可存储和重放历史数据

---

## 🔄 转换层实现

### Python 实现（推荐用于快速开发）

```python
from mq_tick_types import MQTickEvent, MQTickPayload, NTToMQTickConverter
import redis
import json

class PolymarketBridge:
    """Polymarket NT → MQ 桥接层"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)
    
    def on_nt_tick(self, nt_tick: dict, market_data: dict):
        """处理 NT Tick 并转换为 MQ Tick"""
        # 转换为 MQ Tick
        mq_tick = NTToMQTickConverter.convert_polymarket_tick(
            nt_tick, market_data
        )
        
        # 发布到 Redis Streams
        stream_key = f"market.tick.polymarket.{market_data['id']}"
        self.redis_client.xadd(
            stream_key,
            {"data": mq_tick.model_dump_json()}
        )
```

### Rust 实现（推荐用于生产环境）

```rust
use mq_tick_types::{MQTickEvent, NTToMQTickConverter};
use redis::Commands;

pub struct PolymarketBridge {
    redis_client: redis::Client,
}

impl PolymarketBridge {
    pub fn on_nt_tick(&self, market_id: &str, bid: Option<f64>, ask: Option<f64>) {
        // 转换为 MQ Tick
        let mq_tick = NTToMQTickConverter::convert_polymarket_market(
            market_id, bid, ask, 0.0, 0.0
        );
        
        // 序列化为 JSON
        let json = mq_tick.to_json().unwrap();
        
        // 发布到 Redis Streams
        let stream_key = format!("market.tick.polymarket.{}", market_id);
        let _: () = self.redis_client
            .xadd(&stream_key, "*", &[("data", json)])
            .unwrap();
    }
}
```

---

## 🚀 订单流桥接

### MQ → NT 方向

```
MQ ExecutionEngine → Redis(order.request.*) → NT Runner → NT Execution
```

#### 订单请求格式（MQ → NT）

```json
{
  "type": "order_request",
  "ts_event": 1710000000123,
  "account_id": "demo_account",
  "payload": {
    "symbol": "POLY:TRUMP_WIN",
    "side": "BUY",
    "order_type": "MARKET",
    "quantity": 10.0,
    "price": null
  }
}
```

### NT → MQ 方向

```
NT Execution → NT Runner → Redis(order.event.*) → MQ ExecutionEngine
```

#### 订单事件格式（NT → MQ）

```json
{
  "type": "order_event",
  "ts_event": 1710000000456,
  "account_id": "demo_account",
  "payload": {
    "order_id": "NT_ORDER_1000",
    "symbol": "POLY:TRUMP_WIN",
    "side": "BUY",
    "status": "FILL",
    "quantity": 10.0,
    "price": 0.63
  }
}
```

---

## 🎯 为什么必须使用桥接层？

### 1. 解决 Rust JSON 解析问题

**当前错误**:
```
invalid type: map, expected a sequence
```

**原因**: NT 的 JSON 格式和 MQ 期望的格式不一致

**解决**: 桥接层统一转换为 MQ 标准格式

### 2. 保持架构解耦

- NT 可以升级而不影响 MQ
- MQ 可以切换执行后端（从 NT 到其他系统）
- 每层可独立测试和部署

### 3. 支持多租户

- MQ Tick 不包含用户信息
- 通过 Redis key 命名空间隔离：`user:u123:market.tick.*`

### 4. 支持多语言策略

- Python 策略
- JavaScript 策略
- LLM 策略
- 所有策略都使用相同的 JSON 格式

### 5. 支持沙箱

- 策略不能访问 NT 内部对象
- 只能读取 JSON 事件
- 安全隔离

---

## 📊 性能考虑

### 延迟分析

```
Polymarket WS → NT Connector: ~10ms
NT Connector → 桥接层: ~1ms
桥接层 → Redis: ~1ms
Redis → MQ StrategyEngine: ~1ms
总延迟: ~13ms
```

### 优化建议

1. **批量处理**: 桥接层可以批量写入 Redis
2. **异步转换**: 使用 async/await 避免阻塞
3. **缓存**: 缓存市场元数据避免重复查询
4. **压缩**: 对大订单簿使用压缩

---

## 🧪 测试策略

### 单元测试

```python
def test_nt_to_mq_conversion():
    """测试 NT → MQ 转换"""
    nt_tick = {...}
    mq_tick = NTToMQTickConverter.convert_polymarket_tick(nt_tick, market_data)
    
    assert mq_tick.type == "market_tick"
    assert mq_tick.payload.symbol == "POLY:TRUMP_WIN"
    assert mq_tick.payload.bid == 0.62
```

### 集成测试

```python
def test_end_to_end_flow():
    """测试端到端数据流"""
    # 1. 模拟 NT Tick
    # 2. 通过桥接层转换
    # 3. 写入 Redis
    # 4. MQ StrategyEngine 读取
    # 5. 验证数据一致性
```

---

## 📚 相关文件

- `mq_tick_schema.json`: JSON Schema 定义
- `mq_tick_types.py`: Python Pydantic 模型
- `mq_tick_types.rs`: Rust Serde 结构体
- `mq_tick_types.ts`: TypeScript 类型定义
- `architecture_demo.py`: 完整架构演示

---

## 🚀 下一步实施

1. ✅ 定义 MQ Tick 标准格式
2. ✅ 创建多语言类型定义
3. ⏳ 实现 Python 桥接层
4. ⏳ 实现 Rust 桥接层
5. ⏳ 集成真实 NautilusTrader
6. ⏳ 集成真实 Redis Streams
7. ⏳ 端到端测试

---

## 🎁 总结

**桥接层是 MirrorQuant 架构的关键组件，它确保：**

- ✅ NT 和 MQ 完全解耦
- ✅ 数据格式标准化
- ✅ 多语言支持
- ✅ 多租户隔离
- ✅ 可扩展性
- ✅ 可维护性

**没有桥接层，MirrorQuant 的专业架构将无法实现！**
