# AI 工具任务提示模板

> 使用方式：把下面对应任务的提示词复制给你的 AI 工具（Cursor/Copilot/Claude Code），
> AI 工具会结合 SYSTEM_SPEC.md 中的上下文生成符合规范的代码。
>
> 每个提示词开头都有 **[必须先读]** 指引，告诉 AI 工具需要先阅读哪些规范章节。

---

## 任务 1：新增交易所适配器

```
[必须先读] SYSTEM_SPEC.md 第 4 章（数据获取层）

任务：为 <交易所名称> 实现 Connector trait。

要求：
1. 文件位置：data-layer/src/connector/<exchange_name>.rs
2. 必须实现 Connector trait 的全部 4 个方法：id(), subscribe(), fetch_snapshot(), unsubscribe(), state()
3. 使用 ReconnectingWebSocket（见 transport/mod.rs），配置参数：
   - initial_backoff: 1s, max_backoff: 60s, backoff_factor: 2.0, jitter_ratio: 0.3
4. WebSocket 消息解析后必须转换为 NormalizedTick（所有价格字段用 rust_decimal::Decimal）
5. 推入 tick_tx channel，不直接写 Redis（数据层职责分离）
6. state() 用 AtomicU8 实现（0=断开, 1=连接中, 2=已连接）

交易所名称：___
API 文档 URL：___
WebSocket Stream URL：___
```

---

## 任务 2：新增策略插件

```
[必须先读] SYSTEM_SPEC.md 第 6 章（策略层）

任务：实现一个新的交易策略。

要求：
1. 文件位置：strategy-layer/strategy_layer/strategies/<strategy_name>.py
2. 参数类继承 StrategyParams，用 Pydantic，frozen=True
3. 策略类用 @register 装饰器，定义 STRATEGY_ID（全局唯一）和 STRATEGY_NAME
4. on_tick() 必须是纯同步，禁止任何 I/O，必须在 1ms 内返回
5. 返回的 Signal 对象：direction 必须是 SignalDirection 枚举值，strength ∈ [0, 1]
6. 实现 export_state() 和 import_state() 支持热重载状态迁移
7. 如果使用 LLM 权重，通过 self._llm_weight 字段（由 update_llm_weight() 更新）

策略逻辑描述：___
需要的参数：___
```

---

## 任务 3：LLM Provider 对接

```
[必须先读] SYSTEM_SPEC.md 第 7 章（LLM 层）

任务：在 llm_layer/main.py 中新增一个 LLM Provider。

要求：
1. 继承 BaseProvider 抽象类
2. 实现 provider_id 属性、complete() 方法、estimate_cost() 方法
3. complete() 内部使用 @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
4. 必须处理 json_mode=True 的情况（强制 JSON 输出）
5. 记录 input_tokens 和 output_tokens（用于成本追踪）
6. 失败时调用 self.record_error()，成功时调用 self.record_success(cost)
7. is_healthy() 检查：连续 3 次失败且 60s 内 → 不健康；预算超限 → 不健康

Provider 名称：___
API 文档：___
```

---

## 任务 4：风控规则新增

```
[必须先读] SYSTEM_SPEC.md 第 8 章（风控层）

任务：在 risk-engine 的 RiskGateway 串行校验链中新增一个风控检查。

要求：
1. 新检查必须插入在现有链的合适位置（见 SYSTEM_SPEC.md 8.1 节的顺序原则：越快的越靠前）
2. 返回 CheckResult（passed() / rejected() / warned()）
3. 拒绝时必须创建 RiskAlert，并通过 publisher.PublishAlerts() 广播
4. 使用 atomic 操作，不使用 mutex（性能关键路径）
5. 新增的阈值参数通过环境变量配置，不硬编码
6. 如果是"超限但允许平仓"的规则，必须检查 sig.Direction != "exit"
7. 状态需要持久化到 Redis（在 StateStore.Persist() 中新增 key）

规则描述：___
触发条件：___
允许例外的情况：___
```

---

## 任务 5：前端新增页面或组件

```
[必须先读] SYSTEM_SPEC.md 第 11 章（前端）

任务：实现前端组件/页面。

要求：
1. 从 useTradeStore 获取数据，不在组件内直接调用 API（除非需要历史数据）
2. 数字显示：价格保留 2 位小数，百分比保留 2 位，P&L 带 +/- 前缀
3. 颜色规则：盈利/上涨用 text-green-400，亏损/下跌用 text-red-400
4. 使用 Tailwind CSS，不写内联 style（除非动态值）
5. 实时数据用 Zustand selector 订阅，避免全量 re-render
6. WebSocket 推送的消息通过 _topic 字段路由，不另起连接

组件/页面描述：___
需要展示的数据：___
交互行为：___
```

---

## 任务 6：Nautilus Actor 开发

```
[必须先读] SYSTEM_SPEC.md 第 13 章（Nautilus 集成）

任务：开发一个 Nautilus Actor。

要求：
1. 继承 nautilus_trader.trading.actor.Actor
2. on_start() 中建立 Redis 连接，on_stop() 中关闭连接
3. 所有 Redis 操作使用 asyncio.create_task()（不阻塞 Nautilus 主循环）
4. 如果需要向 Redis 写入 tick/order 数据，格式必须与 SYSTEM_SPEC.md 第 4 章第 5 节完全一致
5. 绝不修改 Nautilus 内部代码，通过 subscribe_*() 方法订阅事件
6. 错误处理：捕获所有异常，记录警告日志，不向上抛出（避免影响 Nautilus 主进程）

Actor 功能描述：___
需要订阅的事件类型：___
需要写入的 Redis topic：___
```

---

## 任务 7：回测任务

```
[必须先读] SYSTEM_SPEC.md 第 6.5 节（回测引擎规范）

任务：对指定策略运行回测并生成报告。

要求：
1. 使用 strategy-layer/strategy_layer/backtest/engine.py 中的 BacktestEngine
2. fill_at="next_open"（消除前视偏差，这是规范要求）
3. 数据文件格式：Parquet，列名固定为 time, symbol, bid, ask, last, bid_size, ask_size, volume_24h
4. 必须输出以下指标：total_return, annual_return, sharpe_ratio, sortino_ratio, max_drawdown, calmar_ratio, win_rate, profit_factor
5. 结果打印到 structlog（JSON 格式）

策略 ID：___
回测区间：___（如 2024-01-01 到 2024-12-31）
数据文件路径：___
策略参数：___
```

---

## 任务 8：修复 Bug

```
[必须先读] SYSTEM_SPEC.md 第 16 章（常见错误与禁止行为）

任务：修复以下 Bug。

在修复前，请先检查：
1. 修复是否会引入 float/float64 做金融计算（禁止）
2. 修复是否会在 on_tick() 中加入 I/O 操作（禁止）
3. 修复是否会拦截 direction="exit" 的信号（禁止）
4. 修复是否改变了 Redis topic 的消息格式（会破坏其他服务）

Bug 描述：___
错误日志：___
复现步骤：___
```

---

## 通用提示词前缀（可附加到任何任务）

把以下内容粘贴到任务描述的最前面：

```
你是这个自动交易系统的专职开发 AI。系统规范在 SYSTEM_SPEC.md 中。

在生成任何代码之前，请先确认以下事项：
1. 金融计算使用 Decimal（Python: decimal.Decimal，Go: shopspring/decimal，Rust: rust_decimal）
2. 时间戳使用纳秒整数
3. 价格在 JSON 中序列化为字符串
4. 遵守第 16 章中所有禁止事项
5. 新代码的日志使用 structlog（Python）或 zap（Go）结构化输出

如果任务描述与 SYSTEM_SPEC.md 中的规范有冲突，以 SYSTEM_SPEC.md 为准，并告知冲突所在。
```
