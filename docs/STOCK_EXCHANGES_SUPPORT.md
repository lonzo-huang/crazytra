# 股票市场交易所支持

## 概述

Crazytra 支持多个主流股票交易平台，让用户可以通过 API 进行自动化交易。

## 支持的股票交易所

### 1. Interactive Brokers (IB)

**状态**: ✅ 完全支持（Nautilus 原生）

**覆盖市场**:
- 美股、港股、A股
- 期货、期权、外汇
- 全球 150+ 市场

**API 类型**: TWS API / IB Gateway

**配置示例**:
```python
from nautilus_trader.adapters.interactive_brokers import InteractiveBrokersDataClientConfig
from nautilus_trader.adapters.interactive_brokers import InteractiveBrokersExecClientConfig

# 数据客户端配置
ib_data_config = InteractiveBrokersDataClientConfig(
    username="your_username",
    password="your_password",
    trading_mode="paper",  # paper 或 live
    gateway_host="127.0.0.1",
    gateway_port=4001,  # paper: 4001, live: 4000
)

# 执行客户端配置
ib_exec_config = InteractiveBrokersExecClientConfig(
    username="your_username",
    password="your_password",
    trading_mode="paper",
    gateway_host="127.0.0.1",
    gateway_port=4001,
    account_id="DU123456",  # 你的账户 ID
)
```

**优点**:
- ✅ 覆盖全球市场
- ✅ 专业级交易平台
- ✅ 低佣金
- ✅ 完善的 API

**缺点**:
- ❌ 需要最低存款（$10,000 实盘）
- ❌ 设置相对复杂
- ❌ 需要运行 IB Gateway

**费用**:
- 美股：$0.005/股（最低 $1）
- 数据费：免费（有交易）或 $10/月

---

### 2. Alpaca

**状态**: ✅ 推荐（易用、免费）

**覆盖市场**:
- 美股
- 加密货币

**API 类型**: REST + WebSocket

**实现方式**: 自定义适配器

**配置示例**:
```python
# alpaca_adapter.py
from nautilus_trader.adapters.alpaca import AlpacaDataClientConfig
from nautilus_trader.adapters.alpaca import AlpacaExecClientConfig

alpaca_data_config = AlpacaDataClientConfig(
    api_key="your_api_key",
    api_secret="your_api_secret",
    is_paper=True,  # 纸面交易
)

alpaca_exec_config = AlpacaExecClientConfig(
    api_key="your_api_key",
    api_secret="your_api_secret",
    is_paper=True,
)
```

**优点**:
- ✅ 完全免费（无佣金、无最低存款）
- ✅ 简单易用的 API
- ✅ 支持纸面交易
- ✅ 实时数据免费

**缺点**:
- ❌ 仅支持美股
- ❌ 不支持期权、期货

**费用**: 完全免费

---

### 3. Robinhood

**状态**: 🚧 需要自定义适配器

**覆盖市场**:
- 美股
- 期权
- 加密货币

**API 类型**: 非官方 API（robin_stocks）

**实现方式**: 自定义适配器

**配置示例**:
```python
# robinhood_adapter.py
import robin_stocks.robinhood as rh

class RobinhoodAdapter:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        
    def login(self):
        """登录 Robinhood"""
        rh.login(self.username, self.password)
    
    def get_quote(self, symbol):
        """获取报价"""
        return rh.stocks.get_latest_price(symbol)
    
    def place_order(self, symbol, quantity, side, order_type='market'):
        """下单"""
        if side == 'buy':
            return rh.orders.order_buy_market(symbol, quantity)
        else:
            return rh.orders.order_sell_market(symbol, quantity)
```

**优点**:
- ✅ 零佣金
- ✅ 用户界面友好
- ✅ 支持碎股交易

**缺点**:
- ❌ 没有官方 API
- ❌ 使用非官方库有风险
- ❌ 可能随时失效
- ❌ 功能受限

**费用**: 免费

**⚠️ 重要提示**: Robinhood 没有官方 API，使用第三方库存在账户被封风险。建议使用 Alpaca 或 Interactive Brokers。

---

### 4. Trading212

**状态**: 🚧 需要自定义适配器

**覆盖市场**:
- 美股、欧股
- ETF
- 外汇、商品

**API 类型**: 官方 API（有限功能）

**实现方式**: 自定义适配器

**配置示例**:
```python
# trading212_adapter.py
import requests

class Trading212Adapter:
    BASE_URL = "https://live.trading212.com/api/v0"
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
    
    def get_account(self):
        """获取账户信息"""
        response = requests.get(
            f"{self.BASE_URL}/equity/account/cash",
            headers=self.headers
        )
        return response.json()
    
    def get_positions(self):
        """获取持仓"""
        response = requests.get(
            f"{self.BASE_URL}/equity/portfolio",
            headers=self.headers
        )
        return response.json()
    
    def place_order(self, ticker, quantity, side):
        """下单"""
        payload = {
            "ticker": ticker,
            "quantity": quantity,
            "orderType": "MARKET"
        }
        
        endpoint = "buy" if side == "buy" else "sell"
        response = requests.post(
            f"{self.BASE_URL}/equity/orders/{endpoint}",
            headers=self.headers,
            json=payload
        )
        return response.json()
```

**优点**:
- ✅ 零佣金
- ✅ 支持欧洲市场
- ✅ 官方 API

**缺点**:
- ❌ API 功能有限
- ❌ 不支持实时数据流
- ❌ 仅支持市价单

**费用**: 免费

---

### 5. Tiger Brokers（老虎证券）

**状态**: 🚧 需要自定义适配器

**覆盖市场**:
- 美股、港股、A股
- 期货、期权

**API 类型**: 官方 OpenAPI

**实现方式**: 自定义适配器

**配置示例**:
```python
# tiger_adapter.py
from tigeropen.common.consts import Language, Market
from tigeropen.tiger_open_config import TigerOpenClientConfig
from tigeropen.quote.quote_client import QuoteClient
from tigeropen.trade.trade_client import TradeClient

class TigerBrokersAdapter:
    def __init__(self, tiger_id, account, private_key):
        self.config = TigerOpenClientConfig(sandbox_debug=False)
        self.config.private_key = private_key
        self.config.tiger_id = tiger_id
        self.config.account = account
        self.config.language = Language.zh_CN
        
        self.quote_client = QuoteClient(self.config)
        self.trade_client = TradeClient(self.config)
    
    def get_quote(self, symbols, market=Market.US):
        """获取报价"""
        return self.quote_client.get_market_data(symbols, market=market)
    
    def place_order(self, symbol, quantity, side, order_type='MKT'):
        """下单"""
        from tigeropen.trade.domain import Order
        
        order = Order()
        order.account = self.config.account
        order.symbol = symbol
        order.action = 'BUY' if side == 'buy' else 'SELL'
        order.order_type = order_type
        order.quantity = quantity
        
        return self.trade_client.place_order(order)
```

**优点**:
- ✅ 支持亚洲市场
- ✅ 官方 API 完善
- ✅ 支持多种订单类型

**缺点**:
- ❌ 需要开户
- ❌ 有最低存款要求

**费用**:
- 美股：$0.01/股（最低 $0.99）
- 港股：0.03%（最低 HK$3）

---

### 6. Webull

**状态**: 🚧 需要自定义适配器

**覆盖市场**:
- 美股
- 期权
- 加密货币

**API 类型**: 非官方 API

**实现方式**: 自定义适配器（webull 库）

**配置示例**:
```python
# webull_adapter.py
from webull import webull

class WebullAdapter:
    def __init__(self):
        self.wb = webull()
    
    def login(self, username, password, device_id):
        """登录"""
        self.wb.login(username, password, device_id=device_id)
    
    def get_quote(self, symbol):
        """获取报价"""
        return self.wb.get_quote(symbol)
    
    def place_order(self, symbol, quantity, side, price=None):
        """下单"""
        if side == 'buy':
            return self.wb.place_order(
                stock=symbol,
                action='BUY',
                orderType='MKT' if not price else 'LMT',
                quant=quantity,
                price=price
            )
```

**优点**:
- ✅ 零佣金
- ✅ 支持盘前盘后交易

**缺点**:
- ❌ 没有官方 API
- ❌ 使用第三方库有风险

**费用**: 免费

---

## 推荐方案

### 方案 1：最简单（推荐新手）

```yaml
交易所: Alpaca
优点:
  - 完全免费
  - 简单易用
  - 官方 API
  - 支持纸面交易
适合: 美股交易、学习测试
```

### 方案 2：最专业（推荐专业用户）

```yaml
交易所: Interactive Brokers
优点:
  - 全球市场
  - 低佣金
  - 专业平台
  - Nautilus 原生支持
适合: 全球市场、大资金、专业交易
```

### 方案 3：多市场组合

```yaml
组合:
  - Alpaca: 美股
  - Binance: 加密货币
  - Interactive Brokers: 全球股票、期货
优点: 覆盖所有主要市场
```

## 实现优先级

### 第一优先级（推荐实现）

1. **Alpaca** - 最简单、免费、官方 API
2. **Interactive Brokers** - 已有 Nautilus 支持

### 第二优先级

3. **Trading212** - 欧洲市场、官方 API
4. **Tiger Brokers** - 亚洲市场、官方 API

### 第三优先级（不推荐）

5. **Robinhood** - 无官方 API，有风险
6. **Webull** - 无官方 API，有风险

## 技术实现

### Nautilus 自定义适配器模板

```python
# custom_exchange_adapter.py
from nautilus_trader.adapters.base import DataClient, ExecutionClient
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.instruments import Equity

class CustomDataClient(DataClient):
    """自定义数据客户端"""
    
    async def _connect(self):
        """连接到交易所"""
        # 实现连接逻辑
        pass
    
    async def _disconnect(self):
        """断开连接"""
        pass
    
    async def _subscribe_quote_ticks(self, instrument_id):
        """订阅报价"""
        # 实现订阅逻辑
        pass

class CustomExecutionClient(ExecutionClient):
    """自定义执行客户端"""
    
    async def _connect(self):
        """连接"""
        pass
    
    async def _submit_order(self, command):
        """提交订单"""
        # 实现下单逻辑
        pass
    
    async def _cancel_order(self, command):
        """取消订单"""
        pass
```

### 租户配置交易所连接

```go
// 租户交易所连接
type TenantExchangeConnection struct {
    TenantID     string
    Exchange     string  // "alpaca", "ib", "trading212", "tiger"
    APIKey       string  // 加密存储
    APISecret    string  // 加密存储
    AccountID    string  // 账户 ID
    IsPaper      bool    // 是否纸面交易
    Status       string  // "active", "disconnected"
}

// 支持的交易所
var SupportedExchanges = []string{
    "alpaca",
    "interactive_brokers",
    "trading212",
    "tiger_brokers",
    "binance",
    "polymarket",
}
```

## 安全建议

1. **API Key 安全**
   - 使用加密存储
   - 定期轮换
   - 限制 IP 白名单

2. **权限控制**
   - 只授予必要权限
   - 使用只读 API Key 测试
   - 生产环境使用独立 API Key

3. **资金安全**
   - 先用纸面交易测试
   - 设置每日交易限额
   - 启用风控规则

## 费用对比

| 交易所 | 美股佣金 | 最低存款 | 数据费 | 推荐度 |
|--------|----------|----------|--------|--------|
| **Alpaca** | $0 | $0 | $0 | ⭐⭐⭐⭐⭐ |
| **Interactive Brokers** | $0.005/股 | $0 | $0-$10 | ⭐⭐⭐⭐⭐ |
| **Robinhood** | $0 | $0 | $0 | ⭐⭐ |
| **Trading212** | $0 | $0 | $0 | ⭐⭐⭐⭐ |
| **Tiger Brokers** | $0.01/股 | 视市场 | $0 | ⭐⭐⭐⭐ |
| **Webull** | $0 | $0 | $0 | ⭐⭐ |

## 下一步

1. **立即可用**: Interactive Brokers（Nautilus 原生支持）
2. **快速实现**: Alpaca 适配器（1-2天）
3. **中期实现**: Trading212、Tiger Brokers 适配器（1周）
4. **不推荐**: Robinhood、Webull（非官方 API）

## 参考文档

- [Alpaca API 文档](https://alpaca.markets/docs/)
- [Interactive Brokers API](https://www.interactivebrokers.com/en/trading/ib-api.php)
- [Trading212 API](https://t212public-api-docs.redoc.ly/)
- [Tiger Brokers OpenAPI](https://quant.itigerup.com/openapi/)
- [Nautilus Trader 适配器开发](https://nautilustrader.io/docs/latest/integrations/adapters.html)
