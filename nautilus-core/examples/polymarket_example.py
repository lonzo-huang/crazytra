"""
Polymarket 适配器使用示例

展示如何使用 Polymarket 数据客户端和执行客户端。
"""

import asyncio
from decimal import Decimal

import httpx
from nautilus_trader.adapters.env import get_env_key
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import MessageBus
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TraderId

from adapters.polymarket_config import PolymarketDataClientConfig
from adapters.polymarket_config import PolymarketExecClientConfig
from adapters.polymarket_config import PolymarketMarketConfig
from adapters.polymarket_data import PolymarketDataClient
from adapters.polymarket_data import PolymarketInstrument
from adapters.polymarket_data import POLYMARKET_VENUE
from adapters.polymarket_exec import PolymarketExecutionClient


async def main():
    """主函数"""
    
    # 1. 定义要交易的 Polymarket 市场
    markets = [
        PolymarketMarketConfig(
            condition_id="0x1234567890abcdef",  # 替换为实际的 condition_id
            asset_id="0xabcdef1234567890",      # 替换为实际的 asset_id
            slug="will-btc-hit-100k",
            question="Will Bitcoin hit $100k by end of 2024?",
        ),
    ]
    
    # 2. 创建配置
    config = TradingNodeConfig(
        trader_id=TraderId("TESTER-001"),
        logging=LoggingConfig(log_level="INFO"),
        data_clients={
            "POLYMARKET": PolymarketDataClientConfig(
                api_key=get_env_key("POLYMARKET_API_KEY"),
                poll_interval_secs=5,
            ),
        },
        exec_clients={
            "POLYMARKET": PolymarketExecClientConfig(
                api_key=get_env_key("POLYMARKET_API_KEY"),
                api_secret=get_env_key("POLYMARKET_API_SECRET"),
                paper_trading=True,  # 纸面交易模式
                initial_balance=Decimal("10000.00"),
            ),
        },
        timeout_connection=30.0,
        timeout_reconciliation=10.0,
        timeout_portfolio=10.0,
        timeout_disconnection=10.0,
    )
    
    # 3. 创建交易节点
    node = TradingNode(config=config)
    
    # 4. 手动创建客户端（因为需要自定义适配器）
    loop = asyncio.get_event_loop()
    http_client = httpx.AsyncClient()
    
    # 创建数据客户端
    data_client = PolymarketDataClient(
        loop=loop,
        client=http_client,
        msgbus=node.msgbus,
        cache=node.cache,
        clock=node.clock,
        api_key=get_env_key("POLYMARKET_API_KEY"),
    )
    
    # 创建执行客户端
    exec_client = PolymarketExecutionClient(
        loop=loop,
        client=http_client,
        msgbus=node.msgbus,
        cache=node.cache,
        clock=node.clock,
        api_key=get_env_key("POLYMARKET_API_KEY"),
        api_secret=get_env_key("POLYMARKET_API_SECRET"),
        paper_trading=True,
    )
    
    # 5. 注册客户端到节点
    node.add_data_client(data_client)
    node.add_exec_client(exec_client)
    
    # 6. 添加 Polymarket 工具到缓存
    for market in markets:
        instrument = PolymarketInstrument(
            instrument_id=InstrumentId.from_str(market.to_instrument_id()),
            condition_id=market.condition_id,
            asset_id=market.asset_id,
            question=market.question,
            ts_event=node.clock.timestamp_ns(),
            ts_init=node.clock.timestamp_ns(),
        )
        node.cache.add_instrument(instrument)
    
    # 7. 启动节点
    try:
        await node.start()
        
        # 订阅市场数据
        for market in markets:
            instrument_id = InstrumentId.from_str(market.to_instrument_id())
            await data_client.subscribe_quote_ticks(instrument_id)
        
        print("Polymarket 适配器运行中...")
        print("按 Ctrl+C 停止")
        
        # 保持运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n正在停止...")
    finally:
        await node.stop()
        await http_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
