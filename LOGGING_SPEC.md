# Crazytra 日志规范

本文档定义了 Crazytra 系统的统一日志标准，确保所有组件的日志格式一致、易于查询和分析。

## 日志级别

### 标准级别

| 级别 | 用途 | 示例 |
|------|------|------|
| **DEBUG** | 详细的调试信息 | 变量值、函数调用、数据结构 |
| **INFO** | 一般信息 | 服务启动、配置加载、正常操作 |
| **WARNING** | 警告信息 | 重试操作、降级服务、非关键错误 |
| **ERROR** | 错误信息 | 操作失败、异常捕获、数据错误 |
| **CRITICAL** | 严重错误 | 服务崩溃、数据丢失、安全问题 |

### 使用原则

```python
# ✅ 正确使用
log.debug(f"Calculated signal strength: {strength:.4f}")
log.info(f"Strategy started: {strategy_id}")
log.warning(f"Redis connection retry attempt {attempt}/3")
log.error(f"Failed to parse tick data: {error}")
log.critical(f"Database connection lost, shutting down")

# ❌ 错误使用
log.info(f"x={x}, y={y}, z={z}")  # 应该用 DEBUG
log.error("User clicked button")  # 应该用 INFO
log.warning("Service stopped")    # 应该用 INFO
```

## 日志格式

### Python (structlog)

```python
import structlog

# 配置
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer(),  # 开发环境
        # structlog.processors.JSONRenderer(),  # 生产环境
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()

# 使用
log.info(
    "order_submitted",
    order_id=order.id,
    symbol=order.symbol,
    side=order.side,
    quantity=str(order.quantity),  # Decimal 转字符串
    price=str(order.price),
)
```

**输出示例**：
```
2024-01-01T10:00:00.123456Z [info] order_submitted order_id=ORD-001 symbol=BTC-USDT side=BUY quantity=0.01 price=67840.50
```

### Go (zap)

```go
import "go.uber.org/zap"

// 配置
logger, _ := zap.NewProduction()  // 生产环境
// logger, _ := zap.NewDevelopment()  // 开发环境
defer logger.Sync()

log := logger.Sugar()

// 使用
log.Infow("order_submitted",
    "order_id", order.ID,
    "symbol", order.Symbol,
    "side", order.Side,
    "quantity", order.Quantity.String(),
    "price", order.Price.String(),
)
```

**输出示例**：
```json
{"level":"info","ts":1704067200.123456,"msg":"order_submitted","order_id":"ORD-001","symbol":"BTC-USDT","side":"BUY","quantity":"0.01","price":"67840.50"}
```

### Rust (tracing)

```rust
use tracing::{info, warn, error, debug};

// 配置
tracing_subscriber::fmt()
    .with_target(false)
    .with_thread_ids(true)
    .with_level(true)
    .with_ansi(true)
    .init();

// 使用
info!(
    order_id = %order.id,
    symbol = %order.symbol,
    side = ?order.side,
    quantity = %order.quantity,
    price = %order.price,
    "order_submitted"
);
```

**输出示例**：
```
2024-01-01T10:00:00.123456Z  INFO order_submitted order_id=ORD-001 symbol=BTC-USDT side=Buy quantity=0.01 price=67840.50
```

## 关键事件日志

### 1. 数据层 (Nautilus / Rust)

```rust
// 连接状态
info!(exchange = "binance", "websocket_connected");
warn!(exchange = "binance", attempt = 3, "websocket_reconnecting");
error!(exchange = "binance", error = %e, "websocket_connection_failed");

// Tick 数据
debug!(
    symbol = "BTC-USDT",
    bid = %tick.bid_price,
    ask = %tick.ask_price,
    latency_us = tick.latency_us,
    "tick_received"
);

// 数据发布
info!(
    topic = "market.tick.binance.btcusdt",
    count = batch.len(),
    "ticks_published_to_redis"
);
```

### 2. 策略层 (Python)

```python
# 策略生命周期
log.info("strategy_started", strategy_id=self.id, instrument=self.instrument_id)
log.info("strategy_stopped", strategy_id=self.id, trades=self.trade_count)

# Tick 处理
log.debug(
    "tick_processed",
    symbol=tick.instrument_id,
    bid=str(tick.bid_price),
    ask=str(tick.ask_price),
)

# 信号生成
log.info(
    "signal_generated",
    symbol=symbol,
    direction=direction,
    strength=f"{strength:.4f}",
    llm_factor=f"{llm_factor:.4f}",
)

# LLM 权重更新
log.info(
    "llm_weight_updated",
    symbol=symbol,
    score=f"{score:.4f}",
    confidence=f"{confidence:.4f}",
    model=metadata.get("model"),
)

# 订单提交
log.info(
    "order_submitted",
    order_id=order.client_order_id,
    symbol=order.instrument_id,
    side=order.side,
    quantity=str(order.quantity),
    order_type=order.order_type,
)

# 订单成交
log.info(
    "order_filled",
    order_id=event.client_order_id,
    fill_price=str(event.last_px),
    fill_qty=str(event.last_qty),
    commission=str(event.commission),
)
```

### 3. LLM 层 (Python)

```python
# 服务启动
log.info("llm_layer_starting", symbols=SYMBOLS, interval_s=INTERVAL)

# 新闻获取
log.info("news_fetched", count=len(items), sources=list(set(i.source for i in items)))

# LLM 调用
log.info(
    "llm_request",
    provider=provider.provider_id,
    tag=req.request_tag,
    tokens_estimate=estimate_tokens(req),
)

log.info(
    "llm_response",
    provider=resp.provider,
    model=resp.model,
    latency_ms=resp.latency_ms,
    input_tokens=resp.input_tokens,
    output_tokens=resp.output_tokens,
    cached=resp.cached,
)

# 权重发布
log.info(
    "weight_published",
    symbol=vec.symbol,
    score=f"{vec.llm_score:.4f}",
    confidence=f"{vec.confidence:.4f}",
    model=vec.model_used,
    drivers=vec.key_drivers[:2],
)

# 错误处理
log.warning("provider_failed", provider=p.provider_id, error=str(e))
log.error("json_parse_failed", raw=resp.content[:200])
```

### 4. 风控层 (Go)

```go
// 信号接收
log.Infow("signal_received",
    "signal_id", signal.ID,
    "symbol", signal.Symbol,
    "direction", signal.Direction,
    "strength", signal.Strength,
)

// 风控检查
log.Debugw("risk_check_started", "signal_id", signal.ID)

log.Warnw("signal_rejected_ttl",
    "signal_id", signal.ID,
    "age_ms", ageMs,
    "max_ttl_ms", maxTTL,
)

log.Warnw("signal_rejected_daily_loss",
    "signal_id", signal.ID,
    "daily_loss_pct", dailyLossPct,
    "max_loss_pct", maxLossPct,
)

// 订单生成
log.Infow("order_created",
    "order_id", order.ID,
    "signal_id", signal.ID,
    "symbol", order.Symbol,
    "size", order.Size.String(),
)
```

### 5. 执行层 (Go / Nautilus)

```go
// 订单提交
log.Infow("order_submitting",
    "order_id", order.ID,
    "exchange", order.Exchange,
    "symbol", order.Symbol,
)

// 订单状态
log.Infow("order_accepted",
    "order_id", order.ID,
    "venue_order_id", venueOrderID,
)

log.Infow("order_filled",
    "order_id", order.ID,
    "fill_price", fillPrice.String(),
    "fill_qty", fillQty.String(),
)

log.Errorw("order_rejected",
    "order_id", order.ID,
    "reason", reason,
)
```

## 性能日志

### 延迟追踪

```python
import time

# Python
start = time.perf_counter()
result = process_tick(tick)
latency_ms = (time.perf_counter() - start) * 1000

log.info(
    "tick_processed",
    symbol=tick.symbol,
    latency_ms=f"{latency_ms:.2f}",
    result=result,
)
```

```go
// Go
start := time.Now()
result := processTick(tick)
latencyMs := time.Since(start).Milliseconds()

log.Infow("tick_processed",
    "symbol", tick.Symbol,
    "latency_ms", latencyMs,
    "result", result,
)
```

### 吞吐量统计

```python
# 每分钟统计一次
tick_count = 0
last_report = time.time()

def on_tick(tick):
    global tick_count
    tick_count += 1
    
    now = time.time()
    if now - last_report >= 60:
        log.info(
            "throughput_report",
            ticks_per_minute=tick_count,
            avg_tps=tick_count / 60,
        )
        tick_count = 0
        last_report = now
```

## 错误日志

### 异常捕获

```python
# Python
try:
    result = risky_operation()
except ValueError as e:
    log.error(
        "validation_error",
        operation="risky_operation",
        error=str(e),
        input_data=data,
        exc_info=True,  # 包含堆栈跟踪
    )
except Exception as e:
    log.critical(
        "unexpected_error",
        operation="risky_operation",
        error=str(e),
        exc_info=True,
    )
    raise  # 重新抛出
```

```go
// Go
if err := riskyOperation(); err != nil {
    log.Errorw("operation_failed",
        "operation", "riskyOperation",
        "error", err.Error(),
        "stack", string(debug.Stack()),
    )
    return err
}
```

### 重试日志

```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def fetch_data():
    try:
        return await api_call()
    except Exception as e:
        log.warning(
            "api_call_retry",
            attempt=retry_state.attempt_number,
            max_attempts=3,
            error=str(e),
        )
        raise
```

## 审计日志

### 交易审计

```python
# 关键操作必须记录
log.info(
    "trade_executed",
    trade_id=trade.id,
    order_id=order.id,
    symbol=trade.symbol,
    side=trade.side,
    quantity=str(trade.quantity),
    price=str(trade.price),
    commission=str(trade.commission),
    timestamp_ns=trade.ts_event,
    strategy_id=strategy.id,
    user_id=user.id,  # 如果有用户系统
)
```

### 配置变更

```python
log.info(
    "config_updated",
    component="strategy",
    strategy_id=strategy.id,
    old_config=old_config,
    new_config=new_config,
    changed_by=user_id,
)
```

## 日志聚合和查询

### 结构化查询

使用 structlog 的结构化日志，可以轻松查询：

```bash
# 查询所有订单提交
grep "order_submitted" app.log | jq .

# 查询特定 symbol 的信号
grep "signal_generated" app.log | jq 'select(.symbol == "BTC-USDT")'

# 查询错误日志
grep '"level":"error"' app.log | jq .

# 统计 LLM 调用次数
grep "llm_response" app.log | wc -l

# 计算平均延迟
grep "tick_processed" app.log | jq -r '.latency_ms' | awk '{sum+=$1; count++} END {print sum/count}'
```

### 日志聚合工具

推荐使用：
- **ELK Stack** (Elasticsearch + Logstash + Kibana)
- **Loki + Grafana**
- **Datadog**
- **CloudWatch Logs** (AWS)

## 日志轮转

### Python (logging.handlers)

```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "app.log",
    maxBytes=100 * 1024 * 1024,  # 100 MB
    backupCount=10,
)
```

### Go (lumberjack)

```go
import "gopkg.in/natefinch/lumberjack.v2"

logger := &lumberjack.Logger{
    Filename:   "app.log",
    MaxSize:    100,  // MB
    MaxBackups: 10,
    MaxAge:     30,   // days
    Compress:   true,
}
```

### Docker / Kubernetes

```yaml
# docker-compose.yml
services:
  app:
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"
```

## 敏感信息处理

### 禁止记录

❌ **绝对禁止**记录以下信息：
- API 密钥和密码
- 私钥和证书
- 用户密码
- 信用卡信息
- 个人身份信息 (PII)

### 脱敏处理

```python
# ✅ 正确
log.info("api_key_configured", key_prefix=api_key[:8] + "...")

# ❌ 错误
log.info("api_key_configured", key=api_key)
```

## 生产环境配置

### 日志级别

```bash
# 开发环境
LOG_LEVEL=DEBUG

# 测试环境
LOG_LEVEL=INFO

# 生产环境
LOG_LEVEL=WARNING  # 或 INFO
```

### 输出格式

```python
# 开发环境：人类可读
structlog.dev.ConsoleRenderer()

# 生产环境：JSON
structlog.processors.JSONRenderer()
```

### 示例配置

```python
import os
import structlog

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENV = os.getenv("ENV", "development")

processors = [
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.add_log_level,
    structlog.processors.StackInfoRenderer(),
]

if ENV == "production":
    processors.append(structlog.processors.JSONRenderer())
else:
    processors.append(structlog.dev.ConsoleRenderer())

structlog.configure(
    processors=processors,
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, LOG_LEVEL)
    ),
)
```

## 监控告警

### 关键指标

基于日志设置告警：

```yaml
# 示例：Prometheus AlertManager 规则
groups:
  - name: trading_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(log_messages{level="error"}[5m]) > 10
        annotations:
          summary: "High error rate detected"
      
      - alert: OrderRejectionRate
        expr: rate(log_messages{event="order_rejected"}[5m]) > 5
        annotations:
          summary: "High order rejection rate"
      
      - alert: LLMProviderDown
        expr: rate(log_messages{event="provider_failed"}[5m]) > 3
        annotations:
          summary: "LLM provider failures"
```

## 最佳实践

### DO ✅

1. **使用结构化日志**：便于查询和分析
2. **包含上下文**：order_id, symbol, user_id 等
3. **记录关键路径**：订单流、数据流、错误
4. **使用合适的级别**：不要滥用 ERROR
5. **包含时间戳**：使用 UTC 时间
6. **记录延迟**：性能关键路径
7. **使用常量事件名**：便于搜索

### DON'T ❌

1. **不要记录敏感信息**：密码、密钥
2. **不要在循环中记录 INFO**：会产生大量日志
3. **不要记录大对象**：只记录关键字段
4. **不要使用字符串拼接**：使用参数化
5. **不要忽略异常**：至少记录 WARNING
6. **不要在生产环境用 DEBUG**：性能影响
7. **不要记录 PII**：隐私问题

## 参考资料

- [structlog 文档](https://www.structlog.org/)
- [zap 文档](https://pkg.go.dev/go.uber.org/zap)
- [tracing 文档](https://docs.rs/tracing/)
- [12-Factor App: Logs](https://12factor.net/logs)
