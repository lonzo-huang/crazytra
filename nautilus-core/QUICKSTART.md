# Nautilus Trader 快速启动指南

## 前置要求

- Python 3.11+
- Redis 7.2+
- Docker（可选，用于运行 Redis）

## 5 分钟快速开始

### 1. 安装依赖

```bash
cd nautilus-core
pip install -r requirements.txt
```

### 2. 启动 Redis

```bash
# 使用 Docker
docker run -d -p 6379:6379 --name mirrorquant-redis redis:alpine

# 或使用本地 Redis
redis-server
```

### 3. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件
# 最少需要配置：
# REDIS_URL=redis://localhost:6379
# TRADING_MODE=paper
```

### 4. 启动纸面交易

```bash
python main.py --mode paper
```

你应该看到类似输出：

```
============================================================
Nautilus Trading Node Started
============================================================
Trader ID: MIRRORQUANT-001
Trading Mode: paper
Redis URL: redis://localhost:6379
============================================================

Press Ctrl+C to stop...
```

### 5. 测试 LLM 权重注入

在另一个终端中：

```bash
# 发布测试 LLM 权重
redis-cli XADD llm.weight * data '{
  "symbol":"BTC-USDT",
  "llm_score":0.6,
  "confidence":0.8,
  "horizon":"short",
  "key_drivers":["Test driver"],
  "risk_events":[],
  "model_used":"test",
  "ts_ns":1700000000000000000,
  "ttl_ms":300000
}'
```

检查 Nautilus 日志，应该看到：

```
LLM weight updated for BTC-USDT: score=0.600, confidence=0.800
```

### 6. 验证 Redis 桥接

```bash
# 检查 tick 数据是否写入 Redis
redis-cli XREAD COUNT 1 STREAMS market.tick.binance.btcusdt 0

# 检查订单事件
redis-cli XREAD COUNT 1 STREAMS order.event 0
```

## 完整系统启动

### 启动所有组件

```bash
# 1. 启动 Redis
docker run -d -p 6379:6379 redis:alpine

# 2. 启动 LLM 层（独立进程）
cd ../llm-layer
python -m llm_layer.main &

# 3. 启动 Nautilus 节点
cd ../nautilus-core
python main.py --mode paper &

# 4. 启动 API 网关（可选，如果保留）
cd ../api-gateway
go run ./src/main.go &

# 5. 启动前端
cd ../frontend
npm run dev
```

### 使用启动脚本

```bash
# 给脚本添加执行权限
chmod +x scripts/start.sh

# 启动纸面交易
./scripts/start.sh paper

# 启动实盘交易
./scripts/start.sh live

# 启动回测
./scripts/start.sh backtest
```

## 开发新策略

### 1. 创建策略文件

```bash
cd strategies
touch my_strategy.py
```

### 2. 实现策略

```python
from decimal import Decimal
from pydantic import Field
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OrderSide

from nautilus_core.strategies.base_strategy import (
    MirrorQuantStrategy,
    MirrorQuantStrategyConfig,
)


class MyStrategyConfig(MirrorQuantStrategyConfig):
    """我的策略配置"""
    instrument_id: str
    threshold: float = Field(default=0.02, ge=0.01, le=0.1)
    trade_size: Decimal = Field(default=Decimal("0.01"))


class MyStrategy(MirrorQuantStrategy):
    """我的策略"""
    
    def __init__(self, config: MyStrategyConfig):
        super().__init__(config)
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.threshold = config.threshold
        self.trade_size = config.trade_size
    
    def on_start(self) -> None:
        super().on_start()
        self.subscribe_quote_ticks(self.instrument_id)
        self.log.info(f"MyStrategy started for {self.instrument_id}")
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        # 获取 LLM 调整因子
        symbol = self._convert_instrument_to_symbol(tick.instrument_id)
        llm_factor = self.get_effective_llm_factor(symbol)
        
        # 计算信号
        strength = self.calculate_signal_strength(tick)
        direction = self.calculate_signal_direction(tick)
        
        # 调整仓位
        adjusted_size = float(self.trade_size) * strength * llm_factor
        
        # 执行交易逻辑
        if direction == "long" and adjusted_size > 0.001:
            order = self.order_factory.market(
                instrument_id=tick.instrument_id,
                order_side=OrderSide.BUY,
                quantity=Decimal(str(adjusted_size)),
            )
            self.submit_order(order)
    
    def calculate_signal_strength(self, tick: QuoteTick) -> float:
        # 实现你的信号强度计算
        return 0.5
    
    def calculate_signal_direction(self, tick: QuoteTick) -> str:
        # 实现你的信号方向计算
        return "long"
```

### 3. 在 main.py 中注册策略

```python
from nautilus_core.strategies.my_strategy import MyStrategy, MyStrategyConfig

strategies = [
    MyStrategyConfig(
        strategy_id="my_strategy_btc",
        instrument_id="BTCUSDT.BINANCE",
        threshold=0.02,
        trade_size="0.01",
        enable_llm=True,
    ),
]
```

### 4. 重启节点

```bash
# Ctrl+C 停止
# 重新启动
python main.py --mode paper
```

## 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio

# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_integration.py::test_redis_bridge_tick_format -v -s
```

## 常见问题

### Q: 策略没有收到 LLM 权重？

**检查清单**：
1. LLM 层是否在运行？
2. Redis `llm.weight` stream 是否有数据？
   ```bash
   redis-cli XREAD COUNT 10 STREAMS llm.weight 0
   ```
3. LLMWeightActor 是否启动？查看日志中的 "LLMWeightActor connected"
4. 策略是否调用了 `super().on_start()`？

### Q: 前端看不到数据？

**检查清单**：
1. RedisBridgeActor 是否启动？查看日志中的 "RedisBridgeActor connected"
2. Redis streams 是否有数据？
   ```bash
   redis-cli XREAD COUNT 1 STREAMS market.tick.binance.btcusdt 0
   ```
3. API 网关是否在运行？
4. 前端 WebSocket 连接是否正常？

### Q: 订单没有执行？

**检查清单**：
1. 查看日志中的 `OrderRejected` 事件
2. 检查 Nautilus RiskEngine 配置
3. 确认账户余额充足（纸面交易默认 100,000 USDT）
4. 检查仓位限制和风控参数

### Q: 如何切换到实盘模式？

1. 配置 API keys：
   ```bash
   # .env
   BINANCE_API_KEY=your_key
   BINANCE_SECRET=your_secret
   TRADING_MODE=live
   ```

2. 启动实盘模式：
   ```bash
   python main.py --mode live
   ```

3. **警告**：实盘模式会使用真实资金，请先在纸面模式充分测试！

## 下一步

- 阅读 [README.md](README.md) 了解完整架构
- 查看 [SYSTEM_SPEC.md](../SYSTEM_SPEC.md) 了解系统规范
- 参考 [strategies/ma_cross_llm.py](strategies/ma_cross_llm.py) 学习策略开发
- 阅读 [Nautilus 官方文档](https://nautilustrader.io/)

## 获取帮助

- GitHub Issues: [提交问题](https://github.com/your-repo/issues)
- 文档: [完整文档](../ARCHITECTURE.md)
- 示例: [examples/](../examples/)
