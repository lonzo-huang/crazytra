# Nautilus Trader 自定义适配器

本目录包含为 Nautilus Trader 开发的自定义适配器。

## Polymarket 适配器

Polymarket 是一个去中心化的预测市场平台。此适配器允许 Nautilus Trader 连接到 Polymarket 并交易预测市场。

### 功能特性

- ✅ **实时订单簿数据**：通过 CLOB API 轮询订单簿
- ✅ **纸面交易**：完整的纸面交易模拟
- ✅ **QuoteTick 生成**：将订单簿转换为 Nautilus QuoteTick
- 🚧 **实盘交易**：待实现（需要 API 签名）

### 架构

```
PolymarketDataClient
├── 轮询 CLOB API (/book endpoint)
├── 转换订单簿为 QuoteTick
└── 发布到 Nautilus MessageBus

PolymarketExecutionClient
├── 纸面交易模拟
│   ├── 余额管理
│   ├── 持仓跟踪
│   └── 订单成交模拟
└── 实盘交易（待实现）
    └── CLOB API 订单提交
```

### 使用方法

#### 1. 安装依赖

```bash
pip install nautilus_trader httpx
```

#### 2. 配置环境变量

```bash
# 可选：Polymarket API Key（提高速率限制）
export POLYMARKET_API_KEY="your_api_key"
export POLYMARKET_API_SECRET="your_api_secret"
```

#### 3. 定义市场

```python
from adapters.polymarket_config import PolymarketMarketConfig

markets = [
    PolymarketMarketConfig(
        condition_id="0x1234...",  # 从 Polymarket 获取
        asset_id="0xabcd...",      # 从 Polymarket 获取
        slug="will-btc-hit-100k",
        question="Will Bitcoin hit $100k by end of 2024?",
    ),
]
```

#### 4. 创建客户端

```python
from adapters.polymarket_data import PolymarketDataClient
from adapters.polymarket_exec import PolymarketExecutionClient

# 数据客户端
data_client = PolymarketDataClient(
    loop=loop,
    client=http_client,
    msgbus=msgbus,
    cache=cache,
    clock=clock,
    api_key=api_key,
)

# 执行客户端（纸面交易）
exec_client = PolymarketExecutionClient(
    loop=loop,
    client=http_client,
    msgbus=msgbus,
    cache=cache,
    clock=clock,
    paper_trading=True,
)
```

#### 5. 订阅数据

```python
instrument_id = InstrumentId.from_str("WILL_BTC_HIT_100K.POLYMARKET")
await data_client.subscribe_quote_ticks(instrument_id)
```

### 示例

完整示例见 `examples/polymarket_example.py`：

```bash
cd nautilus-core
python examples/polymarket_example.py
```

### 数据格式

#### Polymarket 订单簿 → Nautilus QuoteTick

```python
# Polymarket CLOB API 响应
{
    "market": "0x1234...",
    "asset_id": "0xabcd...",
    "bids": [
        {"price": "0.65", "size": "1000.00"},
        {"price": "0.64", "size": "500.00"}
    ],
    "asks": [
        {"price": "0.66", "size": "800.00"}
    ],
    "timestamp": 1704067200000
}

# 转换为 Nautilus QuoteTick
QuoteTick(
    instrument_id=InstrumentId("WILL_BTC_HIT_100K.POLYMARKET"),
    bid_price=Price("0.6500"),
    ask_price=Price("0.6600"),
    bid_size=Quantity("1000.00"),
    ask_size=Quantity("800.00"),
    ts_event=1704067200000000000,  # 纳秒
    ts_init=1704067200000050000,
)
```

### 配置参数

#### PolymarketDataClientConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `api_key` | str | None | Polymarket API Key（可选） |
| `poll_interval_secs` | int | 5 | 订单簿轮询间隔（秒） |

#### PolymarketExecClientConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `api_key` | str | None | Polymarket API Key |
| `api_secret` | str | None | Polymarket API Secret |
| `paper_trading` | bool | True | 是否使用纸面交易 |
| `initial_balance` | Decimal | 10000.00 | 纸面交易初始余额（USDC） |

### 获取 Polymarket 市场信息

#### 方法 1：通过 Polymarket 网站

1. 访问 https://polymarket.com
2. 选择一个市场
3. 从 URL 或 API 获取 `condition_id` 和 `asset_id`

#### 方法 2：通过 CLOB API

```bash
# 获取所有活跃市场
curl https://clob.polymarket.com/markets

# 获取特定市场的订单簿
curl "https://clob.polymarket.com/book?market=0x1234...&asset_id=0xabcd..."
```

### 纸面交易 vs 实盘交易

#### 纸面交易（默认）

- ✅ 完全模拟，无需 API 密钥
- ✅ 模拟余额和持仓
- ✅ 模拟订单成交（带滑点）
- ✅ 适合策略开发和测试

#### 实盘交易（待实现）

- ⚠️ 需要 Polymarket API 密钥和签名
- ⚠️ 需要实现 CLOB API 订单提交
- ⚠️ 需要钱包集成（MetaMask / WalletConnect）

### 与 RedisBridgeActor 集成

Polymarket 数据会自动通过 RedisBridgeActor 发布到 Redis：

```python
# Redis topic 格式
market.tick.polymarket.will-btc-hit-100k

# Redis 消息格式
{
    "symbol": "WILL-BTC-HIT-100K",
    "exchange": "polymarket",
    "timestamp_ns": 1704067200000000000,
    "bid": "0.6500",
    "ask": "0.6600",
    "last": "0.6550"
}
```

### 限制和注意事项

1. **轮询延迟**：默认 5 秒轮询间隔，不适合高频交易
2. **无 WebSocket**：Polymarket CLOB API 不提供 WebSocket
3. **速率限制**：无 API Key 时有速率限制
4. **实盘交易**：需要额外开发签名逻辑

### 开发路线图

- [x] 数据客户端（订单簿轮询）
- [x] 纸面交易执行客户端
- [x] QuoteTick 生成
- [ ] 实盘交易订单提交
- [ ] API 签名和认证
- [ ] 订单状态查询
- [ ] 历史数据支持
- [ ] WebSocket 支持（如果 Polymarket 提供）

### 故障排查

#### 问题：无法获取订单簿

```
Failed to fetch orderbook: 401 Unauthorized
```

**解决方案**：检查 API Key 是否正确设置。

#### 问题：轮询间隔太长

**解决方案**：调整 `poll_interval_secs` 参数（注意速率限制）。

```python
PolymarketDataClientConfig(
    poll_interval_secs=2,  # 减少到 2 秒
)
```

### 参考资料

- [Polymarket 官网](https://polymarket.com)
- [CLOB API 文档](https://docs.polymarket.com)
- [Nautilus Trader 文档](https://nautilustrader.io)
