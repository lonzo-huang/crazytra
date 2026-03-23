"""
Polymarket Data Client for Nautilus Trader

提供 Polymarket 预测市场的实时订单簿数据。
"""

import asyncio
from decimal import Decimal
from typing import Optional

import httpx
from nautilus_trader.adapters.env import get_env_key
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import MessageBus
from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model.data import OrderBookDelta
from nautilus_trader.model.data import OrderBookDeltas
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import BookAction
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


POLYMARKET_VENUE = Venue("POLYMARKET")
CLOB_API_BASE = "https://clob.polymarket.com"
POLL_INTERVAL_SECS = 5


class PolymarketInstrument(Instrument):
    """Polymarket 预测市场工具"""
    
    def __init__(
        self,
        instrument_id: InstrumentId,
        condition_id: str,
        asset_id: str,
        question: str,
        ts_event: int,
        ts_init: int,
    ):
        super().__init__(
            instrument_id=instrument_id,
            raw_symbol=instrument_id.symbol,
            asset_class=None,
            quote_currency=None,
            is_inverse=False,
            price_precision=4,
            size_precision=2,
            price_increment=Price.from_str("0.0001"),
            size_increment=Quantity.from_str("0.01"),
            multiplier=Quantity.from_int(1),
            lot_size=None,
            max_quantity=None,
            min_quantity=Quantity.from_str("0.01"),
            max_price=Price.from_str("1.0000"),
            min_price=Price.from_str("0.0001"),
            margin_init=Decimal("0"),
            margin_maint=Decimal("0"),
            maker_fee=Decimal("0.002"),
            taker_fee=Decimal("0.002"),
            ts_event=ts_event,
            ts_init=ts_init,
            info={"condition_id": condition_id, "asset_id": asset_id, "question": question},
        )
        
        self.condition_id = condition_id
        self.asset_id = asset_id
        self.question = question


class PolymarketDataClient(LiveMarketDataClient):
    """
    Polymarket 数据客户端
    
    通过 CLOB API 轮询订单簿数据并转换为 Nautilus 格式。
    """
    
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        client: httpx.AsyncClient,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
        api_key: Optional[str] = None,
    ):
        super().__init__(
            loop=loop,
            client_id=ClientId(POLYMARKET_VENUE.value),
            venue=POLYMARKET_VENUE,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
        )
        
        self._client = client
        self._api_key = api_key or get_env_key("POLYMARKET_API_KEY")
        self._poll_tasks: dict[InstrumentId, asyncio.Task] = {}
        
        self._log.info("PolymarketDataClient initialized")
    
    async def _connect(self) -> None:
        self._log.info("Connecting to Polymarket CLOB API...")
        self._log.info(f"CLOB API: {CLOB_API_BASE}")
    
    async def _disconnect(self) -> None:
        self._log.info("Disconnecting from Polymarket...")
        
        for task in self._poll_tasks.values():
            task.cancel()
        
        self._poll_tasks.clear()
    
    async def _subscribe_quote_ticks(self, instrument_id: InstrumentId) -> None:
        """订阅报价 tick"""
        if instrument_id in self._poll_tasks:
            self._log.warning(f"Already subscribed to {instrument_id}")
            return
        
        instrument = self._cache.instrument(instrument_id)
        if not isinstance(instrument, PolymarketInstrument):
            self._log.error(f"Instrument {instrument_id} is not a PolymarketInstrument")
            return
        
        task = self._loop.create_task(self._poll_orderbook(instrument))
        self._poll_tasks[instrument_id] = task
        
        self._log.info(f"Subscribed to quote ticks for {instrument_id}")
    
    async def _unsubscribe_quote_ticks(self, instrument_id: InstrumentId) -> None:
        """取消订阅报价 tick"""
        task = self._poll_tasks.pop(instrument_id, None)
        if task:
            task.cancel()
            self._log.info(f"Unsubscribed from quote ticks for {instrument_id}")
    
    async def _poll_orderbook(self, instrument: PolymarketInstrument) -> None:
        """轮询订单簿"""
        self._log.info(
            f"Starting orderbook polling for {instrument.id} "
            f"(condition_id={instrument.condition_id})"
        )
        
        while True:
            try:
                await asyncio.sleep(POLL_INTERVAL_SECS)
                
                orderbook = await self._fetch_orderbook(
                    instrument.condition_id,
                    instrument.asset_id,
                )
                
                if orderbook:
                    await self._process_orderbook(instrument, orderbook)
                    
            except asyncio.CancelledError:
                self._log.info(f"Polling cancelled for {instrument.id}")
                break
            except Exception as e:
                self._log.error(f"Error polling orderbook for {instrument.id}: {e}")
                await asyncio.sleep(10)
    
    async def _fetch_orderbook(
        self,
        condition_id: str,
        asset_id: str,
    ) -> Optional[dict]:
        """获取订单簿"""
        url = f"{CLOB_API_BASE}/book"
        params = {
            "market": condition_id,
            "asset_id": asset_id,
            "side": "all",
        }
        
        headers = {}
        if self._api_key:
            headers["POLYMARKET_API_KEY"] = self._api_key
        
        try:
            response = await self._client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self._log.error(f"Failed to fetch orderbook: {e}")
            return None
    
    async def _process_orderbook(
        self,
        instrument: PolymarketInstrument,
        orderbook: dict,
    ) -> None:
        """处理订单簿数据"""
        bids = orderbook.get("bids", [])
        asks = orderbook.get("asks", [])
        
        if not bids or not asks:
            return
        
        # 获取最优买卖价
        best_bid = Decimal(bids[0]["price"])
        best_ask = Decimal(asks[0]["price"])
        best_bid_size = Decimal(bids[0]["size"])
        best_ask_size = Decimal(asks[0]["size"])
        
        # 时间戳
        timestamp_ms = orderbook.get("timestamp", None)
        if timestamp_ms:
            ts_event = millis_to_nanos(timestamp_ms)
        else:
            ts_event = self._clock.timestamp_ns()
        
        ts_init = self._clock.timestamp_ns()
        
        # 创建 QuoteTick
        quote_tick = QuoteTick(
            instrument_id=instrument.id,
            bid_price=Price.from_str(str(best_bid)),
            ask_price=Price.from_str(str(best_ask)),
            bid_size=Quantity.from_str(str(best_bid_size)),
            ask_size=Quantity.from_str(str(best_ask_size)),
            ts_event=ts_event,
            ts_init=ts_init,
        )
        
        self._handle_data(quote_tick)
    
    async def _request_instrument(
        self,
        instrument_id: InstrumentId,
        correlation_id: UUID4,
    ) -> None:
        """请求工具信息（从缓存加载）"""
        instrument = self._cache.instrument(instrument_id)
        if instrument:
            self._handle_data_response(
                data_type=Instrument,
                data=instrument,
                correlation_id=correlation_id,
            )
        else:
            self._log.error(f"Instrument {instrument_id} not found in cache")
    
    async def _request_instruments(
        self,
        venue: Venue,
        correlation_id: UUID4,
    ) -> None:
        """请求所有工具"""
        instruments = self._cache.instruments(venue=venue)
        
        self._handle_data_response(
            data_type=Instrument,
            data=instruments,
            correlation_id=correlation_id,
        )
    
    async def _request_quote_ticks(
        self,
        instrument_id: InstrumentId,
        limit: int,
        correlation_id: UUID4,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> None:
        """请求历史 quote ticks（Polymarket 不支持）"""
        self._log.warning("Historical quote ticks not supported for Polymarket")
        self._handle_data_response(
            data_type=QuoteTick,
            data=[],
            correlation_id=correlation_id,
        )
