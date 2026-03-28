# 📚 NautilusTrader 开发参考索引

> **🎯 用途**: 本索引文件是 NautilusTrader 开发的核心参考文档。每次开发前请先查阅此索引，必要时参考具体文档。

---

## 🏗️ **核心架构概览**

### **系统架构** ([`architecture.md`](docs/nautilus_github_docs/concepts/architecture.md))
- **设计哲学**: DDD、事件驱动、消息传递、端口适配器、崩溃优先设计
- **质量属性**: 可靠性 > 性能 > 模块化 > 可测试性 > 可维护性 > 可部署性
- **核心组件**:
  - `NautilusKernel`: 中央编排组件
  - `MessageBus`: 通信骨干 (发布/订阅、请求/响应)
  - `Cache`: 高性能内存存储
  - `DataEngine`: 市场数据处理和路由
  - `ExecutionEngine`: 订单生命周期管理
  - `RiskEngine`: 风险管理

### **环境上下文**
- `Backtest`: 历史数据 + 模拟交易所
- `Sandbox`: 实时数据 + 模拟交易所  
- `Live`: 实时数据 + 实时交易所

### **数据流和执行流**
- **数据流**: Adapter → Channel → DataEngine → Cache → MessageBus → Strategy
- **执行流**: Strategy → RiskEngine → ExecutionEngine → ExecutionClient → Venue

---

## 🎭 **组件开发指南**

### **Actors** ([`actors.md`](docs/nautilus_github_docs/concepts/actors.md))
**基础组件，Strategy 继承自 Actor**

#### **核心能力**
- 数据订阅和请求 (市场数据、自定义数据)
- 事件处理和发布
- 定时器和警报
- 缓存和投资组合访问
- 日志记录

#### **生命周期方法**
```python
def on_start(self) -> None:     # 启动时 (订阅数据)
def on_stop(self) -> None:      # 停止时 (清理资源)
def on_resume(self) -> None:    # 恢复时
def on_reset(self) -> None:     # 重置时 (重测试间)
def on_dispose(self) -> None:   # 销毁时 (最终清理)
```

#### **数据处理器**
- **实时数据**: `on_bar()`, `on_quote_tick()`, `on_trade_tick()`
- **历史数据**: `on_historical_data()` (通过 `request_*`)
- **自定义数据**: `on_data()`, `on_signal()`

#### **定时器示例**
```python
self.clock.set_timer("timer_name", interval, callback=self._handler)
self.clock.set_time_alert("alert_name", alert_time, callback=self._handler)
```

### **Strategies** ([`strategies.md`](docs/nautilus_github_docs/concepts/strategies.md))
**扩展 Actor，增加订单管理能力**

#### **订单管理命令**
```python
# 提交订单
self.submit_order(order)

# 取消订单
self.cancel_order(order)
self.cancel_orders(order_list)
self.cancel_all_orders()

# 修改订单
self.modify_order(order, new_quantity)

# 市场退出
self.market_exit()
```

#### **订单事件处理器**
```python
def on_order_accepted(self, event: OrderAccepted) -> None:
def on_order_filled(self, event: OrderFilled) -> None:
def on_order_canceled(self, event: OrderCanceled) -> None:
def on_order_rejected(self, event: OrderRejected) -> None:
```

#### **策略配置模式**
```python
class MyStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal

class MyStrategy(Strategy):
    def __init__(self, config: MyStrategyConfig) -> None:
        super().__init__(config)
        # 访问配置: self.config.instrument_id
```

---

## 🔌 **适配器开发**

### **适配器架构** ([`adapters.md`](docs/nautilus_github_docs/concepts/adapters.md))
**集成数据提供商和交易所**

#### **适配器组件**
- `HttpClient`: REST API 通信
- `WebSocketClient`: 实时流连接
- `InstrumentProvider`: 加载和解析合约定义
- `DataClient`: 处理市场数据订阅和请求
- `ExecutionClient`: 处理订单提交、修改、取消

### **适配器开发指南** ([`adapters.md`](docs/nautilus_github_docs/developer_guide/adapters.md))

#### **实现序列**
1. **Phase 1**: Rust 核心基础设施 (HTTP/WebSocket 客户端)
2. **Phase 2**: 合约定义解析
3. **Phase 3**: 市场数据 (订阅 + 历史数据)
4. **Phase 4**: 订单执行 (订单管理 + 账户状态)
5. **Phase 5**: 高级功能 (高级订单类型、批量操作)
6. **Phase 6**: 配置和工厂
7. **Phase 7**: 测试和文档

#### **Rust 适配器模式**
```
crates/adapters/your_adapter/
├── src/
│   ├── common/          # 共享类型和工具
│   ├── http/            # HTTP 客户端
│   ├── websocket/       # WebSocket 客户端
│   ├── python/          # PyO3 绑定
│   ├── config.rs        # 配置结构
│   ├── data.rs          # 数据客户端
│   └── execution.rs     # 执行客户端
```

#### **Python 层结构**
```
nautilus_trader/adapters/your_adapter/
├── config.py           # 配置类
├── data.py             # LiveDataClient
├── execution.py        # LiveExecutionClient
├── factories.py        # 工厂函数
├── providers.py        # InstrumentProvider
└── __init__.py
```

---

## 📊 **数据类型和处理**

### **内置数据类型** ([`data.md`](docs/nautilus_github_docs/concepts/data.md))

#### **市场数据类型**
- `OrderBookDelta`: L1/L2/L3 订单簿更新
- `OrderBookDeltas`: 批量订单簿增量
- `OrderBookDepth10`: 10档订单簿快照
- `QuoteTick`: 最优买卖价
- `TradeTick`: 单笔交易
- `Bar`: OHLCV K线数据
- `MarkPriceUpdate`: 标记价格
- `FundingRateUpdate`: 资金费率

#### **合约类型**
- 现货: `Equity`, `CurrencyPair`, `Commodity`, `IndexInstrument`
- 衍生品: `FuturesContract`, `CryptoPerpetual`, `OptionContract`, `BinaryOption`
- 其他: `BettingInstrument`, `SyntheticInstrument`

### **K线数据聚合**

#### **聚合方法**
- **时间驱动**: `MILLISECOND`, `SECOND`, `MINUTE`, `HOUR`, `DAY`, `WEEK`, `MONTH`, `YEAR`
- **阈值驱动**: `TICK`, `VOLUME`, `VALUE`, `RENKO`
- **信息驱动**: `TICK_IMBALANCE`, `VOLUME_IMBALANCE`, `VALUE_IMBALANCE`, `TICK_RUNS`, `VOLUME_RUNS`, `VALUE_RUNS`

#### **BarType 字符串语法**
```python
# 标准K线 (从Tick聚合)
bar_type = BarType.from_str("BTCUSDT-PERP.BINANCE-5-MINUTE-LAST-INTERNAL")

# 复合K线 (从K线聚合)
bar_type = BarType.from_str("BTCUSDT-PERP.BINANCE-5-MINUTE-LAST-INTERNAL@1-MINUTE-EXTERNAL")
```

#### **数据操作模式**
```python
# 历史数据请求 -> on_historical_data()
self.request_bars(bar_type)

# 实时数据订阅 -> on_bar()
self.subscribe_bars(bar_type)
```

---

## ⚙️ **配置和工厂**

### **策略配置**
```python
from nautilus_trader.config import StrategyConfig

class MyStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    fast_ema_period: int = 10
    slow_ema_period: int = 20
    trade_size: Decimal
    order_id_tag: str
```

### **适配器配置**
```python
from nautilus_trader.config import LiveDataClientConfig, LiveExecClientConfig

class MyDataClientConfig(LiveDataClientConfig):
    api_key: str | None = None
    api_secret: str | None = None
    base_url_http: str | None = None
    base_url_ws: str | None = None
```

---

## 🧪 **测试和验证**

### **测试组织**
- **Rust 单元测试**: `#[cfg(test)]` 块
- **Rust 集成测试**: `tests/` 目录，模拟 Axum 服务器
- **Python 集成测试**: `tests/integration_tests/adapters/<adapter>/`

### **数据加载流程**
1. **DataLoader**: 读取原始数据 → `pd.DataFrame`
2. **DataWrangler**: 处理 DataFrame → `list[Data]`
3. **输出**: Nautilus 数据结构

---

## 🎯 **Polymarket 集成特定**

### **Polymarket API 参考** ([`polymarket.md`](docs/nautilus_github_docs/api_reference/adapters/polymarket.md))
- **模块**: `nautilus_trader.adapters.polymarket`
- **配置**: `polymarket.config`
- **工厂**: `polymarket.factories`
- **枚举**: `polymarket.common.enums`
- **提供者**: `polymarket.providers`
- **数据**: `polymarket.data`
- **执行**: `polymarket.execution`

### **当前实现状态**
- ✅ **Python Fallback 适配器**: `polymarket_python_fallback.py`
- ✅ **BTC 5分钟策略**: `strategies/polymarket/btc_5m_binary_ev.py`
- ✅ **数据服务**: `polymarket_data_service.py`
- ✅ **前端组件**: `PolymarketTradingPanel.tsx`
- 🔄 **Rust 适配器**: 待构建 (需要 Rust 环境)

---

## 📋 **开发检查清单**

### **开始开发前**
- [ ] 查阅此索引文件
- [ ] 确定开发类型 (Strategy/Actor/Adapter)
- [ ] 查看相关概念文档
- [ ] 检查现有实现

### **Strategy 开发**
- [ ] 继承 `Strategy` 类
- [ ] 定义 `StrategyConfig`
- [ ] 实现 `on_start()` 和 `on_stop()`
- [ ] 实现数据处理器 (`on_bar`, `on_quote_tick`)
- [ ] 实现订单事件处理器
- [ ] 添加订单管理逻辑
- [ ] 配置订单ID标签 (多策略实例)

### **Adapter 开发**
- [ ] 实现 Rust 核心 (HTTP/WebSocket 客户端)
- [ ] 实现 `InstrumentProvider`
- [ ] 实现 `DataClient` (LiveDataClient)
- [ ] 实现 `ExecutionClient` (LiveExecutionClient)
- [ ] 创建工厂函数
- [ ] 添加配置类
- [ ] 编写集成测试

### **数据集成**
- [ ] 确定数据类型 (QuoteTick/TradeTick/Bar)
- [ ] 实现 DataWrangler
- [ ] 配置 BarType 聚合
- [ ] 设置数据订阅/请求
- [ ] 验证时间戳处理

---

## 🔍 **故障排除**

### **常见问题**
1. **数据未到达**: 检查订阅 vs 请求处理器
2. **订单失败**: 检查风险引擎配置
3. **合约未找到**: 检查 InstrumentProvider 加载
4. **时间戳问题**: 区分 `ts_event` 和 `ts_init`
5. **精度问题**: 使用固定点运算，避免浮点错误

### **调试技巧**
- 使用 `self.log.info()` 记录关键事件
- 检查 `self.cache` 中的数据状态
- 验证 `self.portfolio` 的仓位信息
- 监控 MessageBus 消息流

---

## 📚 **文档导航**

### **概念文档** (`concepts/`)
- [`architecture.md`](docs/nautilus_github_docs/concepts/architecture.md) - 系统架构
- [`actors.md`](docs/nautilus_github_docs/concepts/actors.md) - Actor 组件
- [`strategies.md`](docs/nautilus_github_docs/concepts/strategies.md) - 策略开发
- [`adapters.md`](docs/nautilus_github_docs/concepts/adapters.md) - 适配器概念
- [`data.md`](docs/nautilus_github_docs/concepts/data.md) - 数据类型
- [`execution.md`](docs/nautilus_github_docs/concepts/execution.md) - 执行流程
- [`orders.md`](docs/nautilus_github_docs/concepts/orders.md) - 订单类型
- [`positions.md`](docs/nautilus_github_docs/concepts/positions.md) - 仓位管理

### **API 参考** (`api_reference/`)
- [`adapters/polymarket.md`](docs/nautilus_github_docs/api_reference/adapters/polymarket.md) - Polymarket API
- [`core.md`](docs/nautilus_github_docs/api_reference/core.md) - 核心组件
- [`model/`](docs/nautilus_github_docs/api_reference/model/) - 数据模型
- [`trading.md`](docs/nautilus_github_docs/api_reference/trading.md) - 交易接口

### **开发指南** (`developer_guide/`)
- [`adapters.md`](docs/nautilus_github_docs/developer_guide/adapters.md) - 适配器开发
- [`rust.md`](docs/nautilus_github_docs/developer_guide/rust.md) - Rust 开发
- [`testing.md`](docs/nautilus_github_docs/developer_guide/testing.md) - 测试指南

### **入门指南** (`getting_started/`)
- 安装和配置
- 第一个策略
- 第一个适配器

---

## 🚀 **最佳实践**

### **代码质量**
- 使用类型提示 (Python) 或强类型 (Rust)
- 遵循 Nautilus 命名约定
- 实现适当的错误处理
- 编写全面的测试

### **性能优化**
- 使用固定点运算进行金融计算
- 合理使用缓存
- 避免阻塞操作
- 优化数据聚合

### **安全性**
- 验证所有输入数据
- 使用 fail-fast 策略
- 保护 API 密钥
- 实现适当的风险检查

---

## 📞 **获取帮助**

### **资源顺序**
1. **此索引文件** - 首选参考
2. **具体概念文档** - 深入理解
3. **API 参考** - 接口详情
4. **开发指南** - 实现细节
5. **示例代码** - 实践参考

### **调试流程**
1. 检查日志输出
2. 验证配置参数
3. 确认数据流
4. 测试组件隔离
5. 查阅相关文档

---

> **💡 提示**: 每次开发前都先快速浏览此索引，确定需要查阅的具体文档，然后深入相关章节。这样可以确保开发符合 NautilusTrader 的架构模式和最佳实践。

---

**📅 最后更新**: 2026年3月28日  
**🎯 适用版本**: NautilusTrader 当前版本  
**📍 项目路径**: `d:/projects/Crazytra/`
