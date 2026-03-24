"""
Alpaca 交易所适配器

Alpaca 是一个免费的美股交易平台，提供官方 API。
适合用于自动化交易和算法交易。

官方文档: https://alpaca.markets/docs/
"""

import asyncio
from decimal import Decimal
from typing import Optional
import aiohttp
from datetime import datetime

from nautilus_trader.adapters.base import DataClient, ExecutionClient
from nautilus_trader.model.data import QuoteTick, TradeTick, Bar
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.identifiers import InstrumentId, Venue, Symbol
from nautilus_trader.model.enums import OrderSide, OrderType, TimeInForce
from nautilus_trader.model.orders import Order
from nautilus_trader.core.datetime import unix_nanos_to_dt


class AlpacaConfig:
    """Alpaca 配置"""
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        is_paper: bool = True,
        base_url: Optional[str] = None,
        data_url: Optional[str] = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_paper = is_paper
        
        # API 端点
        if is_paper:
            self.base_url = base_url or "https://paper-api.alpaca.markets"
            self.data_url = data_url or "https://data.alpaca.markets"
        else:
            self.base_url = base_url or "https://api.alpaca.markets"
            self.data_url = data_url or "https://data.alpaca.markets"
        
        # WebSocket 端点
        self.ws_url = "wss://stream.data.alpaca.markets/v2/iex" if not is_paper else "wss://stream.data.alpaca.markets/v2/test"
        
        # 请求头
        self.headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
        }


class AlpacaDataClient(DataClient):
    """Alpaca 数据客户端"""
    
    def __init__(self, config: AlpacaConfig, logger):
        super().__init__(logger=logger)
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._subscriptions = set()
    
    async def _connect(self):
        """连接到 Alpaca"""
        self._logger.info("Connecting to Alpaca...")
        
        # 创建 HTTP 会话
        self._session = aiohttp.ClientSession(headers=self.config.headers)
        
        # 测试连接
        async with self._session.get(f"{self.config.base_url}/v2/account") as resp:
            if resp.status != 200:
                raise ConnectionError(f"Failed to connect to Alpaca: {await resp.text()}")
            account = await resp.json()
            self._logger.info(f"Connected to Alpaca account: {account['account_number']}")
        
        # 连接 WebSocket
        await self._connect_websocket()
    
    async def _connect_websocket(self):
        """连接 WebSocket 数据流"""
        self._ws = await self._session.ws_connect(self.config.ws_url)
        
        # 认证
        auth_msg = {
            "action": "auth",
            "key": self.config.api_key,
            "secret": self.config.api_secret
        }
        await self._ws.send_json(auth_msg)
        
        # 等待认证响应
        auth_response = await self._ws.receive_json()
        if auth_response[0].get("T") != "success":
            raise ConnectionError(f"WebSocket auth failed: {auth_response}")
        
        self._logger.info("WebSocket connected and authenticated")
        
        # 启动消息处理循环
        asyncio.create_task(self._handle_ws_messages())
    
    async def _disconnect(self):
        """断开连接"""
        self._logger.info("Disconnecting from Alpaca...")
        
        if self._ws:
            await self._ws.close()
        
        if self._session:
            await self._session.close()
    
    async def _subscribe_quote_ticks(self, instrument_id: InstrumentId):
        """订阅报价"""
        symbol = instrument_id.symbol.value
        
        # 订阅报价和交易
        subscribe_msg = {
            "action": "subscribe",
            "quotes": [symbol],
            "trades": [symbol]
        }
        await self._ws.send_json(subscribe_msg)
        
        self._subscriptions.add(symbol)
        self._logger.info(f"Subscribed to {symbol}")
    
    async def _unsubscribe_quote_ticks(self, instrument_id: InstrumentId):
        """取消订阅"""
        symbol = instrument_id.symbol.value
        
        unsubscribe_msg = {
            "action": "unsubscribe",
            "quotes": [symbol],
            "trades": [symbol]
        }
        await self._ws.send_json(unsubscribe_msg)
        
        self._subscriptions.discard(symbol)
        self._logger.info(f"Unsubscribed from {symbol}")
    
    async def _handle_ws_messages(self):
        """处理 WebSocket 消息"""
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    
                    for item in data:
                        msg_type = item.get("T")
                        
                        if msg_type == "q":  # Quote
                            await self._handle_quote(item)
                        elif msg_type == "t":  # Trade
                            await self._handle_trade(item)
                        
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self._logger.error(f"WebSocket error: {msg}")
                    
        except Exception as e:
            self._logger.error(f"WebSocket message handling error: {e}")
    
    async def _handle_quote(self, data: dict):
        """处理报价数据"""
        symbol = data["S"]
        
        # 创建 InstrumentId
        instrument_id = InstrumentId(
            symbol=Symbol(symbol),
            venue=Venue("ALPACA")
        )
        
        # 创建 QuoteTick
        quote_tick = QuoteTick(
            instrument_id=instrument_id,
            bid_price=Decimal(str(data["bp"])),
            ask_price=Decimal(str(data["ap"])),
            bid_size=Decimal(str(data["bs"])),
            ask_size=Decimal(str(data["as"])),
            ts_event=self._parse_timestamp(data["t"]),
            ts_init=self._clock.timestamp_ns(),
        )
        
        # 发布到 Nautilus
        self._handle_data(quote_tick)
    
    async def _handle_trade(self, data: dict):
        """处理成交数据"""
        symbol = data["S"]
        
        instrument_id = InstrumentId(
            symbol=Symbol(symbol),
            venue=Venue("ALPACA")
        )
        
        trade_tick = TradeTick(
            instrument_id=instrument_id,
            price=Decimal(str(data["p"])),
            size=Decimal(str(data["s"])),
            aggressor_side=OrderSide.BUY,  # Alpaca 不提供方向
            trade_id=str(data["i"]),
            ts_event=self._parse_timestamp(data["t"]),
            ts_init=self._clock.timestamp_ns(),
        )
        
        self._handle_data(trade_tick)
    
    def _parse_timestamp(self, timestamp_str: str) -> int:
        """解析时间戳"""
        # Alpaca 时间戳格式: "2024-01-01T12:00:00.000000Z"
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1_000_000_000)


class AlpacaExecutionClient(ExecutionClient):
    """Alpaca 执行客户端"""
    
    def __init__(self, config: AlpacaConfig, logger):
        super().__init__(logger=logger)
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._account_id: Optional[str] = None
    
    async def _connect(self):
        """连接"""
        self._logger.info("Connecting Alpaca execution client...")
        
        self._session = aiohttp.ClientSession(headers=self.config.headers)
        
        # 获取账户信息
        async with self._session.get(f"{self.config.base_url}/v2/account") as resp:
            if resp.status != 200:
                raise ConnectionError(f"Failed to get account: {await resp.text()}")
            account = await resp.json()
            self._account_id = account["account_number"]
            
            self._logger.info(f"Execution client connected, account: {self._account_id}")
            self._logger.info(f"Buying power: ${account['buying_power']}")
            self._logger.info(f"Cash: ${account['cash']}")
    
    async def _disconnect(self):
        """断开连接"""
        if self._session:
            await self._session.close()
    
    async def _submit_order(self, command):
        """提交订单"""
        order: Order = command.order
        
        # 构建订单请求
        order_data = {
            "symbol": order.instrument_id.symbol.value,
            "qty": str(order.quantity),
            "side": "buy" if order.side == OrderSide.BUY else "sell",
            "type": self._convert_order_type(order.order_type),
            "time_in_force": self._convert_time_in_force(order.time_in_force),
        }
        
        # 限价单需要价格
        if order.order_type == OrderType.LIMIT:
            order_data["limit_price"] = str(order.price)
        
        # 止损单需要止损价
        if order.order_type == OrderType.STOP_MARKET:
            order_data["stop_price"] = str(order.trigger_price)
        
        self._logger.info(f"Submitting order: {order_data}")
        
        # 提交订单
        async with self._session.post(
            f"{self.config.base_url}/v2/orders",
            json=order_data
        ) as resp:
            if resp.status not in [200, 201]:
                error_text = await resp.text()
                self._logger.error(f"Order submission failed: {error_text}")
                # 生成订单拒绝事件
                self._generate_order_rejected(order, error_text)
                return
            
            alpaca_order = await resp.json()
            self._logger.info(f"Order submitted: {alpaca_order['id']}")
            
            # 生成订单接受事件
            self._generate_order_accepted(order, alpaca_order["id"])
    
    async def _cancel_order(self, command):
        """取消订单"""
        order = command.order
        
        # Alpaca 订单 ID 存储在 venue_order_id 中
        alpaca_order_id = order.venue_order_id.value
        
        async with self._session.delete(
            f"{self.config.base_url}/v2/orders/{alpaca_order_id}"
        ) as resp:
            if resp.status == 204:
                self._logger.info(f"Order cancelled: {alpaca_order_id}")
                self._generate_order_canceled(order)
            else:
                error_text = await resp.text()
                self._logger.error(f"Cancel failed: {error_text}")
    
    def _convert_order_type(self, order_type: OrderType) -> str:
        """转换订单类型"""
        mapping = {
            OrderType.MARKET: "market",
            OrderType.LIMIT: "limit",
            OrderType.STOP_MARKET: "stop",
            OrderType.STOP_LIMIT: "stop_limit",
        }
        return mapping.get(order_type, "market")
    
    def _convert_time_in_force(self, tif: TimeInForce) -> str:
        """转换有效期"""
        mapping = {
            TimeInForce.DAY: "day",
            TimeInForce.GTC: "gtc",
            TimeInForce.IOC: "ioc",
            TimeInForce.FOK: "fok",
        }
        return mapping.get(tif, "day")


# 使用示例
"""
from alpaca_adapter import AlpacaConfig, AlpacaDataClient, AlpacaExecutionClient

# 配置
config = AlpacaConfig(
    api_key="YOUR_API_KEY",
    api_secret="YOUR_API_SECRET",
    is_paper=True  # 纸面交易
)

# 在 Nautilus 配置中使用
from nautilus_trader.config import TradingNodeConfig

trading_config = TradingNodeConfig(
    data_clients={
        "ALPACA": AlpacaDataClient(config, logger)
    },
    exec_clients={
        "ALPACA": AlpacaExecutionClient(config, logger)
    },
    # ... 其他配置
)
"""
