# 快速参考卡 — AI 工具速查手册

> 本文件是 SYSTEM_SPEC.md 的精简速查版。当 AI 工具需要快速确认接口签名、字段名、
> 枚举值时使用本文件；需要理解设计决策和背景时查阅 SYSTEM_SPEC.md。

---

## Redis Topic 速查

| Topic | 生产者 | 消费者 | MAXLEN |
|-------|-------|--------|--------|
| `market.tick.{exchange}.{symbol}` | 数据层/Nautilus | 策略层、风控层、交易层 | 50,000 |
| `strategy.signal` | 策略层 | 风控层 | 10,000 |
| `llm.weight` | LLM 层 | 策略层（LLM Actor） | 1,000 |
| `order.command` | 风控层 | 交易层 | 10,000 |
| `order.event` | 交易层 | 风控层、前端（via 网关） | 100,000 |
| `position.update` | 交易层 | 前端（via 网关） | 10,000 |
| `risk.alert` | 风控层 | 前端（via 网关） | 5,000 |
| `account.state` | Nautilus/交易层 | 前端（via 网关） | 1,000 |

---

## 核心数据结构速查

### NormalizedTick（Rust）
```rust
pub struct NormalizedTick {
    pub symbol:       Symbol,
    pub timestamp_ns: u64,      // 纳秒
    pub received_ns:  u64,      // 纳秒
    pub bid_price:    Decimal,  // 必须 Decimal
    pub bid_size:     Decimal,
    pub ask_price:    Decimal,
    pub ask_size:     Decimal,
    pub last_price:   Decimal,
    pub last_size:    Decimal,
    pub volume_24h:   Decimal,
    pub sequence:     Option<u64>,
}
```

### Tick（Python 策略层）
```python
@dataclass(frozen=True, slots=True)
class Tick:
    symbol:       str
    timestamp_ns: int
    bid:          Decimal
    ask:          Decimal
    last:         Decimal
    bid_size:     Decimal
    ask_size:     Decimal
    volume_24h:   Decimal
    # mid = (bid + ask) / 2
    # spread_bps = (ask - bid) / mid * 10000
```

### Signal（Python 策略层）
```python
@dataclass
class Signal:
    signal_id:    str          # uuid4
    strategy_id:  str          # 策略的 STRATEGY_ID
    symbol:       str          # "BTC-USDT"
    direction:    SignalDirection  # LONG/SHORT/EXIT/HOLD
    strength:     float        # [0.0, 1.0]
    confidence:   float        # [0.0, 1.0]
    target_price: Decimal | None
    target_size:  Decimal | None
    stop_loss:    Decimal | None
    take_profit:  Decimal | None
    timestamp_ns: int          # 纳秒
    ttl_ms:       int          # 默认 5000
    reason:       str          # 可读原因
```

### LLM 权重消息（Redis JSON）
```json
{
  "symbol":      "BTC-USDT",
  "llm_score":   0.35,        // [-1.0, 1.0]
  "confidence":  0.72,        // [0.0, 1.0]
  "horizon":     "short",     // short/medium/long
  "key_drivers": ["..."],
  "risk_events": ["..."],
  "model_used":  "ollama/mistral:7b-instruct-q4_K_M",
  "ts_ns":       1700000000000000000,
  "ttl_ms":      300000
}
```

### OrderCommand（Go 风控层输出）
```go
type OrderCommand struct {
    CommandID  string          // uuid
    IdempotKey string          // signal_id + "-v1"
    SignalID   string
    Symbol     string          // "BTCUSDT" (Nautilus) 或 "BTC-USDT"
    Direction  string          // "long"/"short"/"exit"
    Notional   decimal.Decimal // 名义价值 USD
    OrderType  string          // "market"/"limit"
    StopLoss   *decimal.Decimal
    TakeProfit *decimal.Decimal
    Mode       string          // "paper"/"live"
    CreatedAt  int64           // UnixNano
}
```

### OrderEvent（Go 交易层输出）
```go
type OrderEvent struct {
    EventID   string          // uuid
    OrderID   string
    SignalID  string
    Symbol    string
    Kind      OrderStatus     // "filled"/"partial_filled"/"cancelled"/"rejected"
    FilledQty decimal.Decimal
    FilledPx  decimal.Decimal
    Fee       decimal.Decimal
    FeeAsset  string          // "USDT"
    Timestamp int64           // UnixNano
    Mode      string          // "paper"/"live"
}
```

---

## 枚举值速查

### SignalDirection（Python）
```python
LONG  = "long"    # 做多
SHORT = "short"   # 做空
EXIT  = "exit"    # 平仓（不区分多空）
HOLD  = "hold"    # 不操作（不发布到 Redis）
```

### AlertKind（Go）
```go
AlertCircuitBreaker = "circuit_breaker"
AlertPositionLimit  = "position_limit"
AlertDailyLoss      = "daily_loss"
AlertDrawdown       = "drawdown"
AlertSignalExpired  = "signal_expired"
AlertSizingError    = "sizing_error"
```

### AlertSeverity（Go）
```go
SeverityInfo     = "info"
SeverityWarn     = "warn"
SeverityCritical = "critical"
```

---

## 关键常量速查

### 风控阈值（环境变量）
```
MAX_POSITION_SIZE = 0.20   (20% NAV per symbol)
MAX_DAILY_LOSS    = 0.05   (5% initial NAV)
MAX_DRAWDOWN      = 0.15   (15% peak NAV)
CB_FAIL_THRESHOLD = 5      (连续失败次数触发熔断)
CB_RESET_MS       = 60000  (熔断冷却 60s)
CB_RECOVER_COUNT  = 3      (半开状态连续成功 3 次恢复)
```

### 滑点模型阈值
```
small_order_threshold  = $1,000   → FixedBpsSlippage (0.5bps)
large_order_threshold  = $50,000  → OrderBookImpactSlippage
中间区间               → VolumeImpactSlippage
```

### 手续费（Binance VIP0）
```
maker_fee = 0.0002  (0.02%)
taker_fee = 0.0005  (0.05%)
bnb_discount = 0.75 (持有 BNB 打 75 折)
```

### LLM 调度
```
routine_interval_s = 300    (5分钟常规分析，用 Ollama)
breaking_threshold = 0.85   (重要性 >= 此值触发即时分析，用云端)
breaking_cooldown_s = 60    (重大事件最小间隔)
decay_half_life_min = 30    (权重衰减半衰期 30 分钟)
cache_ttl_s = 180           (相同内容 3 分钟内不重复调用)
```

---

## 方法签名速查（Python 策略层）

```python
# 注册策略（装饰器）
@register
class MyStrategy(BaseStrategy):
    STRATEGY_ID   = "my_strategy_v1"
    STRATEGY_NAME = "策略显示名"

# 参数更新（无需重启）
strategy.update_llm_weight(weight: float) -> None  # weight ∈ [-1.0, 1.0]

# 热重载接口
strategy.export_state() -> dict
strategy.import_state(state_dict: dict) -> None

# 信号合成器
combinator.configure(symbol: str, weights: list[StrategyWeight]) -> None
await combinator.update_llm_weights(symbol: str, llm_score: float) -> None
await combinator.ingest(signal: Signal) -> None
await combinator.combine(symbol: str) -> CombinedSignal | None

# 运行时调度
await runner.add_strategy(strategy_id: str, params: dict) -> None
await runner.remove_strategy(strategy_id: str) -> None
await runner.dispatch_tick(tick: Tick) -> None
await runner.hot_reload(changed_file: Path) -> None
```

---

## Nautilus 集成速查

### 数据类型转换
```python
# Nautilus → 自建格式
nautilus_tick.instrument_id.symbol.value  → symbol.replace("USDT", "-USDT")
nautilus_tick.ts_event                    → timestamp_ns
nautilus_tick.ts_init                     → received_ns
str(nautilus_tick.bid_price)              → bid (字符串)
str(nautilus_tick.bid_size)               → bid_size
```

### Actor 模板
```python
class MyActor(Actor):
    def on_start(self) -> None:
        self._redis = aioredis.from_url(redis_url)
        self.subscribe_quote_ticks(instrument_id=None)  # None=全部

    def on_quote_tick(self, tick: QuoteTick) -> None:
        asyncio.create_task(self._publish(tick))  # 非阻塞

    async def _publish(self, tick: QuoteTick) -> None:
        try:
            await self._redis.xadd(topic, fields, maxlen=50000, approximate=True)
        except Exception as e:
            self.log.warning(f"Redis error: {e}")  # 不抛出异常
```

---

## 前端类型速查（TypeScript）

```typescript
interface Tick {
  symbol: string; bid: string; ask: string; last: string
  volume_24h: string; timestamp_ns: number; latency_us: number
}

interface Signal {
  signal_id: string; strategy_id: string; symbol: string
  direction: 'long' | 'short' | 'exit' | 'hold'
  strength: number; confidence: number
  reason: string; timestamp_ns: number
}

interface OrderEvent {
  event_id: string; order_id: string; symbol: string
  kind: string; filled_qty: string; filled_px: string
  fee: string; slip_bps: string; latency_ms: number
  timestamp: number; mode: 'paper' | 'live'
}

interface RiskAlert {
  alert_id: string; kind: string; symbol: string
  message: string; severity: 'info' | 'warn' | 'critical'
  value?: number; limit?: number; timestamp: number
}

interface LLMWeight {
  symbol: string; llm_score: number; confidence: number
  horizon: string; key_drivers: string[]
  risk_events: string[]; model_used: string
}
```

---

## 服务端口速查

```
5173  Vite 前端开发服务器
6379  Redis
5432  TimescaleDB/PostgreSQL
8080  API 网关 (REST + WebSocket /ws)
9090  Prometheus
9092  Redpanda
9100  风控层 /health + /metrics
9101  交易层 /snapshot + /alignment
11434 Ollama
3001  Grafana (admin/admin)
```
