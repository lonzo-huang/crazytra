# Nautilus Trader 整合模块

本模块将 Nautilus Trader 整合到 Crazytra 自动交易系统中，保持原有架构的 Redis Streams 作为桥接层。

## 架构整合

```
原有架构                    整合后
─────────────────────────────────────────────────────
Rust 数据层          →  Nautilus DataEngine (Rust core)
Python 策略层        →  Nautilus Strategy 基类
Python 信号合成      →  Nautilus Portfolio + 自定义 Actor
Go 风控层            →  Nautilus RiskEngine + Redis 持久化
Go 交易层            →  Nautilus ExecutionEngine
Redis Streams        →  保留，作为 Nautilus→外部 的桥
LLM 层 (Python)      →  独立进程，写 llm.weight topic
API 网关 (Go)        →  保留，订阅 Redis
前端 (React)         →  不变
```

## 核心组件

### 1. RedisBridgeActor
- **职责**：将 Nautilus 事件同步到 Redis Streams
- **位置**：`actors/redis_bridge.py`
- **关键特性**：
  - 订阅所有 Nautilus tick 和订单事件
  - 转换为与自建数据层完全相同的 JSON 格式
  - 确保前端和 API 网关代码零修改

### 2. LLMWeightActor
- **职责**：从 Redis 读取 LLM 权重并注入到策略
- **位置**：`actors/llm_weight_actor.py`
- **关键特性**：
  - 消费 Redis `llm.weight` topic
  - 实现时间衰减融合（30分钟半衰期）
  - 发布 LLMWeightUpdate 事件到策略

### 3. CrazytraStrategy 基类
- **职责**：扩展 Nautilus Strategy，支持 LLM 权重
- **位置**：`strategies/base_strategy.py`
- **关键特性**：
  - 继承 Nautilus Strategy（保持回测=实盘）
  - 添加 `on_llm_weight_updated()` 回调
  - 提供 `get_effective_llm_factor()` 方法
  - 支持热重载状态迁移

### 4. 示例策略
- **MACrossLLMStrategy**：均线交叉 + LLM 权重增强
- **位置**：`strategies/ma_cross_llm.py`

## 安装

```bash
cd nautilus-core
pip install -r requirements.txt
```

## 配置

### 环境变量

创建 `.env` 文件：

```bash
# Redis
REDIS_URL=redis://localhost:6379

# 交易模式
TRADING_MODE=paper  # paper | live

# Binance
BINANCE_API_KEY=your_api_key
BINANCE_SECRET=your_api_secret
BINANCE_TESTNET=false

# Polymarket
POLYMARKET_API_KEY=your_api_key
POLYMARKET_WALLET_ADDRESS=0x...

# 回测
BACKTEST_DATA_PATH=./data
BACKTEST_START=2024-01-01
BACKTEST_END=2024-12-31
```

## 运行

### 纸面交易模式

```bash
python main.py --mode paper
```

### 实盘模式

```bash
python main.py --mode live
```

### 回测模式

```bash
python main.py --mode backtest
```

## 数据流

### Tick 数据流

```
交易所 WebSocket
    ↓
Nautilus DataEngine (Rust)
    ↓
RedisBridgeActor
    ↓
Redis Stream: market.tick.{exchange}.{symbol}
    ↓
前端 / API 网关 / LLM 层（不变）
```

### LLM 权重流

```
LLM 层（独立进程）
    ↓
Redis Stream: llm.weight
    ↓
LLMWeightActor
    ↓
LLMWeightUpdate 事件
    ↓
CrazytraStrategy.on_llm_weight_updated()
    ↓
调整仓位大小
```

### 订单流

```
Strategy.submit_order()
    ↓
Nautilus RiskEngine（风控检查）
    ↓
Nautilus ExecutionEngine
    ↓
交易所 API
    ↓
OrderEvent
    ↓
RedisBridgeActor
    ↓
Redis Stream: order.event
    ↓
前端 / API 网关（不变）
```

## 与原有系统的兼容性

### 保持不变的部分

1. **LLM 层**：仍然是独立 Python 进程，写入 `llm.weight` topic
2. **API 网关**：继续从 Redis 消费数据
3. **前端**：完全不需要修改
4. **Redis 消息格式**：与自建数据层完全一致

### 替换的部分

1. **Rust 数据层** → Nautilus DataEngine
2. **Python 策略层** → Nautilus Strategy
3. **Go 风控层** → Nautilus RiskEngine（可选，也可保留自建风控）
4. **Go 交易层** → Nautilus ExecutionEngine

### 可选保留的部分

- **Go 风控层**：可以通过 Redis 请求-响应模式与 Nautilus 集成
- **自定义滑点模型**：可以在 Nautilus 的 SimulatedExchange 中配置

## 开发新策略

### 1. 创建策略配置

```python
from pydantic import Field
from nautilus_core.strategies.base_strategy import CrazytraStrategyConfig

class MyStrategyConfig(CrazytraStrategyConfig):
    instrument_id: str
    my_param: int = Field(default=20, ge=5, le=100)
    enable_llm: bool = True
    llm_weight_factor: float = 0.5
```

### 2. 实现策略类

```python
from nautilus_core.strategies.base_strategy import CrazytraStrategy

class MyStrategy(CrazytraStrategy):
    def __init__(self, config: MyStrategyConfig):
        super().__init__(config)
        # 初始化策略状态
    
    def on_start(self) -> None:
        super().on_start()
        # 订阅数据
        self.subscribe_quote_ticks(self.instrument_id)
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        # 计算信号
        strength = self.calculate_signal_strength(tick)
        direction = self.calculate_signal_direction(tick)
        
        # 获取 LLM 调整因子
        llm_factor = self.get_effective_llm_factor(symbol)
        
        # 调整仓位
        adjusted_size = base_size * strength * llm_factor
        
        # 下单
        if direction == "long":
            self._open_long(tick, adjusted_size)
    
    def on_llm_weight_updated(self, symbol, score, confidence, metadata):
        # 响应 LLM 权重变化
        self.log.info(f"LLM: {symbol} score={score:.3f}")
    
    def calculate_signal_strength(self, tick) -> float:
        # 实现信号强度计算
        return 0.5
    
    def calculate_signal_direction(self, tick) -> str:
        # 实现信号方向计算
        return "long"
```

### 3. 在 main.py 中注册

```python
strategies = [
    MyStrategyConfig(
        strategy_id="my_strategy_btc",
        instrument_id="BTCUSDT.BINANCE",
        my_param=30,
    ),
]
```

## 测试

### 单元测试

```bash
pytest tests/
```

### 端到端测试

```bash
# 1. 启动 Redis
docker run -d -p 6379:6379 redis:alpine

# 2. 启动 LLM 层（独立进程）
cd ../llm-layer && python -m llm_layer.main

# 3. 启动 Nautilus 节点
python main.py --mode paper

# 4. 发布测试 LLM 权重
redis-cli XADD llm.weight * data '{"symbol":"BTC-USDT","llm_score":0.6,"confidence":0.8,"ts_ns":1700000000000000000}'

# 5. 检查日志，确认权重被注入
```

## 性能优化

### Redis 连接池

RedisBridgeActor 和 LLMWeightActor 使用异步 Redis 客户端，自动管理连接池。

### 批量 ACK

LLMWeightActor 批量确认消息，减少 Redis 往返次数。

### 非阻塞发布

RedisBridgeActor 使用 `asyncio.create_task()` 异步发布，不阻塞 Nautilus 主循环。

## 故障排查

### 问题：策略没有收到 LLM 权重

**检查**：
1. LLM 层是否在运行？
2. Redis `llm.weight` stream 是否有数据？
3. LLMWeightActor 是否启动？
4. 策略是否调用了 `super().on_start()`？

### 问题：前端看不到 tick 数据

**检查**：
1. RedisBridgeActor 是否启动？
2. Redis `market.tick.*` stream 是否有数据？
3. 消息格式是否正确？

### 问题：订单没有执行

**检查**：
1. Nautilus RiskEngine 是否拒绝了订单？
2. 查看日志中的 `OrderRejected` 事件
3. 检查风控配置（`RISK_ENGINE_CONFIG`）

## 迁移指南

### 从自建策略层迁移

1. 将 `BaseStrategy` 改为继承 `CrazytraStrategy`
2. 将 `on_tick()` 改为 `on_quote_tick()`
3. 添加 `calculate_signal_strength()` 和 `calculate_signal_direction()` 方法
4. 使用 `self.order_factory` 创建订单
5. 使用 `self.submit_order()` 提交订单

### 从自建风控层迁移

可选方案：
1. **完全迁移**：使用 Nautilus RiskEngine，配置 `RISK_ENGINE_CONFIG`
2. **保留自建**：通过 Redis 请求-响应模式集成
3. **混合模式**：Nautilus 做基础风控，自建做高级风控

## 参考文档

- [Nautilus Trader 官方文档](https://nautilustrader.io/)
- [SYSTEM_SPEC.md](../SYSTEM_SPEC.md) - 系统规范
- [QUICK_REF.md](../QUICK_REF.md) - 快速参考
