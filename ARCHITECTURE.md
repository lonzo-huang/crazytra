# Crazytra - 统一自动交易系统架构文档

## 一、系统概述

**Crazytra** 是一个全栈自动交易系统，支持多市场、多策略、LLM 情感增强的智能交易。系统采用分层微服务架构，每层使用最适合的编程语言实现，通过消息总线完全解耦。

### 1.1 核心特性

- **多市场支持**：币安(Binance)、Polymarket、Trading212、老虎证券(Tiger)等
- **智能策略**：插件化策略系统，信号可灵活组合
- **AI 增强**：LLM 实时分析新闻，为策略提供权重
- **风控管理**：实时风控、熔断器、仓位管理
- **双模式交易**：纸面交易模拟 + 实盘执行
- **现代化前端**：React + TypeScript + 实时图表
- **多租户 SaaS**：支持云端部署，多租户隔离，订阅制商业模式
- **自定义订阅**：租户可自由选择市场和策略，按需付费
- **Telegram Bot**：自然语言交易控制，实时通知推送

### 1.2 技术选型原则

核心原则是**语言按职责分工**：

| 职责 | 语言 | 原因 |
|------|------|------|
| 数据管道 | Rust | 延迟敏感、内存安全、高并发 |
| 风控与交易 | Go | 高并发、goroutine、垃圾回收 |
| 策略与 AI | Python | 快速迭代、丰富生态、ML 友好 |
| 用户界面 | React+TS | 现代化、实时性、类型安全 |

---

## 二、系统架构总览

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        外部市场数据源（可插拔扩展）                        │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Binance  │  │Polymarket│  │Trading212│  │  Tiger   │  │  +扩展   │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│       │             │             │             │             │       │
│       └─────────────┴─────────────┴─────────────┴─────────────┘       │
└──────────────────────┼────────────────────────────────────────────────┘
                       ▼ WebSocket / REST
┌─────────────────────────────────────────────────────────────────────────┐
│                      Nautilus Trader 核心引擎                            │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │                    DataEngine (Rust 核心)                            │ │
│ │  WebSocket 管理 · 订单簿维护 · 数据标准化 · 高性能处理                 │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                       │                                                 │
│                       ▼ QuoteTick / TradeTick                           │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │                  StrategyEngine (Python)                             │ │
│ │  ┌──────────────────────┐  ┌──────────────────────┐                 │ │
│ │  │  CrazytraStrategy    │  │  MACrossLLMStrategy  │                 │ │
│ │  │  (基类 + LLM 支持)    │  │  (示例策略)          │                 │ │
│ │  └──────────────────────┘  └──────────────────────┘                 │ │
│ │         ▲                                                            │ │
│ │         │ LLM 权重注入                                               │ │
│ │  ┌──────────────────────┐                                           │ │
│ │  │  LLMWeightActor      │ ◄─────── Redis: llm.weight                │ │
│ │  └──────────────────────┘                                           │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                       │                                                 │
│                       ▼ 订单请求                                        │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │                    RiskEngine                                        │ │
│ │  仓位限制 · 保证金检查 · 风险指标监控                                  │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                       │                                                 │
│                       ▼ 风控通过                                        │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │                  ExecutionEngine                                     │ │
│ │  订单路由 · 状态机管理 · 成交回报 · 多交易所支持                        │ │
│ │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │ │
│ │  │ 纸面交易模拟 │  │  订单管理   │  │   实盘执行   │                  │ │
│ │  └─────────────┘  └─────────────┘  └─────────────┘                  │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│                       │                                                 │
│                       ▼ 订单事件                                        │
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │                  RedisBridgeActor                                    │ │
│ │  Nautilus 事件 → Redis JSON 格式转换 · 异步发布                       │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────────────────┘
                          ▼ Redis Streams（桥接层）
┌─────────────────────────────────────────────────────────────────────────┐
│                       Redis Streams 桥接层                               │
│  market.tick.* │ order.event │ position.update │ account.state          │
└─────────────────────────────────────────────────────────────────────────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   LLM 层         │  │   API 网关       │  │   前端           │
│   (Python)       │  │   (Go/FastAPI)   │  │   (React)        │
│                  │  │                  │  │                  │
│ GPT-4o/Claude    │  │ REST/WebSocket   │  │ 实时图表         │
│ Ollama 本地      │  │ 统一入口         │  │ 策略编辑器       │
│ 新闻情感分析     │  │                  │  │ 回测报告         │
└──────────────────┘  └──────────────────┘  └──────────────────┘
          │
          └─────► Redis: llm.weight (权重向量)
```

### 2.2 数据流路径

**Tick 数据流**：
```
交易所 → Nautilus DataEngine → RedisBridgeActor → Redis → 前端/API网关
```

**LLM 权重流**：
```
LLM层 → Redis llm.weight → LLMWeightActor → Strategy.on_llm_weight_updated()
```

**订单流**：
```
Strategy → RiskEngine → ExecutionEngine → 交易所
                                        ↓
                                 RedisBridgeActor → Redis → 前端
```

---

## 三、分层详细设计

### 3.1 Nautilus 核心层（Python + Rust）

#### 3.1.1 职责定位

**Nautilus Trader** 是系统的核心交易引擎，负责数据获取、策略执行、风控管理和订单执行。采用 Python API + Rust 核心的混合架构。

**关键特性**：
- 🚀 **回测=实盘**：相同策略代码用于回测和实盘
- ⚡ **Rust 核心**：数据引擎用 Rust 实现，纳秒级延迟
- 🔄 **事件驱动**：完整的事件溯源和重放能力
- 📊 **专业级**：机构级交易引擎

#### 3.1.2 Nautilus 核心组件

**1. DataEngine（Rust 核心）**
- 高性能数据处理引擎
- WebSocket 连接管理
- 订单簿维护和聚合
- 数据标准化和验证

**2. StrategyEngine（Python）**
- 策略生命周期管理
- 事件路由和分发
- 状态持久化和恢复
- 热重载支持（通过 CrazytraStrategy）

**3. RiskEngine**
- 实时风控检查
- 仓位限制管理
- 保证金计算
- 风险指标监控

**4. ExecutionEngine**
- 订单路由和执行
- 订单状态机管理
- 成交回报处理
- 多交易所支持

**5. Portfolio**
- 账户状态管理
- 持仓跟踪
- PnL 计算
- 绩效统计

#### 3.1.3 自定义扩展组件

**RedisBridgeActor** (`nautilus-core/actors/redis_bridge.py`)

```python
class RedisBridgeActor(Actor):
    """Nautilus → Redis 桥接"""
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        # 转换为 Crazytra JSON 格式
        payload = {
            "symbol": self._convert_symbol(tick.instrument_id),
            "exchange": tick.instrument_id.venue.value.lower(),
            "timestamp_ns": tick.ts_event,
            "bid": str(tick.bid_price),  # 必须字符串
            "ask": str(tick.ask_price),
            # ...
        }
        # 异步发布到 Redis
        asyncio.create_task(self._publish_to_redis(payload))
```

**LLMWeightActor** (`nautilus-core/actors/llm_weight_actor.py`)

```python
class LLMWeightActor(Actor):
    """LLM 权重注入"""
    
    async def _poll_loop(self) -> None:
        # 消费 Redis llm.weight stream
        entries = await self._redis.xreadgroup(
            groupname="nautilus-llm-cg",
            consumername=self._consumer_name,
            streams={"llm.weight": ">"},
        )
        # 应用时间衰减融合
        effective_score = self._apply_time_decay_fusion(...)
        # 发布到策略
        self._inject_to_strategies(symbol, effective_score)
```

**CrazytraStrategy** (`nautilus-core/strategies/base_strategy.py`)

```python
class CrazytraStrategy(Strategy):
    """扩展 Nautilus Strategy，支持 LLM"""
    
    def get_effective_llm_factor(self, symbol: str) -> float:
        """获取 LLM 影响因子 [0.5, 2.0]"""
        if not self.config.enable_llm:
            return 1.0
        
        score, confidence, _ = self._llm_weights.get(symbol, (0.0, 0.0, {}))
        # score ∈ [-1, 1] → factor ∈ [0.5, 2.0]
        return 1.0 + score * confidence * self.config.llm_weight_factor
```

#### 3.1.4 支持的交易所

**加密货币**：
| 交易所 | Nautilus 支持 | 状态 | 说明 |
|--------|--------------|------|------|
| **Binance** | ✅ 原生支持 | 生产可用 | Spot + Futures |

**股票市场**：
| 交易所 | Nautilus 支持 | 状态 | 说明 |
|--------|--------------|------|------|
| **Interactive Brokers** | ✅ 原生支持 | 生产可用 | 全球股票、期货、期权 |
| **Alpaca** | ✅ 自定义适配器 | 已实现 | 美股、免费、零佣金 |
| **Trading212** | 🚧 自定义适配器 | 开发中 | 欧美股票、零佣金 |
| **Tiger Brokers** | 🚧 自定义适配器 | 计划中 | 美股、港股、A股 |
| **Robinhood** | ⚠️ 非官方 API | 不推荐 | 无官方 API，有风险 |

**其他市场**：
| 交易所 | Nautilus 支持 | 状态 | 说明 |
|--------|--------------|------|------|
| **Polymarket** | 🚧 自定义适配器 | 开发中 | 预测市场 |
| **Betfair** | ✅ 原生支持 | 生产可用 | 体育博彩 |

**推荐组合**：
- 🏆 **新手**: Alpaca（美股）+ Binance（加密货币）
- 🏆 **专业**: Interactive Brokers（全球市场）
- 🏆 **多市场**: Alpaca（美股）+ Trading212（欧股）+ Binance（加密货币）

**详细文档**：`docs/STOCK_EXCHANGES_SUPPORT.md`

#### 3.1.5 配置示例

```python
# nautilus-core/config.py
from nautilus_trader.config import TradingNodeConfig

config = TradingNodeConfig(
    trader_id="CRAZYTRA-001",
    log_level="INFO",
    
    # 数据客户端
    data_clients={
        "BINANCE": BinanceDataClientConfig(...),
    },
    
    # 执行客户端
    exec_clients={
        "BINANCE": BinanceExecClientConfig(...),
    },
    
    # 策略
    strategies=[
        MACrossLLMStrategyConfig(
            instrument_id="BTCUSDT.BINANCE",
            fast_period=10,
            slow_period=20,
            enable_llm=True,
        ),
    ],
    
    # 自定义 Actors
    actors=[
        RedisBridgeActorConfig(...),
        LLMWeightActorConfig(...),
    ],
)
```

### 3.2 Redis Streams 桥接层

#### 3.2.1 职责定位

Redis Streams 作为 Nautilus 与外部系统的桥接层。

- **Nautilus 内部**：使用 MessageBus（高性能事件系统）
- **外部系统**：LLM 层、API 网关、前端通过 Redis Streams 通信
- **桥接组件**：RedisBridgeActor 和 LLMWeightActor

#### 3.2.2 Redis Streams 用途

| 用途 | 生产者 | 消费者 |
|------|--------|--------|
| **Tick、订单事件** | RedisBridgeActor | API 网关、前端 |
| **LLM 权重** | LLM 层 | LLMWeightActor |
| **审计日志** | RedisBridgeActor | 审计系统 |

#### 3.2.3 主题设计（Topic Schema）

```
# Nautilus → Redis（由 RedisBridgeActor 发布）
market.tick.{exchange}.{symbol}    # 实时行情
order.event                        # 订单事件
position.update                    # 持仓更新
account.state                      # 账户状态

# Redis → Nautilus（由 LLMWeightActor 消费）
llm.weight                         # LLM 权重向量

# 可选（如果保留自建组件）
strategy.signal                    # 策略信号（已被 Nautilus 替代）
risk.alert                         # 风控告警
```

#### 3.2.4 数据流向

```
┌──────────────────────────────────────────────────────────┐
│                    Nautilus Trader                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ DataEngine   │→│ Strategy     │→│ RiskEngine   │   │
│  │  (Rust)      │  │ (Python)     │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│         ↓                  ↑                  ↓          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │RedisBridge   │  │LLMWeightActor│  │ExecutionEngine│  │
│  │Actor         │  │              │  │              │   │
│  └──────┬───────┘  └──────▲───────┘  └──────┬───────┘   │
└─────────┼──────────────────┼──────────────────┼──────────┘
          ↓                  ↑                  ↓
    ┌─────────────────────────────────────────────────┐
    │           Redis Streams（桥接层）                │
    │  market.tick.*  │  llm.weight  │  order.event   │
    └─────────────────────────────────────────────────┘
          ↓                  ↑                  ↓
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ 前端     │      │ LLM 层   │      │API 网关  │
    │ (React)  │      │(Python)  │      │  (Go)    │
    └──────────┘      └──────────┘      └──────────┘
```

### 3.3 策略层

#### 3.3.1 职责定位

策略层基于 **Nautilus Strategy** 框架，扩展了 **CrazytraStrategy** 基类以支持 LLM 权重注入。

#### 3.3.2 CrazytraStrategy 基类

```python
from nautilus_trader.trading.strategy import Strategy
from decimal import Decimal

class CrazytraStrategy(Strategy):
    """扩展 Nautilus Strategy，添加 LLM 支持"""
    
    def __init__(self, config: CrazytraStrategyConfig):
        super().__init__(config)
        self._llm_weights: dict[str, tuple] = {}  # (score, confidence, metadata)
    
    def on_llm_weight_updated(
        self, 
        symbol: str, 
        score: float, 
        confidence: float,
        metadata: dict
    ) -> None:
        """LLM 权重更新回调"""
        self._llm_weights[symbol] = (score, confidence, metadata)
        self.log.info(f"LLM weight updated: {symbol} score={score:.3f}")
    
    def get_effective_llm_factor(self, symbol: str) -> float:
        """
        获取 LLM 影响因子
        
        Returns:
            float: [0.5, 2.0] 范围的因子
            - 1.0 = 中性（无 LLM 或 score=0）
            - < 1.0 = 看跌（减少多头仓位）
            - > 1.0 = 看涨（增加多头仓位）
        """
        if not self.config.enable_llm:
            return 1.0
        
        score, confidence, _ = self._llm_weights.get(symbol, (0.0, 0.0, {}))
        # score ∈ [-1, 1], confidence ∈ [0, 1]
        # factor = 1.0 + score * confidence * weight_factor
        return 1.0 + score * confidence * self.config.llm_weight_factor
    
    @abstractmethod
    def calculate_signal_strength(self, tick) -> float:
        """子类实现：计算基础信号强度 [0, 1]"""
        pass
    
    @abstractmethod
    def calculate_signal_direction(self, tick) -> str:
        """子类实现：计算信号方向 'long'/'short'/'hold'"""
        pass
```

#### 3.3.3 示例策略：均线交叉 + LLM

```python
class MACrossLLMStrategy(CrazytraStrategy):
    """均线交叉策略 + LLM 权重调整"""
    
    def on_start(self) -> None:
        super().on_start()
        self.fast_ma = SimpleMovingAverage(self.config.fast_period)
        self.slow_ma = SimpleMovingAverage(self.config.slow_period)
        self.subscribe_quote_ticks(self.instrument_id)
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        # 更新均线
        mid_price = (tick.bid_price + tick.ask_price) / 2
        self.fast_ma.update(mid_price)
        self.slow_ma.update(mid_price)
        
        if not self.fast_ma.initialized or not self.slow_ma.initialized:
            return
        
        # 计算基础信号
        strength = self.calculate_signal_strength(tick)
        direction = self.calculate_signal_direction(tick)
        
        # 获取 LLM 调整因子
        symbol = self._convert_instrument_to_symbol(tick.instrument_id)
        llm_factor = self.get_effective_llm_factor(symbol)
        
        # 调整仓位大小
        base_size = self.config.trade_size
        adjusted_size = float(base_size) * strength * llm_factor
        
        # 执行交易
        if direction == "long" and adjusted_size > 0.001:
            self._submit_market_order(OrderSide.BUY, adjusted_size)
        elif direction == "short" and adjusted_size > 0.001:
            self._submit_market_order(OrderSide.SELL, adjusted_size)
```

#### 3.3.4 回测引擎（Nautilus BacktestEngine）

Nautilus 提供专业级回测引擎，完全事件驱动：

```python
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.node import BacktestNode

# 创建回测节点
node = BacktestNode(config=backtest_config)

# 添加数据
node.add_data(
    data_type=QuoteTick,
    data=historical_ticks,  # Parquet 或 CSV
)

# 添加策略
node.add_strategy(MACrossLLMStrategy(config))

# 运行回测
result = node.run()

# 生成报告
print(result.stats_pnls())
print(result.stats_returns())
```

**回测特性**：
- ✅ 完整的订单簿模拟
- ✅ 真实的滑点和手续费
- ✅ 部分成交支持
- ✅ 延迟模拟
- ✅ 与实盘完全相同的代码

#### 3.3.5 策略开发流程

1. **继承 CrazytraStrategy**
2. **实现抽象方法**：`calculate_signal_strength`, `calculate_signal_direction`
3. **订阅数据**：`subscribe_quote_ticks` 或 `subscribe_bars`
4. **使用 LLM 因子**：`get_effective_llm_factor()` 调整仓位
5. **回测验证**：使用 BacktestEngine
6. **部署实盘**：相同代码，切换 `--mode live`

详见 `nautilus-core/strategies/ma_cross_llm.py` 完整示例。

### 3.4 第四层：LLM 层（Python）

#### 3.4.1 职责定位

把"世界信息"转化为策略层能用的"权重向量"。实时分析新闻、社交媒体、链上数据等，为每个交易标的生成情感权重。

#### 3.4.2 架构设计

```
┌─────────────────────────────────────────────────────┐
│                   新闻聚合器                          │
│  NewsAPI / RSS / Twitter / Discord / 链上事件       │
└─────────────────────────────────────────────────────┘
                          │
                          ▼ 新闻事件
┌─────────────────────────────────────────────────────┐
│                   相关性过滤器                        │
│  判断新闻是否与持仓/关注标的相关                       │
└─────────────────────────────────────────────────────┘
                          │
                          ▼ 相关新闻
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   GPT-4o     │  │   Claude     │  │   Ollama     │
│  (在线模型)   │  │  (在线模型)   │  │  (本地模型)   │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼ 情感分析结果
┌─────────────────────────────────────────────────────┐
│                   权重计算引擎                        │
│  将 LLM 输出转化为策略可用的权重向量 (0.0 ~ 1.0)     │
└─────────────────────────────────────────────────────┘
                          │
                          ▼ Redis Pub/Sub
                   strategy.on_weight_update()
```

#### 3.4.3 混合模型策略

| 模型类型 | 延迟 | 成本 | 适用场景 |
|----------|------|------|----------|
| **Ollama** (本地 Mistral 7B/Llama 3) | ~500ms | 免费 | 普通更新、高频调用 |
| **GPT-4o** (OpenAI) | ~2-5s | 付费 | 深度分析、重要事件 |
| **Claude** (Anthropic) | ~3-7s | 付费 | 复杂推理、长文本 |

**建议策略**：普通更新用本地模型，重要事件用在线模型。

#### 3.4.4 Prompt 设计

```python
SYSTEM_PROMPT = """
你是一个金融情感分析专家。分析以下新闻对 {symbol} 的短期影响。

输出必须是严格的 JSON 格式：
{
  "sentiment": "bullish|bearish|neutral",
  "confidence": 0.0-1.0,
  "factors": ["factor1", "factor2"],
  "time_horizon": "short|medium|long"
}
"""
```

#### 3.4.5 权重映射

```python
def sentiment_to_weight(llm_response: dict) -> float:
    """将 LLM 情感分析映射为策略权重"""
    sentiment_map = {
        "bullish": 1.0,
        "neutral": 0.5,
        "bearish": 0.0
    }
    base = sentiment_map.get(llm_response["sentiment"], 0.5)
    confidence = llm_response["confidence"]
    return base * confidence  # 0.0 ~ 1.0
```

### 3.5 第五层：风控层（Go）

#### 3.5.1 职责定位

用 Go 实现，充分利用 goroutine 并发能力处理实时风控。作为策略信号和交易执行之间的"闸门"。

#### 3.5.2 风控规则类型

```go
type RiskRule interface {
    Check(ctx context.Context, signal *Signal) error
    Name() string
}

// 1. 仓位限制
type PositionLimitRule struct {
    MaxPositionSize float64  // 单仓最大占比（如 0.2 = 20%）
}

// 2. 日亏损限制
type DailyLossLimitRule struct {
    MaxDailyLoss float64  // 日亏损上限（如 0.05 = 5%）
    CurrentLoss  float64  // 当日已实现亏损
}

// 3. 最大回撤
type MaxDrawdownRule struct {
    MaxDrawdown  float64  // 最大回撤限制（如 0.15 = 15%）
    PeakValue    float64  // 历史峰值
    CurrentValue float64  // 当前净值
}

// 4. 信号置信度过滤
type ConfidenceFilterRule struct {
    MinConfidence float64  // 最低置信度阈值
}

// 5. 熔断器
type CircuitBreakerRule struct {
    FailureThreshold   int           // 连续失败次数阈值
    RecoveryTimeout    time.Duration // 熔断后恢复等待时间
    HalfOpenMaxCalls   int           // 半开状态允许的最大测试调用
    State              CircuitState   // 关闭/开启/半开
}
```

#### 3.5.3 熔断器状态机

```
         失败次数 < 阈值
    ┌───────────────────────┐
    │                       │
    ▼                       │
┌───────┐   失败 >= 阈值    │
│ CLOSED │ ──────────────> │
│ 关闭   │                  │
└───────┘                  │
    │                      │
    │ 超时后                │
    ▼                      │
┌───────┐   测试成功        │
│ HALF  │ ──────────────> │
│ OPEN  │                  │
│ 半开  │   测试失败        │
└───────┘ ──────────────> │
    │                       │
    ▼                       │
┌───────┐                  │
│ OPEN  │ ─────────────────┘
│ 开启  │  超时后 -> HALF OPEN
└───────┘
```

#### 3.5.4 状态持久化

熔断器状态持久化到 Redis，确保服务重启后状态不丢失：

```go
func (cb *CircuitBreakerRule) persistState() error {
    key := fmt.Sprintf("circuit_breaker:%s", cb.Name())
    state := map[string]interface{}{
        "state":          cb.State,
        "failures":       cb.ConsecutiveFailures,
        "last_failure":   cb.LastFailureTime,
    }
    return redisClient.HSet(ctx, key, state).Err()
}
```

#### 3.5.5 动态配置

风控规则支持动态配置，不要硬编码：

```yaml
# risk_config.yaml
rules:
  - name: position_limit
    enabled: true
    params:
      max_position_size: 0.2  # 20%
  
  - name: daily_loss
    enabled: true
    params:
      max_daily_loss: 0.05  # 5%
  
  - name: circuit_breaker
    enabled: true
    params:
      failure_threshold: 5
      recovery_timeout: 5m
```

### 3.6 第六层：交易层（Go）

#### 3.6.1 职责定位

负责订单管理、交易执行，支持纸面交易和实盘交易两种模式。

#### 3.6.2 纸面交易（Paper Trading）

**模拟精度是关键**，决定策略验证的可信度：

| 模拟要素 | 实现方式 |
|----------|----------|
| **撮合延迟** | 随机 1-50ms |
| **滑点** | 依据成交量占比动态计算 |
| **手续费** | maker/taker 费率分开处理 |
| **部分成交** | 订单簿深度有限时按比例成交 |

```go
// 模拟撮合引擎
type PaperMatchingEngine struct {
    orderBooks map[string]*OrderBook  // 每个 symbol 一个订单簿
    accounts   map[string]*Account    // 每个用户一个账户
}

func (e *PaperMatchingEngine) matchOrder(order *Order) (*Fill, error) {
    // 1. 延迟模拟
    latency := time.Duration(rand.Intn(50)+1) * time.Millisecond
    time.Sleep(latency)
    
    // 2. 滑点计算
    slippage := e.calculateSlippage(order.Symbol, order.Size)
    fillPrice := order.Price * (1 + slippage)
    
    // 3. 部分成交
    available := e.orderBooks[order.Symbol].availableVolume(order.Side)
    fillSize := min(order.Size, available)
    
    // 4. 手续费
    fee := fillSize * fillPrice * e.getFeeRate(order.Type)
    
    return &Fill{
        OrderID:   order.ID,
        Size:      fillSize,
        Price:     fillPrice,
        Fee:       fee,
        Timestamp: time.Now(),
    }, nil
}
```

#### 3.6.3 订单管理（OMS）

```go
type OrderStatus string

const (
    StatusPending       OrderStatus = "pending"
    StatusSubmitted     OrderStatus = "submitted"
    StatusPartialFilled OrderStatus = "partial_filled"
    StatusFilled        OrderStatus = "filled"
    StatusCancelled     OrderStatus = "cancelled"
    StatusRejected      OrderStatus = "rejected"
)

type Order struct {
    ID            string
    Symbol        string
    Side          Side        // Buy / Sell
    Type          OrderType   // Market / Limit / Stop
    Size          decimal.Decimal
    Price         decimal.Decimal
    StopPrice     *decimal.Decimal  // 止损价
    Status        OrderStatus
    FilledSize    decimal.Decimal
    AvgFillPrice  decimal.Decimal
    CreatedAt     time.Time
    UpdatedAt     time.Time
}
```

#### 3.6.4 实盘适配器

```go
type LiveExchangeAdapter interface {
    Connect() error
    Disconnect() error
    
    // 订单操作
    SubmitOrder(order *Order) (*Order, error)
    CancelOrder(orderID string) error
    GetOrder(orderID string) (*Order, error)
    
    // 账户信息
    GetBalance() (*Balance, error)
    GetPositions() ([]Position, error)
}

// 交易所适配器实现
type BinanceAdapter struct{ /* ... */ }
type PolymarketAdapter struct{ /* ... */ }
type MetaMaskAdapter struct{ /* ... */ }  // 区块链钱包
```

### 3.7 第七层：API 网关（Go）

#### 3.7.1 职责定位

统一入口，提供 REST API 和 WebSocket 服务，处理认证、限流、路由。

#### 3.7.2 核心功能

```go
// 路由设计
func setupRoutes(r *gin.Engine) {
    api := r.Group("/api/v1")
    {
        // 行情数据
        api.GET("/tick/:symbol", handlers.GetTick)
        api.GET("/orderbook/:symbol", handlers.GetOrderBook)
        
        // 策略管理
        api.GET("/strategies", handlers.ListStrategies)
        api.POST("/strategies/:id/enable", handlers.EnableStrategy)
        api.POST("/strategies/:id/disable", handlers.DisableStrategy)
        
        // 交易操作
        api.POST("/orders", handlers.SubmitOrder)
        api.GET("/orders", handlers.ListOrders)
        api.DELETE("/orders/:id", handlers.CancelOrder)
        
        // 账户信息
        api.GET("/balance", handlers.GetBalance)
        api.GET("/positions", handlers.GetPositions)
        
        // 回测
        api.POST("/backtest", handlers.RunBacktest)
        api.GET("/backtest/:id", handlers.GetBacktestResult)
    }
    
    // WebSocket 实时推送
    r.GET("/ws", handlers.WebSocketHandler)
}
```

#### 3.7.3 WebSocket 推送

```go
// 订阅主题 → 转发到客户端
func (h *WebSocketHandler) handleSubscribe(client *Client, topic string) {
    switch {
    case strings.HasPrefix(topic, "market.tick."):
        h.subscribeToRedis(client, topic)
    case strings.HasPrefix(topic, "order.event."):
        h.subscribeToKafka(client, topic)
    }
}
```

### 3.8 第八层：前端（React + TypeScript）

#### 3.8.1 技术栈

- **框架**：React 18 + TypeScript
- **构建**：Vite
- **样式**：TailwindCSS
- **状态管理**：Zustand
- **图表**：TradingView Lightweight Charts / Recharts
- **路由**：React Router v6

#### 3.8.2 核心页面

| 页面 | 功能 | 技术方案 |
|------|------|----------|
| **实时行情看板** | 显示所有连接交易所的实时行情 | TradingView Lightweight Charts |
| **策略编辑器** | 参数表单 + 实时预览 | 动态表单 + 代码编辑器 |
| **订单簿与持仓** | 显示当前持仓和活跃订单 | 实时表格 |
| **回测报告** | 收益曲线、风险指标 | Recharts 图表 |
| **LLM 情感看板** | 各标的实时情感权重 | 热力图/仪表盘 |

#### 3.8.3 与后端通信

```typescript
// WebSocket - 实时行情
const ws = new WebSocket('ws://localhost:8080/ws');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  useTickStore.getState().updateTick(data);
};

// REST API - 配置和历史数据
const response = await fetch('/api/v1/strategies');
const strategies = await response.json();
```

#### 3.8.4 前端状态管理（Zustand）

前端使用 Zustand 进行状态管理，避免 Prop Drilling，支持跨组件状态共享：

```typescript
// stores/tradeStore.ts
import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

interface TradeState {
  // 实时行情
  ticks: Map<string, Tick>;
  // 持仓
  positions: Position[];
  // 活跃订单
  activeOrders: Order[];
  // 连接状态
  wsConnected: boolean;
  
  // Actions
  updateTick: (tick: Tick) => void;
  setPositions: (positions: Position[]) => void;
  addOrder: (order: Order) => void;
  updateOrder: (orderId: string, update: Partial<Order>) => void;
  setWsConnected: (connected: boolean) => void;
}

export const useTradeStore = create<TradeState>()(
  subscribeWithSelector((set, get) => ({
    ticks: new Map(),
    positions: [],
    activeOrders: [],
    wsConnected: false,
    
    updateTick: (tick) => {
      set((state) => {
        const newTicks = new Map(state.ticks);
        newTicks.set(tick.symbol, tick);
        return { ticks: newTicks };
      });
    },
    
    setPositions: (positions) => set({ positions }),
    
    addOrder: (order) => {
      set((state) => ({
        activeOrders: [...state.activeOrders, order]
      }));
    },
    
    updateOrder: (orderId, update) => {
      set((state) => ({
        activeOrders: state.activeOrders.map(o =>
          o.id === orderId ? { ...o, ...update } : o
        )
      }));
    },
    
    setWsConnected: (connected) => set({ wsConnected: connected })
  }))
);

// 订阅选择器（性能优化）
// 只订阅特定 symbol 的 tick 变化
export function useTick(symbol: string) {
  return useTradeStore(
    useCallback(
      (state) => state.ticks.get(symbol),
      [symbol]
    )
  );
}
```

#### 3.8.5 WebSocket 自动重连

前端 WebSocket 也需要断线重连机制：

```typescript
// hooks/useWebSocket.ts
import { useEffect, useRef, useCallback } from 'react';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws';
const RECONNECT_DELAY = 3000;  // 3秒
const MAX_RECONNECT_ATTEMPTS = 10;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  
  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
      reconnectCountRef.current = 0;
      useTradeStore.getState().setWsConnected(true);
      
      // 重新订阅之前订阅的主题
      const subscribedTopics = getSubscribedTopics();
      subscribedTopics.forEach(topic => {
        ws.send(JSON.stringify({ action: 'subscribe', topic }));
      });
    };
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      handleMessage(message);
    };
    
    ws.onclose = () => {
      console.log('WebSocket closed');
      useTradeStore.getState().setWsConnected(false);
      wsRef.current = null;
      
      // 自动重连
      if (reconnectCountRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectTimerRef.current = setTimeout(() => {
          reconnectCountRef.current++;
          console.log(`Reconnecting... attempt ${reconnectCountRef.current}`);
          connect();
        }, RECONNECT_DELAY * Math.min(reconnectCountRef.current + 1, 5));
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    wsRef.current = ws;
  }, []);
  
  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
    }
  }, []);
  
  const subscribe = useCallback((topic: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'subscribe', topic }));
    }
  }, []);
  
  const unsubscribe = useCallback((topic: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'unsubscribe', topic }));
    }
  }, []);
  
  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);
  
  return { subscribe, unsubscribe, ws: wsRef.current };
}
```

#### 3.8.6 核心组件架构

```
frontend/src/
├── components/
│   ├── common/              # 通用组件
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Card.tsx
│   │   └── Loading.tsx
│   ├── charts/              # 图表组件
│   │   ├── TradingViewChart.tsx
│   │   ├── PriceChart.tsx
│   │   └── DepthChart.tsx
│   ├── trading/             # 交易相关
│   │   ├── OrderForm.tsx    # 订单表单
│   │   ├── PositionTable.tsx # 持仓表格
│   │   ├── OrderBook.tsx   # 订单簿
│   │   └── TradeHistory.tsx # 成交历史
│   └── layout/              # 布局组件
│       ├── Header.tsx
│       ├── Sidebar.tsx
│       └── Footer.tsx
├── pages/
│   ├── Dashboard/           # 实时行情看板
│   │   ├── index.tsx
│   │   ├── MarketOverview.tsx
│   │   └── WatchList.tsx
│   ├── Strategy/            # 策略管理
│   │   ├── index.tsx
│   │   ├── StrategyList.tsx
│   │   ├── StrategyEditor.tsx
│   │   └── BacktestPanel.tsx
│   ├── Trading/             # 交易界面
│   │   ├── index.tsx
│   │   ├── OrderPanel.tsx
│   │   └── PositionPanel.tsx
│   ├── LLM/                 # LLM 情感看板
│   │   ├── index.tsx
│   │   ├── SentimentHeatmap.tsx
│   │   └── NewsPanel.tsx
│   └── Settings/            # 系统设置
│       └── index.tsx
├── hooks/                   # 自定义 Hooks
│   ├── useWebSocket.ts
│   ├── useTicks.ts
│   └── useApi.ts
├── stores/                  # 状态管理
│   ├── tradeStore.ts
│   ├── strategyStore.ts
│   └── userStore.ts
├── api/                     # API 客户端
│   ├── client.ts
│   ├── market.ts
│   ├── strategy.ts
│   └── order.ts
├── types/                   # TypeScript 类型
│   ├── market.ts
│   ├── strategy.ts
│   └── order.ts
└── utils/                   # 工具函数
    ├── format.ts           # 格式化
    ├── calc.ts            # 计算
    └── validation.ts      # 验证
```

#### 3.8.7 实时行情看板设计

```typescript
// pages/Dashboard/index.tsx
import { useEffect } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useTradeStore } from '@/stores/tradeStore';
import { TradingViewChart } from '@/components/charts/TradingViewChart';
import { WatchList } from './WatchList';
import { MarketOverview } from './MarketOverview';

export function Dashboard() {
  const { subscribe, unsubscribe } = useWebSocket();
  const wsConnected = useTradeStore((state) => state.wsConnected);
  
  useEffect(() => {
    // 订阅所有市场数据
    subscribe('market.tick.*');
    subscribe('order.event.*');
    
    return () => {
      unsubscribe('market.tick.*');
      unsubscribe('order.event.*');
    };
  }, [subscribe, unsubscribe]);
  
  return (
    <div className="flex h-screen bg-gray-100">
      {/* 左侧：自选列表 */}
      <div className="w-64 bg-white border-r">
        <WatchList />
      </div>
      
      {/* 中间：图表 */}
      <div className="flex-1 p-4">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">实时行情</h1>
          <ConnectionStatus connected={wsConnected} />
        </div>
        
        <TradingViewChart 
          symbol="BTCUSDT" 
          exchange="binance"
        />
        
        <MarketOverview className="mt-4" />
      </div>
      
      {/* 右侧：订单簿 */}
      <div className="w-80 bg-white border-l">
        <OrderBook symbol="BTCUSDT" />
      </div>
    </div>
  );
}

// 连接状态指示器
function ConnectionStatus({ connected }: { connected: boolean }) {
  return (
    <div className={`flex items-center gap-2 ${
      connected ? 'text-green-500' : 'text-red-500'
    }`}>
      <div className={`w-2 h-2 rounded-full ${
        connected ? 'bg-green-500' : 'bg-red-500'
      }`} />
      <span className="text-sm">
        {connected ? '已连接' : '断开'}
      </span>
    </div>
  );
}
```

#### 3.8.8 开发状态

| 模块 | 状态 | 说明 |
|------|------|------|
| **项目初始化** | ✅ 已完成 | Vite + React + TS + Tailwind 配置 |
| **状态管理** | ✅ 已完成 | Zustand 配置 |
| **API 客户端** | 🚧 进行中 | REST API 封装 |
| **WebSocket** | 🚧 进行中 | 实时数据推送 |
| **图表组件** | ⏳ 待开发 | TradingView 集成 |
| **看板页面** | ⏳ 待开发 | Dashboard 布局 |
| **策略编辑器** | ⏳ 待开发 | 表单 + 代码编辑 |
| **回测报告** | ⏳ 待开发 | 图表 + 数据展示 |

### 3.9 其他交易所连接器（框架定义）

除了 Binance 和 Polymarket，系统还预留了其他交易所的连接框架：

#### 3.9.1 Tiger 证券（待实现）

```rust
// data-layer/src/connector/tiger.rs

pub struct TigerConnector {
    api_key: String,
    api_secret: String,
    account_id: String,
    state: Arc<AtomicU8>,
}

#[async_trait]
impl Connector for TigerConnector {
    fn id(&self) -> &'static str { "tiger" }
    
    async fn subscribe(
        &self,
        symbols: Vec<Symbol>,
        tick_tx: mpsc::Sender<NormalizedTick>,
    ) -> anyhow::Result<()> {
        // TODO: 实现 Tiger Open API WebSocket 连接
        // 参考: https://www.itigerup.com/openapi/info
        tracing::info!("Tiger connector stub - not yet implemented");
        Ok(())
    }
    
    async fn fetch_snapshot(&self, symbol: &Symbol) -> anyhow::Result<NormalizedTick> {
        anyhow::bail!("Tiger snapshot not yet implemented")
    }
    
    async fn unsubscribe(&self, _symbols: &[Symbol]) -> anyhow::Result<()> {
        Ok(())
    }
    
    fn state(&self) -> ConnectorState {
        ConnectorState::Disconnected
    }
}
```

**Tiger 特点**：
- 支持美股、港股、A股通
- 提供 Open API（WebSocket + REST）
- 需要实名认证和开户
- 支持模拟盘（paper trading）

#### 3.9.2 Trading212（待实现）

```rust
// data-layer/src/connector/trading212.rs

pub struct Trading212Connector {
    api_key: String,
    state: Arc<AtomicU8>,
}

#[async_trait]
impl Connector for Trading212Connector {
    fn id(&self) -> &'static str { "trading212" }
    
    async fn subscribe(
        &self,
        symbols: Vec<Symbol>,
        tick_tx: mpsc::Sender<NormalizedTick>,
    ) -> anyhow::Result<()> {
        // TODO: 实现 Trading212 API 连接
        // 参考: https://t212public-api-docs.redoc.ly/
        tracing::info!("Trading212 connector stub - not yet implemented");
        Ok(())
    }
    
    async fn fetch_snapshot(&self, symbol: &Symbol) -> anyhow::Result<NormalizedTick> {
        anyhow::bail!("Trading212 snapshot not yet implemented")
    }
    
    async fn unsubscribe(&self, _symbols: &[Symbol]) -> anyhow::Result<()> {
        Ok(())
    }
    
    fn state(&self) -> ConnectorState {
        ConnectorState::Disconnected
    }
}
```

**Trading212 特点**：
- 零佣金美股交易
- 提供公开 API
- 欧洲用户为主
- 支持小数股交易

#### 3.9.3 交易所连接器实现状态

| 交易所 | 状态 | 数据接入 | 实盘交易 | 说明 |
|--------|------|----------|----------|------|
| **Binance** | 🚧 开发中 | 基础框架 | 待实现 | 优先实现，流动性最好 |
| **Polymarket** | 🚧 开发中 | 框架定义 | 待实现 | 预测市场特殊处理 |
| **Tiger** | ⏳ 待开发 | 框架定义 | 待实现 | 美股港股支持 |
| **Trading212** | ⏳ 待开发 | 框架定义 | 待实现 | 零佣金欧美市场 |

---

## 四、数据流向总图

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                      外部世界                          │
                    │  ┌──────────┐  ┌──────────┐  ┌─────────────────────┐   │
                    │  │ Binance  │  │Polymarket│  │  新闻/社交媒体       │   │
                    │  │ 交易所   │  │ 预测市场 │  │  Twitter/RSS/新闻    │   │
                    │  └────┬─────┘  └────┬─────┘  └──────────┬──────────┘   │
                    └───────┼─────────────┼──────────────────┼──────────────┘
                            │ WebSocket   │ GraphQL/API      │ HTTP/RSS
                            ▼             ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              数据获取层 (Rust)                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │   Binance   │  │  Polymarket │  │   Tiger     │  │  其他交易所连接器...          │ │
│  │  Connector  │  │  Connector  │  │  Connector  │  │                             │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────────────────────────┘ │
│         │                │                │                                           │
│         └────────────────┴────────────────┘                                           │
│                          │                                                            │
│                          ▼ NormalizedTick                                             │
│                   ┌───────────────┐                                                   │
│                   │  环形缓冲区    │  RingBuffer (无锁 SPSC)                          │
│                   └───────┬───────┘                                                   │
└───────────────────────────┼───────────────────────────────────────────────────────────┘
                            │
                            ▼ Redis Streams / Kafka
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              消息总线 (Redis/Kafka)                                  │
│  Topics:                                                                            │
│    - market.tick.{exchange}.{symbol}    # 实时行情                                   │
│    - strategy.signal.{strategy_id}       # 策略信号                                  │
│    - llm.weight.{symbol}                 # LLM 权重                                  │
│    - risk.command                        # 风控指令                                  │
│    - order.event.{order_id}              # 订单事件                                  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   策略层       │  │    LLM 层      │  │   存储层       │
│  (Python)     │  │   (Python)     │  │  Redis/DB     │
│               │  │               │  │               │
│ ┌───────────┐ │  │ ┌───────────┐ │  │ ┌───────────┐ │
│ │ 策略引擎   │ │  │ │ 新闻聚合器 │ │  │ │ 时序数据库 │ │
│ │ (Tick/Bar)│ │  │ │           │ │  │ │TimescaleDB│ │
│ └─────┬─────┘ │  │ └─────┬─────┘ │  │ └───────────┘ │
│       │       │  │       │       │  │               │
│ ┌─────▼─────┐ │  │ ┌─────▼─────┐ │  │               │
│ │ 信号合成器 │ │  │ │  LLM 模型  │ │  │               │
│ │ (Combinator)│ │  │ │(GPT/Ollama)│ │  │               │
│ └─────┬─────┘ │  │ └─────┬─────┘ │  │               │
└───────┼───────┘  └───────┼───────┘  └───────────────┘
        │                  │
        │  注入 LLM 权重   │
        │ <────────────────┘
        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              风控层 (Go)                                             │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                          风控规则引擎                                          │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐  │  │
│  │  │ 仓位限制     │ │ 日亏损限制   │ │ 最大回撤     │ │        熔断器            │  │  │
│  │  │PositionLimit│ │DailyLoss    │ │MaxDrawdown  │ │    CircuitBreaker       │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                                │
│                          风控通过？ │                                                │
│                        ┌───────────┴───────────┐                                    │
│                        ▼                       ▼                                    │
│                   [是/通过]              [否/拦截]                                   │
│                        │                       │                                    │
└────────────────────────┼───────────────────────┼────────────────────────────────────┘
                         │                       │
                         ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              交易层 (Go)                                             │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           纸面交易 (Paper Trading)                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │   │
│  │  │ 撮合引擎     │  │ 滑点模拟     │  │ 延迟模拟     │  │  账户/持仓管理       │ │   │
│  │  │MatchingEngine│  │Slippage     │  │Latency      │  │  Account Manager    │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           实盘交易 (Live Trading)                            │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │   │
│  │  │ OMS 订单管理  │  │ 交易所适配器 │  │ 成交回报处理 │  │  钱包集成 (MetaMask) │ │   │
│  │  │ Order Mgmt   │  │ Adapters     │  │ Fill Handler│  │  Wallet Integration│ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                                │
│                                    ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                           订单生命周期                                         │   │
│  │  pending → submitted → partial_filled → filled / cancelled / rejected        │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼ 订单执行
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
           ┌──────────────┐                 ┌──────────────┐
           │   交易所 API  │                 │   区块链     │
           │  (Binance等) │                 │  (MetaMask) │
           └──────────────┘                 └──────────────┘
```

---

## 五、目录结构

```
Crazytra/
├── README.md                      # 项目说明
├── Makefile                       # 构建脚本
├── .env.example                   # 环境变量示例
│
├── infra/                         # 基础设施 (Docker/K8s)
│   ├── docker-compose.yml         # 本地开发环境
│   ├── docker/
│   │   ├── data-layer.Dockerfile
│   │   ├── strategy-layer.Dockerfile
│   │   └── ...
│   └── scripts/
│       └── init_db.sql            # 数据库初始化脚本
│
├── data-layer/                    # 数据获取层 (Rust)
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── connector/
│       │   ├── mod.rs             # Connector trait 定义
│       │   ├── binance.rs         # 币安连接器
│       │   └── polymarket.rs      # Polymarket 连接器
│       ├── buffer/
│       │   └── ring_buffer.rs     # 无锁环形缓冲区
│       ├── bus/
│       │   └── redis_bus.rs       # Redis 消息总线
│       └── transport/
│           └── websocket.rs       # WebSocket 客户端
│
├── strategy-layer/                # 策略层 (Python)
│   ├── pyproject.toml
│   └── strategy_layer/
│       ├── __init__.py
│       ├── main.py                # 入口
│       ├── base.py                # Strategy 基类
│       ├── combinator.py          # 信号合成器
│       ├── runner.py              # 策略执行引擎
│       ├── registry.py            # 策略注册表
│       ├── backtest/              # 回测引擎
│       │   ├── engine.py
│       │   └── report.py
│       └── strategies/            # 策略实现
│           ├── moving_average.py
│           └── rsi_strategy.py
│
├── llm-layer/                     # LLM 层 (Python)
│   ├── pyproject.toml
│   └── llm_layer/
│       ├── __init__.py
│       ├── main.py
│       ├── providers/             # LLM 提供商适配器
│       │   ├── openai.py
│       │   ├── anthropic.py
│       │   └── ollama.py
│       ├── news/                  # 新闻聚合器
│       │   ├── aggregator.py
│       │   └── filters.py
│       └── analyzer.py            # 情感分析引擎
│
├── risk-engine/                   # 风控层 (Go)
│   ├── go.mod
│   └── src/
│       ├── main.go
│       ├── rules/
│       │   ├── position_limit.go
│       │   ├── daily_loss.go
│       │   ├── max_drawdown.go
│       │   └── circuit_breaker.go
│       ├── engine.go
│       └── config.go
│
├── trading-layer/                 # 交易层 (Go)
│   ├── go.mod
│   └── src/
│       ├── main.go
│       ├── paper/                 # 纸面交易
│       │   ├── matching_engine.go
│       │   └── account.go
│       ├── oms/                   # 订单管理系统
│       │   ├── order.go
│       │   └── position.go
│       ├── live/                  # 实盘交易
│       │   └── adapters/
│       └── bridge.go              # Kafka 双写桥接
│
├── api-gateway/                   # API 网关 (Go)
│   ├── go.mod
│   └── src/
│       ├── main.go
│       ├── handlers/
│       │   ├── market.go
│       │   ├── strategy.go
│       │   ├── order.go
│       │   └── websocket.go
│       ├── middleware/
│       │   ├── auth.go            # JWT 认证
│       │   └── ratelimit.go     # 限流
│       └── router.go
│
└── frontend/                      # 前端 (React + TS)
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── components/            # 通用组件
        ├── pages/                 # 页面
        │   ├── Dashboard.tsx    # 实时行情看板
        │   ├── StrategyEditor.tsx # 策略编辑器
        │   ├── Positions.tsx    # 持仓管理
        │   ├── Backtest.tsx     # 回测报告
        │   └── LLMDashboard.tsx # LLM 情感看板
        ├── stores/                # Zustand 状态管理
        └── api/                   # API 客户端
```

---

## 六、开发路线图

### 第一阶段：核心链路打通 (MVP)

**目标**：验证整个系统架构，打通从数据获取到交易执行的完整链路。

| 任务 | 优先级 | 预计工期 |
|------|--------|----------|
| 搭建基础设施 (Docker Compose) | P0 | 1 天 |
| 实现 Binance 连接器 | P0 | 3 天 |
| 搭建 Redis 消息总线 | P0 | 1 天 |
| 实现均线交叉策略 | P0 | 2 天 |
| 实现纸面交易撮合引擎 | P0 | 3 天 |
| 搭建基础 API 网关 | P0 | 2 天 |
| 实现基础前端看板 | P1 | 3 天 |
| **MVP 联调测试** | P0 | 2 天 |

**阶段成果**：系统可以接收 Binance 实时数据，执行简单策略，进行纸面交易。

### 第二阶段：策略与回测

| 任务 | 优先级 | 预计工期 |
|------|--------|----------|
| 实现信号合成器 | P1 | 3 天 |
| 实现回测引擎 | P1 | 5 天 |
| 添加 RSI、MACD 等策略 | P1 | 3 天 |
| 策略热重载功能 | P2 | 2 天 |
| 回测报告可视化 | P1 | 3 天 |

### 第三阶段：LLM 智能增强

| 任务 | 优先级 | 预计工期 |
|------|--------|----------|
| 新闻聚合器 | P1 | 3 天 |
| Ollama 本地模型集成 | P1 | 2 天 |
| GPT-4o 在线模型集成 | P1 | 2 天 |
| 情感分析引擎 | P1 | 3 天 |
| 权重注入策略层 | P1 | 2 天 |
| LLM 情感看板 | P2 | 2 天 |

### 第四阶段：风控与实盘

| 任务 | 优先级 | 预计工期 |
|------|--------|----------|
| 实现完整风控规则 | P0 | 5 天 |
| 熔断器状态持久化 | P1 | 2 天 |
| Binance 实盘适配器 | P0 | 3 天 |
| MetaMask 钱包集成 | P1 | 3 天 |
| 交易风控测试 | P0 | 3 天 |

### 第五阶段：完善与优化

| 任务 | 优先级 | 预计工期 |
|------|--------|----------|
| Polymarket 连接器实现 | P2 | 5 天 |
| Trading212 连接器 | P2 | 3 天 |
| Kafka 迁移（可选） | P2 | 5 天 |
| 前端 UI/UX 优化 | P2 | 5 天 |
| 性能优化与压力测试 | P2 | 5 天 |
| 文档完善 | P2 | 3 天 |

---

## 七、关键技术实现

### 7.1 数据层 - WebSocket 断线重连

```rust
pub struct ReconnectConfig {
    pub max_attempts: u32 = 10,
    pub base_delay_ms: u64 = 100,
    pub max_delay_ms: u64 = 30000,
    pub jitter_percent: f64 = 0.1,
}

pub async fn connect_with_retry(
    url: &str,
    config: &ReconnectConfig,
) -> Result<WebSocketStream, Error> {
    for attempt in 0..config.max_attempts {
        match connect_async(url).await {
            Ok((ws, _)) => {
                info!("WebSocket connected after {} attempts", attempt + 1);
                return Ok(ws);
            }
            Err(e) => {
                let delay = calculate_backoff(attempt, config);
                warn!("Connection failed (attempt {}), retrying in {}ms: {}", 
                      attempt + 1, delay, e);
                sleep(Duration::from_millis(delay)).await;
            }
        }
    }
    Err(Error::MaxRetriesExceeded)
}

fn calculate_backoff(attempt: u32, config: &ReconnectConfig) -> u64 {
    let base = config.base_delay_ms * 2_u64.pow(attempt.min(10));  // 指数退避
    let capped = base.min(config.max_delay_ms);  // 上限限制
    let jitter = (capped as f64 * config.jitter_percent * rand::random::<f64>()) as u64;
    capped + jitter  // 添加随机抖动
}
```

### 7.2 策略层 - 热重载实现

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import importlib

class StrategyReloadHandler(FileSystemEventHandler):
    def __init__(self, runner: StrategyRunner):
        self.runner = runner
    
    def on_modified(self, event):
        if event.src_path.endswith('.py'):
            strategy_name = Path(event.src_path).stem
            self.reload_strategy(strategy_name)
    
    def reload_strategy(self, name: str):
        try:
            # 1. 卸载旧策略
            old_strategy = self.runner.strategies.get(name)
            if old_strategy:
                old_strategy.stop()
            
            # 2. 重新加载模块
            module = importlib.import_module(f'strategies.{name}')
            importlib.reload(module)
            
            # 3. 实例化新策略
            new_strategy = module.Strategy(self.runner.config)
            
            # 4. 替换并启动
            self.runner.strategies[name] = new_strategy
            new_strategy.start()
            
            logger.info(f"Hot reloaded strategy: {name}")
        except Exception as e:
            logger.error(f"Failed to reload {name}: {e}")
```

### 7.3 风控层 - 熔断器实现

```go
type CircuitState int

const (
    StateClosed CircuitState = iota    // 正常
    StateOpen                           // 熔断
    StateHalfOpen                       // 半开
)

type CircuitBreaker struct {
    state               CircuitState
    consecutiveFailures int
    lastFailureTime     time.Time
    
    FailureThreshold  int           // 失败阈值
    RecoveryTimeout   time.Duration // 恢复超时
    HalfOpenMaxCalls  int           // 半开测试调用数
    
    mutex sync.RWMutex
}

func (cb *CircuitBreaker) Execute(fn func() error) error {
    // 1. 检查状态
    if err := cb.canExecute(); err != nil {
        return err  // 熔断中，直接拒绝
    }
    
    // 2. 执行业务函数
    err := fn()
    
    // 3. 记录结果
    cb.recordResult(err)
    
    return err
}

func (cb *CircuitBreaker) canExecute() error {
    cb.mutex.RLock()
    defer cb.mutex.RUnlock()
    
    switch cb.state {
    case StateClosed:
        return nil  // 正常执行
        
    case StateOpen:
        if time.Since(cb.lastFailureTime) > cb.RecoveryTimeout {
            // 超时后转为半开
            cb.mutex.RUnlock()
            cb.mutex.Lock()
            cb.state = StateHalfOpen
            cb.consecutiveFailures = 0
            cb.mutex.Unlock()
            cb.mutex.RLock()
            return nil
        }
        return errors.New("circuit breaker open")
        
    case StateHalfOpen:
        if cb.consecutiveFailures >= cb.HalfOpenMaxCalls {
            return errors.New("circuit breaker half-open, max calls reached")
        }
        return nil
    }
    
    return nil
}

func (cb *CircuitBreaker) recordResult(err error) {
    cb.mutex.Lock()
    defer cb.mutex.Unlock()
    
    if err != nil {
        cb.consecutiveFailures++
        cb.lastFailureTime = time.Now()
        
        if cb.state == StateHalfOpen || cb.consecutiveFailures >= cb.FailureThreshold {
            cb.state = StateOpen
        }
    } else {
        if cb.state == StateHalfOpen {
            // 测试成功，关闭熔断
            cb.state = StateClosed
            cb.consecutiveFailures = 0
        }
    }
    
    // 持久化到 Redis
    cb.persistState()
}
```

### 7.4 交易层 - Kafka 双写桥接

```go
// 策略信号和订单事件需要同时写入 Redis（实时消费）和 Kafka（持久审计）
type DualWriteBridge struct {
    redisClient *redis.Client
    kafkaWriter *kafka.Writer
}

func (b *DualWriteBridge) PublishEvent(ctx context.Context, event *TradingEvent) error {
    // 1. 序列化
    data, err := json.Marshal(event)
    if err != nil {
        return err
    }
    
    // 2. 写入 Redis（实时消费，< 1ms）
    redisErr := b.redisClient.XAdd(ctx, &redis.XAddArgs{
        Stream: event.Topic,
        Values: map[string]interface{}{
            "data": string(data),
            "ts":   time.Now().UnixNano(),
        },
    }).Err()
    
    // 3. 异步写入 Kafka（持久审计）
    kafkaErr := b.kafkaWriter.WriteMessages(ctx, kafka.Message{
        Topic: event.Topic,
        Key:   []byte(event.ID),
        Value: data,
    })
    
    // 4. 错误处理
    if redisErr != nil {
        return fmt.Errorf("redis write failed: %w", redisErr)
    }
    if kafkaErr != nil {
        // Kafka 失败不阻断，记录日志
        logger.Warn("kafka write failed", zap.Error(kafkaErr))
    }
    
    return nil
}
```

### 7.5 Polymarket 连接器详细实现

Polymarket 是基于区块链的预测市场平台，与其他交易所不同，需要特殊的集成方式。

#### 7.5.1 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     Polymarket 数据流                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐         ┌──────────────┐                     │
│  │ Polymarket   │         │  The Graph   │                     │
│  │ CLOB API     │         │  Subgraph    │                     │
│  │ (REST/WebSocket)       │  (GraphQL)   │                     │
│  └──────┬───────┘         └──────┬───────┘                     │
│         │                        │                              │
│         ▼                        ▼                              │
│  ┌──────────────────────────────────────────────┐              │
│  │      PolymarketConnector (Rust)             │              │
│  │  ┌─────────────┐    ┌────────────────────┐  │              │
│  │  │ CLOB Client │    │ Subgraph Client    │  │              │
│  │  │ - 订单簿轮询 │    │ - 事件监听         │  │              │
│  │  │ - 订单操作  │     │ - 结算价格         │  │              │
│  │  └─────────────┘    └────────────────────┘  │              │
│  │                                              │              │
│  │  ┌────────────────────────────────────────┐  │              │
│  │  │      数据标准化层                      │  │              │
│  │  │  - 概率价格 → NormalizedTick           │  │              │
│  │  │  - Yes/No 代币价格转换                  │  │              │
│  │  └────────────────────────────────────────┘  │              │
│  └──────────────────────┬───────────────────────┘              │
│                         │                                       │
│                         ▼ Redis Streams                        │
│                  ┌──────────────┐                              │
│                  │  消息总线     │                              │
│                  └──────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

#### 7.5.2 核心数据结构

```rust
/// Polymarket 市场定义
pub struct PolymarketMarket {
    pub market_id: String,           // 市场唯一标识
    pub condition_id: String,        // 条件ID（用于结算）
    pub slug: String,                // 市场URL标识
    pub outcome_names: Vec<String>,  // ["Yes", "No"] 或其他选项
    pub token_ids: Vec<String>,     // 每个结果的ERC20代币ID
    pub min_tick_size: Decimal,     // 最小价格变动单位（通常为0.01 = 1美分）
    pub min_order_size: Decimal,    // 最小订单金额（通常为1 USDC）
}

/// Polymarket 订单簿（CLOB格式）
pub struct PolymarketOrderBook {
    pub market_id: String,
    pub outcome: String,             // "Yes" 或 "No"
    pub bids: Vec<PolymarketOrder>,  // 买单（买入Yes = 看涨）
    pub asks: Vec<PolymarketOrder>,  // 卖单（卖出Yes = 看跌）
    pub timestamp: u64,
}

pub struct PolymarketOrder {
    pub price: Decimal,              // 0.00 ~ 1.00（表示概率）
    pub size: Decimal,               // USDC金额
    pub side: OrderSide,
    pub owner: String,               // 钱包地址
}
```

#### 7.5.3 价格标准化（关键转换）

Polymarket 的特殊之处在于价格本身就是**概率**（0.00 ~ 1.00），需要转换为标准tick格式：

```rust
impl PolymarketConnector {
    /// 将 Polymarket 订单簿转换为 NormalizedTick
    /// 
    /// 在预测市场中：
    /// - bid_price = Yes 代币的最高买单价格（市场对Yes的估值）
    /// - ask_price = Yes 代币的最低卖单价格
    /// - 隐含概率 = (bid + ask) / 2
    fn normalize_orderbook(
        &self,
        market: &PolymarketMarket,
        orderbook: PolymarketOrderBook,
    ) -> NormalizedTick {
        // 获取最优买卖价
        let best_bid = orderbook.bids.first()  // 最高买价
            .map(|o| o.price)
            .unwrap_or(Decimal::ZERO);
            
        let best_ask = orderbook.asks.first()  // 最低卖价
            .map(|o| o.price)
            .unwrap_or(Decimal::ONE);
        
        // 聚合深度（计算总数量）
        let bid_size: Decimal = orderbook.bids.iter()
            .take(5)  // 前5档
            .map(|o| o.size)
            .sum();
            
        let ask_size: Decimal = orderbook.asks.iter()
            .take(5)
            .map(|o| o.size)
            .sum();
        
        NormalizedTick {
            symbol: Symbol {
                exchange: "polymarket".to_string(),
                base: market.slug.clone(),
                quote: "USDC".to_string(),
                kind: InstrumentKind::PredictionMarket,
            },
            timestamp_ns: orderbook.timestamp * 1_000_000,  // ms → ns
            received_ns: current_timestamp_ns(),
            bid_price: best_bid,      // Yes 代币买价（即市场认为会发生的概率）
            bid_size,
            ask_price: best_ask,      // Yes 代币卖价
            ask_size,
            last_price: (best_bid + best_ask) / Decimal::TWO,  // 中间价
            last_size: Decimal::ZERO, // CLOB不直接提供last trade
            volume_24h: self.get_24h_volume(&market.market_id),
            sequence: None,
        }
    }
}
```

#### 7.5.4 CLOB API 轮询实现

```rust
const CLOB_POLL_INTERVAL: Duration = Duration::from_secs(5);

impl PolymarketConnector {
    async fn poll_clob_loop(
        &self,
        markets: Vec<PolymarketMarket>,
        tick_tx: mpsc::Sender<NormalizedTick>,
    ) -> anyhow::Result<()> {
        let client = reqwest::Client::new();
        
        loop {
            for market in &markets {
                // 1. 获取订单簿
                let url = format!(
                    "https://clob.polymarket.com/book/{}?side=all",
                    market.condition_id
                );
                
                let response = client
                    .get(&url)
                    .header("POLYMARKET_API_KEY", self.clob_api_key.as_deref().unwrap_or(""))
                    .timeout(Duration::from_secs(10))
                    .send()
                    .await?;
                
                if !response.status().is_success() {
                    tracing::warn!("CLOB API error: {}", response.status());
                    continue;
                }
                
                let orderbook: PolymarketOrderBookResponse = response.json().await?;
                
                // 2. 转换为内部格式
                let tick = self.normalize_orderbook(market, orderbook.into());
                
                // 3. 发送到消息总线
                if tick_tx.send(tick).await.is_err() {
                    tracing::error!("Failed to send tick, receiver dropped");
                    return Ok(());
                }
            }
            
            tokio::time::sleep(CLOB_POLL_INTERVAL).await;
        }
    }
}
```

#### 7.5.5 The Graph 集成（链上数据）

```rust
/// 通过 The Graph 获取链上事件
const POLYMARKET_SUBGRAPH_URL: &str = 
    "https://api.thegraph.com/subgraphs/name/polymarket/polymarket";

/// GraphQL 查询：获取市场结算结果
const MARKET_RESOLVED_QUERY: &str = r#"
query GetMarketResolution($conditionId: String!) {
    condition(id: $conditionId) {
        id
        resolved
        resolutionTimestamp
        payoutNumerators
        payoutDenominator
    }
}
"#;

impl PolymarketConnector {
    /// 监听市场结算事件（用于最终价格确定）
    async fn subscribe_resolutions(
        &self,
        markets: Vec<PolymarketMarket>,
    ) -> anyhow::Result<()> {
        let client = reqwest::Client::new();
        
        for market in markets {
            let query = json!({
                "query": MARKET_RESOLVED_QUERY,
                "variables": {
                    "conditionId": market.condition_id
                }
            });
            
            let response = client
                .post(POLYMARKET_SUBGRAPH_URL)
                .json(&query)
                .send()
                .await?;
                
            let result: SubgraphResponse = response.json().await?;
            
            if let Some(condition) = result.data.condition {
                if condition.resolved {
                    tracing::info!(
                        market = %market.slug,
                        "Market resolved! Final payout: {:?}",
                        condition.payout_numerators
                    );
                    // 触发结算流程...
                }
            }
        }
        
        Ok(())
    }
}
```

#### 7.5.6 与 MetaMask 集成（实盘交易）

Polymarket 交易需要通过区块链钱包（如 MetaMask）签名：

```go
// trading-layer/src/live/polymarket_adapter.go

type PolymarketAdapter struct {
    clobAPIKey    string
    clobSecret    string
    walletAddress string
    rpcClient     *ethclient.Client  // 以太坊RPC
}

func (a *PolymarketAdapter) SubmitOrder(order *Order) (*Order, error) {
    // 1. 构造 CLOB 订单
    clobOrder := &CLOBOrder{
        MarketID:  order.Symbol.Base,  // 使用condition_id
        Side:      order.Side,
        Price:     order.Price,         // 0.00 ~ 1.00
        Size:      order.Size,
        TokenID:   a.getTokenID(order.Symbol.Base, "Yes"),
    }
    
    // 2. 签名订单（使用私钥）
    signature, err := a.signOrder(clobOrder)
    if err != nil {
        return nil, fmt.Errorf("failed to sign order: %w", err)
    }
    
    // 3. 提交到 CLOB API
    resp, err := a.submitToCLOB(clobOrder, signature)
    if err != nil {
        return nil, fmt.Errorf("failed to submit to CLOB: %w", err)
    }
    
    // 4. 更新订单状态
    order.ExternalID = resp.OrderID
    order.Status = StatusSubmitted
    
    return order, nil
}
```

#### 7.5.7 特殊考虑事项

| 方面 | 传统交易所 | Polymarket |
|------|-----------|-----------|
| **价格含义** | 资产价格 | 事件发生概率 (0-1) |
| **结算方式** | 可随时平仓 | 事件结算后统一 payout |
| **代币类型** | 同质化代币 | 条件代币（NFT-like） |
| **流动性** | 连续交易 | 离散事件驱动 |
| **手续费** | Maker/Taker | 协议费 0-2% |
| **钱包集成** | API Key | 区块链签名 |

#### 7.5.8 开发状态

- ✅ **框架定义**：`PolymarketConnector` 结构体、接口已实现
- 🚧 **CLOB 轮询**：需要实现具体的HTTP轮询逻辑
- 🚧 **The Graph 集成**：GraphQL 查询客户端待实现
- ⏳ **钱包集成**：MetaMask 签名待实现
- ⏳ **事件监听**：链上结算事件订阅待实现

### 7.6 数据持久化策略

#### 7.6.1 存储分层

```
┌──────────────────────────────────────────────────────────────┐
│                      数据生命周期                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  实时数据（秒级）                                             │
│  ├─ Redis Streams  ← 数据层写入，策略层消费                    │
│  └─ TTL: 1小时                                               │
│                                                              │
│  热数据（小时级）                                             │
│  ├─ TimescaleDB  ← 策略信号、成交记录                        │
│  └─ 保留: 30天                                               │
│                                                              │
│  冷数据（长期）                                               │
│  ├─ PostgreSQL   ← 账户、配置、历史回测                      │
│  └─ 保留: 永久                                               │
│                                                              │
│  归档数据（压缩）                                             │
│  ├─ S3/GCS       ← 原始tick数据压缩归档                      │
│  └─ 保留: 5年                                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 7.6.2 TimescaleDB 表设计

```sql
-- 行情数据表（超表）
CREATE TABLE market_ticks (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    bid_price DECIMAL(18,8),
    ask_price DECIMAL(18,8),
    bid_size DECIMAL(18,8),
    ask_size DECIMAL(18,8),
    volume_24h DECIMAL(18,8),
    PRIMARY KEY (time, symbol, exchange)
);

-- 转换为超表，按天分区
SELECT create_hypertable('market_ticks', 'time', chunk_time_interval => INTERVAL '1 day');

-- 创建索引
CREATE INDEX idx_market_ticks_symbol ON market_ticks (symbol, time DESC);

-- 信号记录表
CREATE TABLE strategy_signals (
    time TIMESTAMPTZ NOT NULL,
    strategy_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT,  -- long/short/exit
    strength DECIMAL(5,4),
    confidence DECIMAL(5,4),
    executed BOOLEAN DEFAULT FALSE,
    metadata JSONB
);
SELECT create_hypertable('strategy_signals', 'time');

-- 自动数据保留策略：删除30天前的数据
SELECT add_retention_policy('market_ticks', INTERVAL '30 days');
```

### 7.7 测试策略

#### 7.7.1 单元测试

**Rust 数据层**：

```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_ring_buffer() {
        let mut buffer = RingBuffer::<i32>::new(1024);
        
        // 写入
        buffer.push(1);
        buffer.push(2);
        buffer.push(3);
        
        // 读取
        assert_eq!(buffer.pop(), Some(1));
        assert_eq!(buffer.pop(), Some(2));
        assert_eq!(buffer.pop(), Some(3));
    }
    
    #[tokio::test]
    async fn test_binance_connector() {
        let connector = BinanceConnector::new(None);
        
        // Mock WebSocket 服务器
        let mock_server = tokio_tungstenite::accept_async(...).await;
        
        // 发送测试数据
        let test_tick = json!({
            "e": "bookTicker",
            "s": "BTCUSDT",
            "b": "43000.00",
            "B": "1.5",
            "a": "43000.50",
            "A": "0.8"
        });
        
        // 验证标准化结果
        let tick = connector.parse_tick(test_tick).await;
        assert_eq!(tick.symbol.base, "BTC");
        assert_eq!(tick.bid_price, dec!(43000.00));
    }
}
```

**Python 策略层**：

```python
import pytest
import pandas as pd
from strategy_layer.strategies.moving_average import MovingAverageCross

class TestMovingAverageCross:
    def test_golden_cross_signal(self):
        """测试金叉买入信号"""
        strategy = MovingAverageCross(fast=5, slow=10)
        
        # 模拟价格数据（快速上穿慢速）
        data = pd.DataFrame({
            'close': [100, 101, 102, 103, 104, 105, 110, 115, 120, 125]
        })
        
        signal = strategy.on_bar(data)
        
        assert signal is not None
        assert signal.direction == 'long'
        assert signal.strength > 0.5
    
    def test_no_signal_when_flat(self):
        """测试横盘时无信号"""
        strategy = MovingAverageCross(fast=5, slow=10)
        
        # 模拟横盘数据
        data = pd.DataFrame({
            'close': [100] * 10
        })
        
        signal = strategy.on_bar(data)
        
        assert signal is None
```

**Go 风控/交易层**：

```go
func TestCircuitBreaker(t *testing.T) {
    cb := &CircuitBreaker{
        FailureThreshold: 3,
        RecoveryTimeout:  5 * time.Second,
        HalfOpenMaxCalls: 2,
    }
    
    // 模拟连续失败
    for i := 0; i < 3; i++ {
        err := cb.Execute(func() error {
            return errors.New("test error")
        })
        assert.NotNil(t, err)
    }
    
    // 验证熔断器已开启
    assert.Equal(t, StateOpen, cb.state)
    
    // 验证新请求被拒绝
    err := cb.Execute(func() error {
        return nil
    })
    assert.Equal(t, "circuit breaker open", err.Error())
}
```

#### 7.7.2 集成测试

```bash
# 运行所有测试
make test

# 分层测试
cd data-layer && cargo test
cd strategy-layer && pytest
cd risk-engine && go test ./...
```

#### 7.7.3 端到端测试

```python
# tests/e2e/test_full_flow.py
import pytest
import asyncio
import redis.asyncio as aioredis

@pytest.mark.asyncio
async def test_full_trading_flow():
    """测试完整交易链路"""
    redis = aioredis.from_url("redis://localhost:6379")
    
    # 1. 发布模拟行情
    await redis.xadd("market.tick.binance.BTCUSDT", {
        "data": json.dumps({
            "symbol": "BTCUSDT",
            "bid_price": "43000",
            "ask_price": "43001"
        })
    })
    
    # 2. 等待策略层处理
    await asyncio.sleep(0.1)
    
    # 3. 验证信号生成
    messages = await redis.xread({"strategy.signal": "0"}, count=1, block=1000)
    assert len(messages) > 0
    
    # 4. 验证风控通过
    # 5. 验证订单提交
    # ...
```

#### 7.7.4 回测验证

```python
# 验证策略在历史数据上的表现
from strategy_layer.backtest.engine import BacktestEngine

def test_strategy_robustness():
    """测试策略鲁棒性"""
    engine = BacktestEngine()
    
    # 使用历史数据回测
    result = engine.run(
        strategy=MovingAverageCross(),
        data=load_historical_data("BTCUSDT", "2023-01-01", "2023-12-31"),
        initial_cash=100000
    )
    
    # 验证关键指标
    assert result.sharpe_ratio > 0.5  # Sharpe > 0.5
    assert result.max_drawdown < 0.3  # 最大回撤 < 30%
    assert result.win_rate > 0.4      # 胜率 > 40%
    assert len(result.trades) > 10     # 至少10笔交易
```

### 7.8 监控与告警

#### 7.8.1 指标采集（Prometheus）

```go
// 定义监控指标
var (
    TickLatency = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name: "data_layer_tick_latency_microseconds",
            Help: "Tick processing latency",
            Buckets: []float64{100, 500, 1000, 5000, 10000},
        },
        []string{"exchange", "symbol"},
    )
    
    SignalCount = prometheus.NewCounterVec(
        prometheus.CounterOpts{
            Name: "strategy_signals_total",
            Help: "Total number of signals generated",
        },
        []string{"strategy_id", "direction"},
    )
    
    OrderFillTime = prometheus.NewHistogram(
        prometheus.HistogramOpts{
            Name: "trading_order_fill_duration_seconds",
            Help: "Order fill duration",
            Buckets: []float64{0.1, 0.5, 1, 2, 5, 10},
        },
    )
    
    CircuitBreakerState = prometheus.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "risk_circuit_breaker_state",
            Help: "Circuit breaker state (0=closed, 1=open, 2=half-open)",
        },
        []string{"rule_name"},
    )
)
```

#### 7.8.2 健康检查

```go
// api-gateway/src/handlers/health.go

func HealthCheck(c *gin.Context) {
    // 检查各层健康状态
    checks := map[string]interface{}{
        "data_layer":     checkDataLayer(),
        "strategy_layer": checkStrategyLayer(),
        "risk_engine":    checkRiskEngine(),
        "trading_layer":  checkTradingLayer(),
        "redis":          checkRedis(),
        "database":       checkDatabase(),
    }
    
    allHealthy := true
    for _, check := range checks {
        if !check.(map[string]interface{})["healthy"].(bool) {
            allHealthy = false
            break
        }
    }
    
    status := http.StatusOK
    if !allHealthy {
        status = http.StatusServiceUnavailable
    }
    
    c.JSON(status, gin.H{
        "status":   map[bool]string{true: "healthy", false: "unhealthy"}[allHealthy],
        "checks":   checks,
        "timestamp": time.Now().Unix(),
    })
}

// 各层健康检查实现
func checkDataLayer() map[string]interface{} {
    // 检查连接器状态
    connectors := dataLayer.GetConnectorHealth()
    unhealthy := 0
    for _, conn := range connectors {
        if conn.State != "connected" {
            unhealthy++
        }
    }
    
    return map[string]interface{}{
        "healthy":     unhealthy == 0,
        "connectors":  len(connectors),
        "unhealthy":   unhealthy,
    }
}
```

#### 7.8.3 日志聚合（ELK / Loki）

```yaml
# 日志配置示例
logging:
  level: INFO
  format: json
  output:
    - stdout
    - file: /var/log/crazytra/app.log
  fields:
    - timestamp
    - level
    - component
    - trace_id
    - message
    - error
  
# 关键日志事件
important_events:
  - signal_generated
  - order_submitted
  - order_filled
  - risk_rule_triggered
  - circuit_breaker_opened
  - connector_disconnected
```

#### 7.8.4 告警规则

```yaml
# 告警配置 alerting.yml
groups:
  - name: crazytra_alerts
    rules:
      # 数据延迟告警
      - alert: DataLatencyHigh
        expr: data_layer_tick_latency_microseconds > 5000
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "数据延迟过高"
          description: "{{ $labels.exchange }} {{ $labels.symbol }} 延迟超过5ms"
      
      # 风控熔断告警
      - alert: CircuitBreakerOpened
        expr: risk_circuit_breaker_state == 1
        for: 0s
        labels:
          severity: critical
        annotations:
          summary: "风控熔断器开启"
          description: "{{ $labels.rule_name }} 熔断器已开启"
      
      # 订单失败率告警
      - alert: OrderFailureRateHigh
        expr: |
          (
            rate(trading_orders_failed_total[5m])
            /
            rate(trading_orders_total[5m])
          ) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "订单失败率过高"
          description: "过去5分钟订单失败率超过10%"
      
      # 服务宕机告警
      - alert: ServiceDown
        expr: up == 0
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "服务宕机"
          description: "{{ $labels.instance }} 服务已停止"
```

#### 7.8.5 监控面板（Grafana）

```json
// dashboard.json 示例
{
  "dashboard": {
    "title": "Crazytra Trading System",
    "panels": [
      {
        "title": "实时延迟",
        "type": "graph",
        "targets": [
          {
            "expr": "avg(data_layer_tick_latency_microseconds) by (exchange)"
          }
        ]
      },
      {
        "title": "信号生成速率",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(strategy_signals_total[1m])"
          }
        ]
      },
      {
        "title": "持仓盈亏",
        "type": "graph",
        "targets": [
          {
            "expr": "trading_position_pnl"
          }
        ]
      },
      {
        "title": "熔断器状态",
        "type": "table",
        "targets": [
          {
            "expr": "risk_circuit_breaker_state"
          }
        ]
      }
    ]
  }
}
```

---

## 八、部署与运维

```bash
# 1. 启动基础设施
cd infra && docker-compose up -d redis timescaledb ollama

# 2. 拉取 Ollama 模型
docker exec trading-ollama ollama pull mistral:7b-instruct-q4_K_M

# 3. 启动各层（分别开多个终端）
cd data-layer     && cargo run
cd strategy-layer && python -m strategy_layer.main
cd llm-layer      && python -m llm_layer.main
cd risk-engine    && go run ./src/main.go
cd trading-layer  && go run ./src/main.go
cd api-gateway    && go run ./src/main.go

# 4. 启动前端
cd frontend && npm run dev
```

### 8.2 生产环境部署

```bash
# 使用 Makefile 一键部署
make up  # 启动所有服务

# 查看日志
make logs
make logs-risk-engine  # 只看风控层

# 运行测试
make test

# 清理环境
make clean
```

### 8.3 监控端点

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:5173 | React 开发服务器 |
| API 网关 | http://localhost:8080 | REST/WebSocket |
| Grafana | http://localhost:3001 | 监控面板 |
| Prometheus | http://localhost:9090 | 指标采集 |
| Redis | localhost:6379 | 消息总线 |
| TimescaleDB | localhost:5432 | 时序数据库 |

---

## 九、API 参考

### 9.1 REST API

#### 行情数据

```http
GET /api/v1/tick/{symbol}
Response: {
  "symbol": "BTCUSDT",
  "bid_price": "43210.50",
  "ask_price": "43211.00",
  "last_price": "43210.75",
  "timestamp": 1699876543000000000
}

GET /api/v1/orderbook/{symbol}?depth=10
Response: {
  "bids": [["43210.50", "1.5"], ...],
  "asks": [["43211.00", "0.8"], ...]
}
```

#### 策略管理

```http
GET /api/v1/strategies
POST /api/v1/strategies/{id}/enable
POST /api/v1/strategies/{id}/disable
POST /api/v1/strategies/{id}/config
```

#### 交易操作

```http
POST /api/v1/orders
Body: {
  "symbol": "BTCUSDT",
  "side": "buy",
  "type": "limit",
  "size": "0.1",
  "price": "43000"
}

GET /api/v1/orders?status=open
DELETE /api/v1/orders/{id}
```

#### 回测

```http
POST /api/v1/backtest
Body: {
  "strategy_id": "ma_cross",
  "symbol": "BTCUSDT",
  "start_date": "2024-01-01",
  "end_date": "2024-06-01",
  "initial_cash": 100000
}

GET /api/v1/backtest/{id}
```

### 9.2 WebSocket 订阅

```javascript
// 连接
const ws = new WebSocket('ws://localhost:8080/ws?token=JWT_TOKEN');

// 订阅行情
ws.send(JSON.stringify({
  action: 'subscribe',
  topic: 'market.tick.binance.BTCUSDT'
}));

// 订阅订单事件
ws.send(JSON.stringify({
  action: 'subscribe',
  topic: 'order.event.*'
}));

// 接收消息
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.topic, data.payload);
};
```

---

## 十、注意事项与最佳实践

### 10.1 安全建议

1. **API 密钥管理**：使用环境变量或 Vault，不要硬编码
2. **JWT 密钥**：生产环境使用强随机密钥，定期轮换
3. **风控优先**：实盘交易前必须经过充分的风控测试
4. **资金隔离**：纸面交易和实盘使用不同的钱包/账户

### 10.2 性能优化

1. **Rust 数据层**：使用 `ring-channel` 无锁队列减少延迟
2. **Go 服务**：合理设置 GOMAXPROCS，利用 goroutine 池
3. **Python 层**：使用 `numba` 加速计算密集型策略
4. **数据库**：TimescaleDB 按时间分区，合理设置 Chunk 大小

### 10.3 调试技巧

1. **日志级别**：开发用 `DEBUG`，生产用 `INFO`
2. **链路追踪**：每个消息携带 `trace_id` 追踪全流程
3. **数据验证**：关键节点验证数据完整性
4. **回测对比**：实盘表现与回测结果定期对比

---

## 十一、贡献指南

### 11.1 提交 Issue

- 使用清晰的标题描述问题
- 提供复现步骤和环境信息
- 附上相关日志和截图

### 11.2 提交 PR

1. Fork 仓库并创建功能分支
2. 编写代码并添加测试
3. 确保 `make test` 通过
4. 提交 PR 并描述变更内容

### 11.3 代码规范

- **Rust**：遵循 `cargo fmt` 和 `cargo clippy`
- **Go**：使用 `gofmt` 和 `golangci-lint`
- **Python**：遵循 PEP8，使用 `black` 格式化
- **TypeScript**：启用严格模式

---

## 十二、多租户 SaaS 架构

### 12.1 多租户部署模式

Crazytra 支持两种部署模式：

1. **单租户模式**（当前）：独立部署，适合个人或单一机构
2. **多租户 SaaS 模式**（扩展）：云端部署，支持多个租户共享基础设施

### 12.2 租户隔离方案

#### 命名空间隔离（推荐）

```
Redis Key: tenant:{tenant_id}:market.tick.btcusdt
Database: tenant_a.positions, tenant_b.positions
Kafka Topic: tenant-a-signals, tenant-b-signals
```

**优点**：
- ✅ 成本效益高
- ✅ 资源利用率高
- ✅ 易于管理
- ✅ 快速扩展

#### 数据库隔离

```sql
-- 每个租户独立 Schema
CREATE SCHEMA tenant_abc123;
CREATE SCHEMA tenant_xyz789;

-- 或使用行级安全策略（RLS）
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON positions
    USING (tenant_id = current_setting('app.tenant_id')::UUID);
```

### 12.3 租户自定义订阅系统

#### 市场订阅

租户可以自由选择订阅的交易所和交易对：

```go
type TenantMarketSubscription struct {
    TenantID     string
    Exchange     string  // binance, polymarket, tiger
    Symbol       string  // BTC-USDT, ETH-USDT
    Status       string  // active, paused
    Config       SubscriptionConfig
}

type SubscriptionConfig struct {
    TickInterval     string  // realtime, 1s, 5s
    DepthLevel       int     // 订单簿深度
    HistoryDays      int     // 历史数据保留
    EnableNotify     bool    // 价格告警
}
```

**配额限制**：
- Free Plan: 10 个交易对
- Starter Plan: 50 个交易对
- Professional Plan: 无限制

#### 策略订阅

租户可以从策略市场选择或创建自定义策略：

**策略类型**：
1. **公开策略**（免费）：社区贡献，开源代码
2. **私有策略**：租户自创，不对外公开
3. **高级策略**（付费）：专业开发，经过回测验证

```go
type TenantStrategySubscription struct {
    TenantID        string
    StrategyID      string
    Parameters      map[string]interface{}  // 自定义参数
    Symbols         []string                // 应用的交易对
    MaxPositionSize decimal.Decimal
}
```

### 12.4 定价模型

| 计划 | 价格 | 市场订阅 | 策略订阅 | 功能 |
|------|------|----------|----------|------|
| **Free** | $0/月 | 10个 | 1个 | 基础功能 |
| **Starter** | $29/月 | 50个 | 3个 | + Telegram |
| **Professional** | $99/月 | 无限 | 10个 | + LLM + 回测 |
| **Enterprise** | 定制 | 无限 | 无限 | + 独立部署 + SLA |

### 12.5 云端部署架构

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  API Gateway    │
                    │  + Auth Service │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌────▼────┐         ┌────▼────┐
   │ Tenant A│         │ Tenant B│         │ Tenant C│
   │ Namespace│        │ Namespace│        │ Namespace│
   └────┬────┘         └────┬────┘         └────┬────┘
        │                    │                    │
   ┌────▼─────────────────────▼────────────────────▼────┐
   │           Shared Infrastructure                     │
   │  Redis | TimescaleDB | Ollama | Kafka              │
   └─────────────────────────────────────────────────────┘
```

**推荐云平台**：
- AWS: ECS + RDS + ElastiCache + MSK
- GCP: GKE + Cloud SQL + Memorystore + Pub/Sub
- Azure: AKS + PostgreSQL + Redis + Event Hubs

**成本估算**（100 租户）：
- 计算资源: $200/月
- 数据库: $150/月
- 缓存: $80/月
- 消息队列: $100/月
- 总计: ~$600/月

### 12.6 认证和授权

#### JWT Token 结构

```json
{
  "sub": "user_123456",
  "tenant_id": "tenant_abc123",
  "role": "admin",
  "permissions": [
    "trade.execute",
    "strategy.manage",
    "reports.view"
  ],
  "plan": "professional",
  "exp": 1700000000
}
```

#### 权限模型

| 角色 | 创建租户 | 管理用户 | 执行交易 | 修改策略 |
|------|----------|----------|----------|----------|
| Super Admin | ✓ | ✓ | ✓ | ✓ |
| Tenant Admin | ✗ | ✓ | ✓ | ✓ |
| Trader | ✗ | ✗ | ✓ | ✓ |
| Viewer | ✗ | ✗ | ✗ | ✗ |

### 12.7 动态数据路由

```go
// 根据租户订阅动态路由数据
func RouteMarketData(tick *MarketTick) {
    // 查询订阅了这个市场的所有租户
    subscriptions := getActiveSubscriptions(tick.Exchange, tick.Symbol)
    
    for _, sub := range subscriptions {
        // 检查配额
        if !checkQuota(sub.TenantID) {
            continue
        }
        
        // 发送到租户的 Redis Stream
        key := fmt.Sprintf("tenant:%s:market.tick.%s.%s", 
            sub.TenantID, tick.Exchange, tick.Symbol)
        
        redis.XAdd(ctx, &redis.XAddArgs{
            Stream: key,
            Values: tick.ToMap(),
        })
    }
}
```

### 12.8 详细文档

完整的多租户架构设计和订阅系统详见：
- `docs/MULTI_TENANT_ARCHITECTURE.md` - 多租户 SaaS 架构设计
- `docs/TENANT_SUBSCRIPTION_SYSTEM.md` - 租户自定义订阅系统

---

## 十三、Telegram Bot 集成

### 13.1 功能概述

Telegram Bot 提供三大核心功能：
1. **实时通知**：订单成交、风险告警、持仓更新
2. **交互命令**：查询账户、持仓、生成报告
3. **自然语言控制**：用人类语言控制交易系统

### 13.2 通知类型

#### 订单通知

```
✅ 订单成交

🟢 BTC-USDT BUY
价格: $67,840.50
数量: 0.1000
成交: 0.1000
订单ID: order_abc123
```

#### 风险告警

```
🚨 风险告警

类型: DAILY_LOSS_LIMIT
级别: CRITICAL
消息: 日损失超过限制
当前值: -5.2%
阈值: -5.0%
```

#### 持仓更新

```
📈 持仓更新

🟢 BTC-USDT LONG
数量: 0.1000
入场价: $67,500.00
当前价: $67,840.50
未实现盈亏: $34.05
```

### 13.3 自然语言命令

支持用人类语言控制交易系统：

```
用户: "查看我的账户状态"
Bot: 💼 账户状态 [显示详情]

用户: "BTC 现在多少钱？"
Bot: 💰 BTC-USDT 实时价格: $67,840.50

用户: "平掉 ETH 的仓位"
Bot: ✅ 已发送平仓指令：ETH-USDT

用户: "暂停所有交易"
Bot: ⏸️ 已暂停所有交易
```

**支持的命令类型**：
- 查询类：账户状态、持仓、价格、盈亏
- 交易控制：平仓、平掉所有、暂停/恢复交易
- 策略控制：启用/禁用策略

### 13.4 技术实现

#### NLP 处理流程

```
用户消息
    ↓
Telegram Bot
    ↓
Ollama LLM（本地 AI）
    ↓
意图解析 + 参数提取
    ↓
执行命令
    ↓
返回结果
```

#### 命令执行

```go
// 通过 Redis Pub/Sub 发送命令
command := map[string]interface{}{
    "action":       "CLOSE_POSITION",
    "symbol":       "BTC-USDT",
    "timestamp_ns": time.Now().UnixNano(),
    "source":       "telegram",
}

redis.Publish(ctx, "trading.command", jsonData)
```

### 13.5 配置

```bash
# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
TELEGRAM_ENABLE=true

# Ollama（用于 NLP）
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M
```

### 13.6 详细文档

- `telegram-bot/README.md` - Telegram Bot 完整文档
- `telegram-bot/QUICKSTART.md` - 快速开始指南
- `telegram-bot/NLP_GUIDE.md` - 自然语言命令指南

---

## 附录：术语表

| 术语 | 说明 |
|------|------|
| **Tick** | 单个市场行情数据（买一卖一最新价） |
| **Bar** | K线数据（OHLCV：开高低收量） |
| **Signal** | 策略产生的交易信号（买/卖/持有） |
| **Position** | 持仓，持有的资产数量 |
| **Slippage** | 滑点，实际成交价与预期的偏差 |
| **Drawdown** | 回撤，从峰值到谷值的跌幅 |
| **Sharpe** | 夏普比率，风险调整后收益 |
| **Circuit Breaker** | 熔断器，连续失败时暂停服务 |
| **OMS** | 订单管理系统（Order Management System） |
| **SPSC** | 单生产者单消费者队列 |

---

**文档版本**：v1.0  
**最后更新**：2024年  
**维护者**：Crazytra Team
