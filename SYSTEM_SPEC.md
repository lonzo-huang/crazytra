# Auto Trading System — AI Development Specification

> **用途**：本文档是给 AI 编程工具（Cursor、GitHub Copilot、Claude Code 等）的完整上下文文档。
> 阅读本文档后，AI 工具应能独立理解整个系统的架构决策、代码风格、集成方式，并按规范生成代码。
>
> **版本**：v1.0 | 基于完整设计对话生成
> **更新原则**：每次新增重大功能或修改架构决策时，同步更新本文档对应章节。

---

## 目录

1. [项目定位与核心目标](#1-项目定位与核心目标)
2. [技术栈选型决策](#2-技术栈选型决策)
3. [系统架构总览](#3-系统架构总览)
4. [数据获取层（Rust）](#4-数据获取层rust)
5. [消息总线（Redis + Kafka）](#5-消息总线redis--kafka)
6. [策略层（Python）](#6-策略层python)
7. [LLM 层（Python）](#7-llm-层python)
8. [风控层（Go）](#8-风控层go)
9. [交易层（Go）](#9-交易层go)
10. [API 网关（Go）](#10-api-网关go)
11. [前端（React + Vite）](#11-前端react--vite)
12. [基础设施](#12-基础设施)
13. [Nautilus Trader 集成规范](#13-nautilus-trader-集成规范)
14. [开源工具替换映射](#14-开源工具替换映射)
15. [编码规范与约定](#15-编码规范与约定)
16. [常见错误与禁止行为](#16-常见错误与禁止行为)

---

## 1. 项目定位与核心目标

### 1.1 系统定位

这是一套**多市场、多策略、LLM 情感增强**的自动交易系统。核心差异化优势：

1. **LLM 情感权重是一等公民**——不是附加功能，而是实时影响每条交易信号强度的核心机制
2. **Polymarket 链上预测市场接入**——支持 CEX（Binance、Tiger）+ DEX（Polymarket）混合交易
3. **纸面交易行为对齐**——纸面交易的滑点、手续费、延迟模拟精度达到生产可信级别

### 1.2 关键架构决策（不可违背）

```
决策 1：语言按职责分工
  Rust  → 数据获取层（延迟敏感，纳秒级）
  Python → 策略层 + LLM 层（快速迭代，AI 生态）
  Go    → 风控层 + 交易层 + API 网关（并发，生产稳定）
  React → 前端（实时 UI）

决策 2：消息总线双轨
  Redis Streams → 实时路径（tick → 策略 → 风控 → 交易）
  Kafka/Redpanda → 审计路径（订单日志、回放）

决策 3：LLM 层独立进程
  LLM 层是独立 Python 进程，通过 Redis llm.weight topic 推送权重向量
  策略层订阅此 topic，无需重启策略即可实时感知权重变化

决策 4：Nautilus Trader 工具级接入（非代码级 fork）
  pip install nautilus_trader 作为依赖引入
  只借用其 DataClient 和 ExecutionClient
  绝不 fork 源码，绝不修改其内部实现
  风控层、LLM 层、Polymarket 全部保持自建

决策 5：纸面/实盘单开关切换
  TRADING_MODE=paper → SimulatedExchange
  TRADING_MODE=live  → 真实交易所
  两种模式下策略代码完全相同，零修改
```

### 1.3 Alpha 来源（指导所有架构取舍）

本系统的 alpha 来自：**LLM 情感信号 × Polymarket 链上数据 × 自定义风控规则**。
任何简化这三点的架构决策都是错误的，即使能减少开发工作量。

---

## 2. 技术栈选型决策

| 层次 | 选型 | 版本要求 | 不选什么 & 原因 |
|------|------|----------|----------------|
| 数据获取 | Rust + tokio | 1.79+ | 不用 Python asyncio（延迟不可控） |
| 消息总线（实时） | Redis Streams | 7.2+ | 不用 RabbitMQ（无 consumer group） |
| 消息总线（审计） | Redpanda | latest | 不用 Kafka（需要 JVM，运维重） |
| 策略层 | Python | 3.11+ | 不用 Cython（失去热重载能力） |
| LLM 本地 | Ollama | latest | 不用 llama.cpp 直接调（无 HTTP API） |
| LLM 云端 | Anthropic claude-sonnet-4-6 / GPT-4o | — | 按需路由，不锁定单一厂商 |
| 风控/交易/网关 | Go | 1.22+ | 不用 Java（GC 停顿影响延迟） |
| 数值计算 | Decimal（Python）/ shopspring/decimal（Go） | — | 绝不用 float64 做金融计算 |
| 前端框架 | Vite + React 18 | — | 不用 Next.js（无 SSR 需求） |
| 前端状态 | Zustand | 4.x | 不用 Redux（样板代码过多） |
| 金融图表 | lightweight-charts | 4.x | 不用 Recharts（非金融场景优化） |
| 时序数据库 | TimescaleDB（pg16） | — | 不用 InfluxDB（SQL 生态更友好） |

---

## 3. 系统架构总览

### 3.1 数据流方向

```
外部市场（Binance / Polymarket / Tiger）
            ↓  WebSocket / REST
     [数据获取层 · Rust]
            ↓  NormalizedTick
     [Redis Streams: market.tick.*]
            ↓                    ↓
  [策略层 · Python]    [LLM 层 · Python]
  on_tick() 计算信号    新闻情感 → 权重向量
            ↓                    ↓
     [Redis: strategy.signal] ← [Redis: llm.weight]
            ↓
     [风控层 · Go]  ← 三态熔断 + Kelly 定仓 + 回撤检查
            ↓  order.command
     [交易层 · Go]  → 纸面撮合 / 实盘执行
            ↓  order.event
     [Redis: order.event + position.update]
            ↓
     [API 网关 · Go]  → WebSocket 推送
            ↓
     [前端 · React]
```

### 3.2 Topic 命名规范

```
market.tick.<exchange>.<symbol>   # 行情 tick，如 market.tick.binance.btcusdt
strategy.signal                   # 策略信号
llm.weight                        # LLM 权重向量
order.command                     # 风控审批后的下单指令
order.event                       # 成交/拒单/取消事件
position.update                   # 持仓变化
risk.alert                        # 风控告警（熔断、超限等）
account.state                     # 账户净值快照
pnl.snapshot                      # P&L 快照（每分钟）
```

### 3.3 目录结构

```
trading-system/
├── .env.example              # 所有环境变量模板
├── Makefile                  # make up/dev/test/logs
├── README.md
├── data-layer/               # Rust crate
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs
│       ├── connector/        # mod.rs + binance.rs + polymarket.rs
│       ├── transport/        # mod.rs (ReconnectingWebSocket)
│       ├── buffer/           # mod.rs (RingBuffer SPSC)
│       └── bus/              # mod.rs (RedisBus)
├── strategy-layer/           # Python package
│   ├── pyproject.toml
│   └── strategy_layer/
│       ├── __init__.py
│       ├── base.py           # Tick, Signal, BaseStrategy ABC
│       ├── registry.py       # @register + StrategyRegistry
│       ├── combinator.py     # SignalCombinator (4 modes)
│       ├── runner.py         # StrategyRunner + HotReloader
│       ├── main.py           # 进程入口
│       ├── strategies/       # 插件目录（热重载监听此目录）
│       │   ├── ma_cross.py
│       │   └── mean_reversion.py
│       └── backtest/
│           └── engine.py     # BacktestEngine
├── llm-layer/                # Python package
│   ├── pyproject.toml
│   └── llm_layer/
│       └── main.py           # 所有 LLM 逻辑（单文件大模块）
├── risk-engine/              # Go module
│   ├── go.mod
│   └── src/
│       ├── main.go
│       ├── models.go
│       ├── circuit_breaker.go
│       ├── position.go
│       ├── pnl.go
│       ├── sizer.go
│       ├── gateway.go
│       ├── state_store.go
│       ├── metrics.go
│       └── publisher.go
├── trading-layer/            # Go module
│   ├── go.mod
│   └── src/
│       ├── main.go
│       ├── models.go
│       ├── orderbook.go
│       ├── slippage.go
│       ├── fees.go
│       ├── matching.go
│       ├── account.go
│       ├── realignment.go
│       └── executor.go
├── api-gateway/              # Go module
│   ├── go.mod
│   └── src/main.go
├── nautilus-core/            # Nautilus 工具级接入（可选模块）
│   ├── requirements.txt      # nautilus_trader==固定版本
│   ├── config.py
│   ├── strategies/           # 继承 nautilus Strategy 的策略版本
│   ├── actors/
│   │   ├── redis_bridge.py   # Nautilus 事件 → Redis
│   │   └── llm_weight_actor.py
│   └── main.py
├── frontend/                 # React + Vite
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── index.css
│       ├── store/tradeStore.ts
│       ├── hooks/
│       │   └── useWebSocket.ts
│       ├── components/
│       │   ├── dashboard/
│       │   ├── strategy/
│       │   ├── alerts/
│       │   └── llm/
│       └── pages/
│           ├── Dashboard.tsx
│           ├── Strategies.tsx
│           ├── Alerts.tsx
│           └── LLMInsights.tsx
└── infra/
    ├── docker-compose.yml
    ├── docker/
    │   ├── Dockerfile.rust
    │   ├── Dockerfile.python
    │   └── Dockerfile.go
    ├── config/prometheus.yml
    └── scripts/init_db.sql
```

---

## 4. 数据获取层（Rust）

### 4.1 核心 Trait 定义

所有数据源必须实现 `Connector` trait，AI 生成新适配器时必须实现以下全部方法：

```rust
// src/connector/mod.rs

#[async_trait]
pub trait Connector: Send + Sync + 'static {
    fn id(&self) -> &'static str;

    async fn subscribe(
        &self,
        symbols: Vec<Symbol>,
        tick_tx: mpsc::Sender<NormalizedTick>,
    ) -> anyhow::Result<()>;

    async fn fetch_snapshot(&self, symbol: &Symbol) -> anyhow::Result<NormalizedTick>;
    async fn unsubscribe(&self, symbols: &[Symbol]) -> anyhow::Result<()>;
    fn state(&self) -> ConnectorState;
}
```

### 4.2 NormalizedTick 数据结构（禁止修改字段名）

```rust
pub struct NormalizedTick {
    pub symbol:       Symbol,
    pub timestamp_ns: u64,      // 交易所原始时间（纳秒）
    pub received_ns:  u64,      // 本地接收时间（纳秒），用于延迟监控
    pub bid_price:    Decimal,  // 必须用 Decimal，禁止 f64
    pub bid_size:     Decimal,
    pub ask_price:    Decimal,
    pub ask_size:     Decimal,
    pub last_price:   Decimal,
    pub last_size:    Decimal,
    pub volume_24h:   Decimal,
    pub sequence:     Option<u64>,  // 用于检测丢包
}
```

### 4.3 WebSocket 重连规范

重连必须实现指数退避（exponential backoff）+ jitter：

```
初始等待: 1s
最大等待: 60s
退避基数: 2.0
Jitter 比例: 0.3（避免惊群效应）
Ping 间隔: 20s
Pong 超时: 5s
```

### 4.4 环形缓冲区规范

- 容量**必须**是 2 的幂（用位掩码代替取模，性能提升约 3×）
- 实现无锁 SPSC（Single Producer Single Consumer）
- 缓冲区满时使用 `push_overwrite`：丢弃最旧数据（实时行情宁可丢旧数据）

### 4.5 Redis 发布格式

写入 Redis 的 JSON 字段名**固定不变**，前端和策略层依赖这些字段：

```json
{
  "symbol": "BTC-USDT",
  "exchange": "binance",
  "timestamp_ns": 1700000000000000000,
  "received_ns": 1700000000000050000,
  "bid": "67840.50",
  "ask": "67841.20",
  "bid_size": "0.5",
  "ask_size": "0.3",
  "last": "67840.80",
  "volume_24h": "28000.5",
  "latency_us": 50
}
```

### 4.6 新增交易所适配器的步骤

1. 在 `src/connector/` 创建新文件，如 `tiger.rs`
2. 实现 `Connector` trait 的全部 4 个方法
3. 在 `src/connector/mod.rs` 中 `pub mod tiger;`
4. 在 `src/main.rs` 中 `registry.register(Arc::new(TigerConnector::new(...)))`
5. **不需要修改其他任何文件**

---

## 5. 消息总线（Redis + Kafka）

### 5.1 两条路径的职责划分

```
Redis Streams（实时路径）：
  - 所有实时 tick 数据
  - 策略信号
  - LLM 权重更新
  - 风控告警
  - 订单命令和事件
  - 延迟要求：< 1ms

Redpanda/Kafka（审计路径）：
  - 订单完整日志（orders-audit）
  - 策略信号历史（strategy-signals-history）
  - 历史 tick 归档（market-ticks-archive，Snappy 压缩）
  - 延迟要求：无，重吞吐量
```

### 5.2 消费者组命名规范

```
risk-signal-cg        风控层消费 strategy.signal
risk-tick-cg          风控层消费 market.tick.*（更新价格缓存）
risk-event-cg         风控层消费 order.event（更新仓位）
trading-cg            交易层消费 order.command
paper-trading-cg      纸面交易层消费
strategy-tick-cg      策略层消费 market.tick.*
strategy-llm-cg       策略层消费 llm.weight
gateway-relay         API 网关中继消费所有 topic
nautilus-llm-cg       Nautilus 集成时 LLM 权重消费（如启用）
```

### 5.3 消费者实现规范

所有消费者必须：
1. 使用 `XREADGROUP` + consumer group（不用 `XREAD`）
2. 处理完消息后批量 `XACK`（不逐条 ACK）
3. 捕获所有异常，不能因单条消息解析失败而中断消费循环
4. `MAXLEN` 使用近似裁剪（`~` 前缀），比精确裁剪快 10 倍

### 5.4 背压处理策略

按优先级分三级：
- **高优先级**（order.*、risk.*）：永不丢弃，背压传导到上游
- **中优先级**（strategy.signal）：满了等待，最多等 500ms
- **低优先级**（market.tick.*）：满了丢弃最旧数据，实时性优先于完整性

---

## 6. 策略层（Python）

### 6.1 BaseStrategy ABC（禁止修改接口签名）

```python
class BaseStrategy(ABC):
    STRATEGY_ID:   ClassVar[str]   # 必须定义
    STRATEGY_NAME: ClassVar[str]   # 必须定义

    @classmethod
    @abstractmethod
    def get_params_schema(cls) -> type[StrategyParams]: ...

    @abstractmethod
    def on_tick(self, tick: Tick) -> list[Signal]: ...
    # on_tick 必须是纯同步，禁止任何 I/O 操作

    @abstractmethod
    def on_order_event(self, event: OrderEvent) -> None: ...

    # 热重载状态迁移接口（子类可选覆盖）
    def export_state(self) -> dict: ...
    def import_state(self, state_dict: dict) -> None: ...
```

### 6.2 新增策略插件的规范

在 `strategy_layer/strategies/` 目录下创建新文件，必须：

1. 定义继承自 `StrategyParams` 的参数类（用 Pydantic，`frozen=True`）
2. 用 `@register` 装饰器注册
3. 定义 `STRATEGY_ID`（全局唯一字符串）和 `STRATEGY_NAME`
4. 实现 `get_params_schema`、`on_tick`、`on_order_event` 三个方法
5. `on_tick` 中禁止 I/O，必须在 1ms 内返回

```python
from strategy_layer.base import BaseStrategy, StrategyParams, Signal, Tick, OrderEvent
from strategy_layer.registry import register
from pydantic import Field

class MyStrategyParams(StrategyParams):
    period: int = Field(default=20, ge=5, le=200)

@register
class MyStrategy(BaseStrategy):
    STRATEGY_ID   = "my_strategy_v1"   # 全局唯一
    STRATEGY_NAME = "我的策略"

    @classmethod
    def get_params_schema(cls): return MyStrategyParams

    def on_tick(self, tick: Tick) -> list[Signal]:
        # 纯计算，无 I/O
        return []

    def on_order_event(self, event: OrderEvent) -> None:
        pass
```

### 6.3 信号合成器模式

支持四种合成模式，通过配置切换：

```python
class CombineMode(str, Enum):
    WEIGHTED_SUM  = "weighted_sum"   # 默认，加权求和
    MAJORITY_VOTE = "majority_vote"  # 多数表决
    UNANIMOUS     = "unanimous"      # 一致同意（最保守）
    VETO          = "veto"           # 任一空头即做空
```

LLM 权重注入接口：
```python
await combinator.update_llm_weights(symbol="BTC-USDT", llm_score=0.6)
# llm_score ∈ [-1.0, 1.0]，正=看涨，负=看跌
# 内部转换为 llm_factor ∈ [0.5, 2.0]，直接乘以策略基础权重
```

### 6.4 热重载规范

`StrategyRunner` 监听 `strategy_layer/strategies/` 目录，文件变更时：
1. 导出旧策略状态（`export_state()`）
2. 停止旧策略
3. `importlib` 重新加载模块
4. 用新类实例化，导入旧状态（`import_state()`）
5. 启动新策略
6. 失败时自动回滚到旧策略

**状态字段规范**（`export_state` 必须包含）：
```python
{
    "position":    str,   # Decimal 序列化为字符串
    "entry_price": str | None,
    "pnl":         str,
    "trade_count": int,
    "extra":       dict   # 策略自定义字段
}
```

### 6.5 回测引擎规范

- 使用事件驱动模式，与实盘共享完全相同的策略代码
- `fill_at="next_open"`：信号在 T 时刻产生，成交在 T+1 时刻，消除前视偏差
- 数据格式：Parquet 文件，列名固定为 `time, symbol, bid, ask, last, bid_size, ask_size, volume_24h`
- 绩效指标必须计算：`total_return, annual_return, sharpe_ratio, sortino_ratio, max_drawdown, calmar_ratio, win_rate, profit_factor`

---

## 7. LLM 层（Python）

### 7.1 三种 Provider 的接入规范

所有 Provider 继承 `BaseProvider`，实现统一接口：

```python
class BaseProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @abstractmethod
    async def complete(self, req: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    def estimate_cost(self, req: LLMRequest) -> float: ...

    def is_healthy(self) -> bool: ...    # 基于错误计数和预算
    def record_error(self) -> None: ...
    def record_success(self, cost: float) -> None: ...
```

**Ollama（本地）**：
- 基础 URL：`http://localhost:11434`
- 强制 JSON 输出：请求体加 `"format": "json"` 字段
- 推荐模型：`mistral:7b-instruct-q4_K_M`（速度/质量最佳平衡）
- 失败重试：`@retry(stop=stop_after_attempt(2), wait=wait_fixed(1))`

**Claude（Anthropic）**：
- 模型：`claude-sonnet-4-6`
- 强制 JSON：在 system prompt 末尾加 `"\n\nOutput ONLY valid JSON."` + assistant prefill `"{"`
- 失败重试：`@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))`

**GPT-4o（OpenAI）**：
- 原生 JSON mode：`"response_format": {"type": "json_object"}`
- 失败重试：同 Claude

### 7.2 路由规则

```python
# 常规情感分析 → Ollama（零成本）
# 重大新闻（importance >= 0.85）→ Claude/GPT-4o（高精度）
# provider 失败 → 自动故障转移到下一个健康 provider
# 相同内容 180s 内不重复调用（ResponseCache）
```

### 7.3 情感分析输出格式（禁止修改）

LLM 必须输出以下 JSON 格式，`SentimentResult` Pydantic 模型校验：

```json
{
  "sentiments": [
    {
      "symbol": "BTC-USDT",
      "score": 0.35,
      "confidence": 0.72,
      "horizon": "short",
      "key_drivers": ["Fed pause expected", "ETF inflows"],
      "risk_events": ["FOMC Thursday"]
    }
  ],
  "market_regime": "risk_on",
  "macro_summary": "一句话宏观判断"
}
```

- `score` ∈ [-1.0, 1.0]：-1=强烈看跌，+1=强烈看涨
- `confidence` ∈ [0.0, 1.0]
- `horizon`：`"short"` (1h) / `"medium"` (1d) / `"long"` (1w)
- `market_regime`：`"risk_on"` / `"risk_off"` / `"neutral"`

### 7.4 权重向量发布到 Redis

发布到 `llm.weight` topic 的消息格式：

```json
{
  "symbol": "BTC-USDT",
  "llm_score": 0.28,
  "confidence": 0.65,
  "horizon": "short",
  "key_drivers": ["..."],
  "risk_events": ["..."],
  "model_used": "ollama/mistral:7b-instruct-q4_K_M",
  "ts_ns": 1700000000000000000,
  "ttl_ms": 300000
}
```

### 7.5 时间衰减融合规范

```
新权重与历史权重做指数衰减融合：
  score = (new×conf_new + Σ old_i×conf_i×decay_i) / Z
  decay_i = exp(-age_s × ln(2) / half_life_s)
  half_life_s = 30分钟（默认，可配置）

策略层实际使用的有效权重：
  effective_score = llm_score × confidence
  （低置信度时自动收缩影响力）
```

### 7.6 新闻聚合规范

- RSS 来源：CoinDesk、CoinTelegraph、CryptoPanic
- NewsAPI：可选，需 NEWSAPI_KEY 环境变量
- 去重：MD5 标题哈希，维护 3000 条历史集合
- 时效过滤：超过 4 小时的新闻不发给 LLM
- 重要性评分：`source_weight + keyword_hits × 0.08`
- 高影响关键词：`fed, fomc, rate, sec, ban, hack, etf, bankruptcy, fraud, acquisition, liquidation`

---

## 8. 风控层（Go）

### 8.1 串行校验链顺序（禁止改变顺序）

```
1. TTL 检查      → 信号是否过期（纳秒级比较，最快）
2. Hold 过滤     → direction="hold" 直接丢弃
3. 熔断器检查    → CircuitBreaker.Allow()
4. 日损限制      → 日亏超过 5% 且非平仓方向
5. 最大回撤      → 当前回撤超过 15% 且非平仓方向
6. 仓位限制      → 单标的仓位超过 NAV 20%
7. 仓位定型      → OrderSizer.Size() 计算下单量
8. 通过 → 发布 order.command
```

顺序设计原则：越快的检查越靠前，减少平均校验耗时。P50 延迟目标 < 5µs。

### 8.2 熔断器三态机规范

```
状态：Closed（正常）→ Open（熔断）→ HalfOpen（探测）→ Closed

触发条件：连续失败 5 次 → Open
冷却时间：60s 后进入 HalfOpen
恢复条件：连续成功 3 次 → Closed
探测失败：立即回到 Open

实现要求：
  - state 用 atomic.Int32（不用 mutex，性能关键路径）
  - 失败计数用 atomic.Int64
  - 所有状态转换用 CAS（CompareAndSwap）
  - 支持 ForceOpen（人工熔断）和 ForceClose（人工恢复）接口
  - 状态持久化到 Redis（服务重启后恢复）
```

### 8.3 Kelly 定仓规范

```go
// Kelly 公式：f* = (p×b - q) / b
// p = confidence（置信度），b = 1 + strength×2（赔率映射）
// q = 1 - p

// Fractional Kelly：kelly × 0.3（保守系数，避免全 Kelly 的极端波动）
// 最终下单量：min(kelly_size, strength × max_position × nav)
```

### 8.4 风控参数（环境变量配置）

```
MAX_POSITION_SIZE=0.20    单仓最大 20% NAV
MAX_DAILY_LOSS=0.05       日损上限 5% 初始 NAV
MAX_DRAWDOWN=0.15         最大回撤 15% 峰值 NAV
MAX_LEVERAGE=1.0          不允许杠杆（可调整）
PAPER_INITIAL_CASH=100000 纸面交易初始资金
```

### 8.5 P&L 监控规范

- 回撤追踪器用 `atomic.Int64`（× 1e8 存储，无锁）
- 每 100ms 刷新一次 NAV 和回撤
- 每 5s 持久化一次状态到 Redis（pipeline 批量写入 5 个 key）
- 每天午夜自动重置日损计数器

### 8.6 平仓方向特殊处理

日损超限和回撤超限时：
- **禁止**拦截 `direction="exit"` 的信号（平仓不应受风控限制）
- **仅拦截** `direction="long"` 和 `direction="short"` 的开仓信号

---

## 9. 交易层（Go）

### 9.1 三层滑点模型（按订单规模自动选择）

```
小单（< $1,000）   → FixedBpsSlippage：0.5bps + ±0.2bps noise
中等单（< $50,000）→ VolumeImpactSlippage：Almgren-Chriss 平方根模型
大单（>= $50,000） → OrderBookImpactSlippage：逐档吃订单簿

自适应模型（AdaptiveSlippage）自动判断并路由
```

### 9.2 手续费模型（Binance 现货分层费率）

```
VIP0（< 50 BTC 月交易量）：maker 0.10%，taker 0.10%
VIP1（< 500 BTC）：         maker 0.09%，taker 0.10%
VIP4（< 4500 BTC）：        maker 0.02%，taker 0.04%
使用 BNB 支付：×0.75 折扣
```

### 9.3 延迟模拟（对数正态分布）

```
Binance 现货：μ=2.5, σ=0.6, RTT=5ms, spike_prob=0.003, spike_max=300ms
Polymarket：  μ=4.0, σ=0.8, RTT=20ms, spike_prob=0.02,  spike_max=2000ms
```

中位数通过 `e^μ + RTT` 计算：Binance ≈ 17ms，Polymarket ≈ 75ms。

### 9.4 Limit 单成交规则（禁止违反）

- Limit 单必须等到**市场价穿越 limit 价**时才成交
- 成交价固定为 limit 价（无额外滑点）
- 手续费使用 maker 费率（比 taker 低）
- IOC：立即成交，否则取消；FOK：全部成交，否则取消

### 9.5 幂等键规范

```go
// 格式：signal_id + "-v1"
// 防止网络超时重试导致重复下单
// 服务重启后 idempKeys 清空（Redis ACK 防止 Redis 侧重复投递）
order.IdempotKey = signal.SignalID + "-v1"
```

### 9.6 行为对齐检查器

`RealignmentChecker` 持续追踪纸面交易的预测滑点 vs 实际滑点：
- 样本窗口：最近 500 笔
- 告警阈值：平均偏差 > 3bps
- 触发告警时输出：`"slippage overestimated/underestimated by X bps — recalibrate SlippageModel"`

---

## 10. API 网关（Go）

### 10.1 REST 接口规范

```
GET  /health                  健康检查，无需认证
GET  /ws                      WebSocket 升级端点
POST /auth/token              获取 JWT（dev 模式用 dev-secret）

GET  /api/v1/strategies       策略列表
POST /api/v1/strategies/:id/params  更新策略参数（触发热重载）
GET  /api/v1/orders           历史订单（默认最近 100 条）
GET  /api/v1/alerts           风控告警（默认最近 50 条）
GET  /api/v1/weights          最新 LLM 权重（每个 symbol 最新一条）
GET  /api/v1/ticks/:symbol    最新 tick（:symbol 如 BTCUSDT）
GET  /api/v1/pnl              P&L 快照
GET  /metrics                 Prometheus 指标（无需认证）
```

### 10.2 WebSocket 消息格式

所有推送消息包含 `_topic` 字段，前端据此路由：

```json
{
  "_topic": "market.tick.binance.btcusdt",
  "_id": "1700000000000-0",
  "symbol": "BTC-USDT",
  ...其他字段
}
```

### 10.3 CORS 配置

```
AllowOrigins: ["http://localhost:5173", "http://localhost:3000"]
AllowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
AllowHeaders: ["Origin", "Authorization", "Content-Type"]
AllowCredentials: true
```

---

## 11. 前端（React + Vite）

### 11.1 Zustand Store 结构（禁止修改 key 名）

```typescript
interface TradeStore {
  wsStatus:     'connecting' | 'connected' | 'disconnected'
  ticks:        Record<string, Tick>        // key = symbol
  tickHistory:  Record<string, Tick[]>      // 最近 500 条
  signals:      Signal[]                    // 最近 500 条
  orders:       OrderEvent[]                // 最近 1000 条
  alerts:       RiskAlert[]                 // 最近 200 条
  weights:      Record<string, LLMWeight>   // key = symbol
  pnl:          PnLSnapshot
  equityHistory: {ts: number; nav: number}[] // 最近 1440 点（24h）
}
```

### 11.2 WebSocket 自动重连规范

```
指数退避：1s → 2s → 4s → ... → max 30s
重连后自动恢复订阅状态
状态显示：'connecting'（黄点）/ 'connected'（绿点）/ 'disconnected'（红点）
```

### 11.3 页面结构

```
/           Dashboard：实时 tick 卡片 + 净值曲线 + 信号流 + 订单簿
/strategies Strategies：策略列表 + 参数编辑器 + 信号合成器配置 + 回测绩效
/alerts     Alerts：风控告警流 + 熔断器状态 + 风控仪表盘 + 限制配置
/llm        LLM Insights：情感权重条 + 驱动因素标签 + 新闻列表
```

### 11.4 金融数字显示规范

```typescript
// 价格：始终使用 Decimal 字符串解析，不用 parseFloat 做精度关键计算
const price = new Decimal(tick.bid)

// 显示精度：
//   BTC/ETH 价格：小数点后 2 位
//   小币种：视情况 4-6 位
//   百分比：2 位
//   P&L 金额：2 位（带 + 号前缀表示盈利）

// 颜色规范：
//   盈利/上涨：text-green-400 / var(--green)
//   亏损/下跌：text-red-400   / var(--red)
//   中性：     text-gray-400  / var(--text1)
```

### 11.5 图表规范

- K 线图和深度图：使用 `lightweight-charts`，不用 Recharts
- 净值曲线：Recharts `LineChart`（已有依赖，无需额外引入）
- Sparkline（tick 卡片内小图）：纯 SVG `<polyline>`，不引入额外库

---

## 12. 基础设施

### 12.1 环境变量完整列表

```bash
# 消息总线
REDIS_URL=redis://localhost:6379
KAFKA_BROKERS=localhost:9092

# 数据库
DATABASE_URL=postgresql://trader:trader@localhost:5432/trading
TIMESCALE_URL=postgresql://trader:trader@localhost:5432/market_data

# 交易所
BINANCE_API_KEY=
BINANCE_SECRET=
TIGER_ACCESS_TOKEN=
TRADING212_API_KEY=

# LLM
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M
NEWSAPI_KEY=

# 交易配置
TRADING_MODE=paper            # paper | live
PAPER_INITIAL_CASH=100000
LEVERAGE=1                    # 默认不使用杠杆

# 风控参数
MAX_POSITION_SIZE=0.20
MAX_DAILY_LOSS=0.05
MAX_DRAWDOWN=0.15

# 服务配置
API_PORT=8080
JWT_SECRET=change_me_in_production
LLM_INTERVAL_S=300            # LLM 分析间隔（秒）
BREAKING_THRESHOLD=0.85       # 重大新闻触发阈值

# 前端
VITE_API_URL=http://localhost:8080
VITE_WS_URL=ws://localhost:8080
```

### 12.2 TimescaleDB 表结构规范

关键表（`infra/scripts/init_db.sql` 中定义）：

```sql
-- market_ticks：时序数据，按天分区，7天后压缩，90天后删除
-- strategy_signals：策略信号历史
-- orders：订单记录（含 paper/live 模式标记）
-- llm_weights：LLM 权重历史（用于事后分析预测准确性）
-- risk_alerts：风控告警历史

-- 连续聚合视图：ticks_1m（1分钟 OHLCV，实时更新）
```

### 12.3 Makefile 目标

```makefile
make up          # 构建所有镜像并启动全部服务
make down        # 停止所有服务
make dev         # 只启动 Redis + TimescaleDB + Ollama（本地开发模式）
make pull-model  # 拉取 Ollama 模型
make logs        # 尾随所有服务日志
make logs-xxx    # 尾随指定服务日志
make test        # 运行所有测试
make clean       # 删除所有容器和卷
make dev-token   # 生成开发用 JWT token
```

---

## 13. Nautilus Trader 集成规范

### 13.1 集成模式（工具级，非代码级）

**核心原则：`pip install nautilus_trader`，绝不 fork 源码。**

```
# requirements.txt 中固定到 patch 版本
nautilus_trader==1.204.0
```

升级流程：
1. 隔离环境测试新版本
2. 跑回测对比（绩效必须完全一致）
3. dry-run 24h 验证事件格式
4. 升级生产环境

### 13.2 三种用法（按需选择）

**用法 A（最轻量）**：只借 DataClient，推入自己的 Redis
```python
# 用 Nautilus 的 BinanceHttpClient / BinanceWebSocketClient
# 数据出来后立即转换为 NormalizedTick 格式推入 Redis
# 策略层、风控层、LLM 层对此完全透明
```

**用法 B（中量）**：只借 BacktestEngine 做严格回测验证
```python
# 用 Nautilus 的 BacktestEngine 验证策略
# 利用其"回测=实盘"特性消除前视偏差
# 实盘仍用自建方案
```

**用法 C（完整）**：Nautilus 作为实盘执行层，通过 Actor 保留自建的 LLM 和风控
```python
# RedisBridgeActor：Nautilus 事件 → Redis（前端和 API 网关不变）
# LLMWeightActor：Redis llm.weight → 策略 update_llm_weight()
# 自建 Go 风控层通过 Redis 请求-响应模式与 Nautilus 集成
```

### 13.3 RedisBridgeActor 发布格式

Actor 向 Redis 写入的消息格式必须与非 Nautilus 路径完全相同，确保前端和 API 网关代码零修改。
参考 `nautilus-core/actors/redis_bridge.py` 中的 `on_quote_tick` 和 `_forward_order_event` 方法。

### 13.4 Nautilus 特有注意事项

- 标的 ID 格式：`BTCUSDT.BINANCE`（非 `BTC-USDT`），需要在 Actor 中转换
- 时间戳：Nautilus 使用 `ts_event`（交易所时间）和 `ts_init`（本地接收时间），对应 `timestamp_ns` 和 `received_ns`
- 数量类型：`Quantity` 对象，需要 `str()` 转换后用 Decimal 解析
- 价格类型：`Price` 对象，同上

---

## 14. 开源工具替换映射

以下开源工具可以替换对应的自建模块，按需选用：

| 自建模块 | 可替换工具 | 替换收益 | 损失的能力 |
|---------|----------|---------|---------|
| Rust 数据层 | cryptofeed | 更多交易所，少写 2-4 周代码 | 极致延迟优化能力 |
| 策略层框架 | Freqtrade | 开箱即用，社区活跃 | LLM 原生集成、Polymarket |
| 回测引擎 | Nautilus BacktestEngine | 前视偏差从架构层消除 | 无（可叠加使用） |
| Kafka | Redpanda | 无 JVM，低延迟，兼容 Kafka 客户端 | 无（完全透明替换） |
| Go API 网关 | FastAPI | Python 栈统一，减少跨语言 | Go 的并发性能上限 |
| 监控看板 | Grafana | 零前端开发，模板丰富 | 定制化程度 |
| 新闻数据 | OpenBB | 免费，支持 100+ 数据源 | 无（额外补充） |

**绝对不替换的模块（核心差异化）**：
- LLM 层的权重注入机制
- Polymarket 接入能力
- Go 风控层的三态熔断 + Kelly 定仓

---

## 15. 编码规范与约定

### 15.1 通用规范

```
金融计算：
  Python → 使用 decimal.Decimal，禁止 float
  Go     → 使用 github.com/shopspring/decimal
  Rust   → 使用 rust_decimal crate
  原因：0.1 + 0.2 ≠ 0.3（float），金融计算必须用定点数

错误处理：
  Python → 业务错误用自定义异常，记录结构化日志（structlog）
  Go     → 所有错误向上传递，main 层统一处理
  Rust   → anyhow::Result，使用 ? 操作符

日志：
  Python → structlog，JSON 格式，包含 strategy/symbol/signal_id 等 context
  Go     → zap，JSON 格式
  Rust   → tracing，env-filter 控制级别

并发：
  Python → asyncio，不用 threading（GIL 问题）
  Go     → goroutine + channel，不过度使用 mutex
  Rust   → tokio async，atomic 优先于 mutex
```

### 15.2 Rust 特定规范

- 所有 WebSocket 连接必须有断线重连逻辑（见 `transport/mod.rs`）
- 环形缓冲区容量必须是 2 的幂
- 金融数据全部用 `rust_decimal::Decimal`
- 每个 `Connector` 实现都必须有 `AtomicU8` 状态追踪（0=断开, 1=连接中, 2=已连接）

### 15.3 Python 特定规范

- 策略类参数必须用 Pydantic + `frozen=True`
- `on_tick` 方法严格禁止 I/O（会阻塞事件循环）
- 所有时间戳使用纳秒整数（`time.time_ns()`）
- Decimal 序列化到 JSON 时转换为字符串（`str(decimal_value)`）

### 15.4 Go 特定规范

- 风控层所有状态字段优先使用 `atomic`，避免 mutex 成为热点
- Redis 操作使用 pipeline 批量执行
- `context.Context` 贯穿所有服务，支持优雅退出
- 服务停止时最后一次 `Persist()` 持久化状态

### 15.5 TypeScript/React 特定规范

- 所有金融数字用 `string` 类型传输，前端显示时用 `parseFloat(x).toFixed(2)`
- WebSocket 消息解析失败必须 `catch` 并忽略（不能因为一条坏消息崩溃）
- Zustand store 的 action 函数必须是纯函数（不直接调用 API）
- 颜色只用 CSS 变量（支持暗色模式），不硬编码十六进制

---

## 16. 常见错误与禁止行为

### 16.1 架构级禁止事项

```
❌ 禁止：在 on_tick() 中做任何 I/O（网络请求、Redis 读写、文件操作）
✅ 正确：on_tick 纯计算，I/O 在 Actor/Consumer 中异步完成

❌ 禁止：用 float64/float32 做价格计算
✅ 正确：全程 Decimal

❌ 禁止：fork Nautilus 源码
✅ 正确：pip install，通过公开 API 扩展

❌ 禁止：在风控层拦截 direction="exit" 的信号
✅ 正确：日损/回撤超限时只拦截开仓，平仓永远放行

❌ 禁止：策略层直接调用交易所 API
✅ 正确：策略层只产生 Signal，通过 Redis → 风控 → 交易层执行

❌ 禁止：纸面交易允许负 cash（穿仓）
✅ 正确：触发清算时 cash = max(cash, 0)

❌ 禁止：同一个 signal_id 被执行两次
✅ 正确：order.IdempotKey = signal_id + "-v1"，内存 map 去重
```

### 16.2 数据格式禁止事项

```
❌ 禁止：Redis topic 用小写 symbol（如 btc-usdt）
✅ 正确：topic 用小写无连字符（如 btcusdt），payload 里用 "BTC-USDT"

❌ 禁止：时间戳用毫秒
✅ 正确：所有内部时间戳用纳秒（timestamp_ns）

❌ 禁止：JSON 中用数字类型传递价格
✅ 正确：价格字段始终用字符串（"67840.50"）
```

### 16.3 LLM 层禁止事项

```
❌ 禁止：直接把 llm_score 作为权重（未考虑置信度）
✅ 正确：effective_score = llm_score × confidence

❌ 禁止：对每条新闻都调用云端 LLM
✅ 正确：常规更新用 Ollama，重大新闻（importance >= 0.85）才升级到云端

❌ 禁止：LLM 输出解析失败时抛异常中断服务
✅ 正确：解析失败降级为中性结果（score=0, confidence=0）
```

### 16.4 Nautilus 集成禁止事项

```
❌ 禁止：修改 Nautilus 内部任何文件
✅ 正确：通过 Strategy/Actor 子类扩展

❌ 禁止：在 RedisBridgeActor 中修改消息格式
✅ 正确：必须与自建数据层输出格式完全一致

❌ 禁止：在 nautilus-core 中实现 LLM 逻辑
✅ 正确：LLM 层始终是独立进程，通过 Redis 通信
```

---

## 附录 A：快速启动命令

```bash
# 首次设置
cp .env.example .env
# 填写 .env 中的 API keys

# 开发模式（只启动基础设施）
make dev
# 之后在各目录分别启动服务：
# cd data-layer && cargo run
# cd strategy-layer && python -m strategy_layer.main
# cd llm-layer && python -m llm_layer.main
# cd risk-engine && go run ./src/main.go
# cd trading-layer && go run ./src/main.go
# cd api-gateway && go run ./src/main.go
# cd frontend && npm run dev

# 下载本地 LLM 模型（约 4GB）
make pull-model

# 全部容器化启动
make up

# 生成开发用 JWT token
make dev-token
```

## 附录 B：关键 GitHub 仓库

```
nautilus_trader:     github.com/nautechsystems/nautilus_trader
cryptofeed:          github.com/bmoscon/cryptofeed
ccxt:                github.com/ccxt/ccxt
freqtrade:           github.com/freqtrade/freqtrade
redpanda:            github.com/redpanda-data/redpanda
ollama:              github.com/ollama/ollama
fingpt:              github.com/AI4Finance-Foundation/FinGPT
openbb:              github.com/OpenBB-finance/OpenBBTerminal
lightweight-charts:  github.com/tradingview/lightweight-charts
PyPortfolioOpt:      github.com/robertmartin8/PyPortfolioOpt
```

## 附录 C：端口规划

```
5173   前端开发服务器（Vite）
6379   Redis
5432   TimescaleDB
8080   API 网关
9090   Prometheus
9092   Redpanda/Kafka
9100   风控层 HTTP（/health, /metrics）
9101   交易层 HTTP（/snapshot, /alignment）
11434  Ollama
3001   Grafana
```
