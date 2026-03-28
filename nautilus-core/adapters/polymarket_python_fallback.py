"""
Polymarket Python Fallback Implementation
临时 Python 实现，用于在 Rust 模块构建完成前测试功能
"""

import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class MarketData:
    id: str
    condition_id: str
    question: str
    volume: float
    liquidity: float
    end_date: str
    active: bool
    category: str
    asset_ids: List[str]


@dataclass
class OrderBook:
    instrument_id: str
    bids: List[tuple]
    asks: List[tuple]
    last_update: datetime


class PolymarketPythonAdapter:
    """
    Polymarket Python 适配器（临时实现）
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.gamma_api_url = "https://gamma-api.polymarket.com"
        self.clob_api_url = "https://clob.polymarket.com"
        self.is_running = False
        self.session = None
        
    async def start(self) -> bool:
        """启动适配器"""
        try:
            self.session = aiohttp.ClientSession()
            self.is_running = True
            logger.info("Polymarket Python adapter started")
            return True
        except Exception as e:
            logger.error(f"Failed to start adapter: {e}")
            return False
    
    async def stop(self) -> None:
        """停止适配器"""
        if self.session:
            await self.session.close()
        self.is_running = False
        logger.info("Polymarket Python adapter stopped")
    
    async def fetch_markets(self) -> List[MarketData]:
        """获取市场数据"""
        if not self.session:
            logger.error("Session not initialized")
            return []
        
        try:
            params = {
                "active": "true",
                "limit": "100"
            }
            
            async with self.session.get(f"{self.gamma_api_url}/markets", params=params) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch markets: {response.status}")
                    return []
                
                data = await response.json()
                markets = []
                
                # API 返回的是列表，不是字典
                if isinstance(data, list):
                    markets_data = data
                else:
                    markets_data = data.get("markets", [])
                
                for market in markets_data:
                    market_data = MarketData(
                        id=market.get("id", ""),
                        condition_id=market.get("condition_id", ""),
                        question=market.get("question", ""),
                        volume=market.get("volume", 0.0),
                        liquidity=market.get("liquidity", 0.0),
                        end_date=market.get("end_date_iso", ""),
                        active=market.get("active", False),
                        category=market.get("category", "other"),
                        asset_ids=market.get("clob_token_ids", [])
                    )
                    markets.append(market_data)
                
                logger.info(f"Fetched {len(markets)} markets")
                return markets
                
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []
    
    async def get_order_book(self, asset_id: str) -> Optional[OrderBook]:
        """获取订单簿"""
        if not self.session:
            logger.error("Session not initialized")
            return None
        
        try:
            params = {"token_id": asset_id}
            
            async with self.session.get(f"{self.clob_api_url}/book", params=params) as response:
                if response.status != 200:
                    logger.warning(f"Order book not found for {asset_id}: {response.status}")
                    return None
                
                data = await response.json()
                
                bids = [(float(bid[0]), float(bid[1])) for bid in data.get("bids", [])]
                asks = [(float(ask[0]), float(ask[1])) for ask in data.get("asks", [])]
                
                order_book = OrderBook(
                    instrument_id=asset_id,
                    bids=bids,
                    asks=asks,
                    last_update=datetime.now()
                )
                
                logger.debug(f"Got order book for {asset_id}: {len(bids)} bids, {len(asks)} asks")
                return order_book
                
        except Exception as e:
            logger.error(f"Failed to get order book for {asset_id}: {e}")
            return None
    
    async def subscribe_asset(self, asset_id: str) -> bool:
        """订阅资产更新（Python 版本暂不支持 WebSocket）"""
        logger.info(f"Subscribed to asset (Python fallback): {asset_id}")
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """获取适配器状态"""
        return {
            "is_running": self.is_running,
            "rust_available": False,
            "python_fallback": True,
            "config": self.config,
        }


# 全局适配器实例
_polymarket_adapter: Optional[PolymarketPythonAdapter] = None


def get_polymarket_adapter(config: Optional[Dict[str, Any]] = None) -> PolymarketPythonAdapter:
    """获取全局 Polymarket 适配器实例"""
    global _polymarket_adapter
    
    if _polymarket_adapter is None:
        _polymarket_adapter = PolymarketPythonAdapter(config)
    
    return _polymarket_adapter


async def initialize_polymarket(config: Optional[Dict[str, Any]] = None) -> bool:
    """初始化 Polymarket 适配器"""
    adapter = get_polymarket_adapter(config)
    return await adapter.start()


# 测试函数
async def test_polymarket_python():
    """测试 Python 适配器"""
    logger.info("Testing Polymarket Python adapter...")
    
    adapter = get_polymarket_adapter()
    
    # 启动适配器
    if not await adapter.start():
        logger.error("Failed to start adapter")
        return
    
    try:
        # 测试获取市场数据
        markets = await adapter.fetch_markets()
        logger.info(f"Test: fetched {len(markets)} markets")
        
        # 显示前几个市场
        for i, market in enumerate(markets[:3]):
            logger.info(f"Market {i+1}: {market.question}")
            logger.info(f"  Volume: ${market.volume:,.2f}")
            logger.info(f"  Liquidity: ${market.liquidity:,.2f}")
        
        # 测试获取订单簿
        if markets:
            first_market = markets[0]
            if first_market.asset_ids:
                order_book = await adapter.get_order_book(first_market.asset_ids[0])
                if order_book:
                    logger.info(f"Test: got order book with {len(order_book.bids)} bids")
        
        logger.info("Polymarket Python adapter test completed")
        
    finally:
        await adapter.stop()


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_polymarket_python())
