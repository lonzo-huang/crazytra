"""
Polymarket Adapter - Rust Bridge for MirrorQuant
连接 Rust DataEngine 和 Python StrategyEngine
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

try:
    # Import Rust module (will be built later)
    from nautilus_core.rust import PolymarketDataEngine, MarketData, QuoteTick, TradeTick, OrderBook
    RUST_AVAILABLE = True
except ImportError:
    logging.warning("Rust module not available, using Python fallback")
    RUST_AVAILABLE = False
    # Fallback classes for development
    from dataclasses import dataclass
    
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

logger = logging.getLogger(__name__)


class PolymarketRustAdapter:
    """
    Polymarket 适配器 - Rust 桥接层
    
    负责连接 Rust DataEngine 和 Python StrategyEngine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化适配器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.rust_engine = None
        self.is_running = False
        self.subscribed_assets = set()
        
        if RUST_AVAILABLE:
            try:
                self.rust_engine = PolymarketDataEngine(self.config)
                logger.info("Rust PolymarketDataEngine initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Rust engine: {e}")
                raise
        else:
            logger.warning("Using Python fallback implementation")
    
    async def start(self) -> bool:
        """启动适配器"""
        if not self.rust_engine:
            logger.error("Rust engine not available")
            return False
        
        try:
            # 启动 WebSocket 连接
            success = self.rust_engine.start_realtime()
            if success:
                self.is_running = True
                logger.info("Polymarket adapter started successfully")
                return True
            else:
                logger.error("Failed to start WebSocket connection")
                return False
        except Exception as e:
            logger.error(f"Failed to start adapter: {e}")
            return False
    
    async def stop(self) -> None:
        """停止适配器"""
        self.is_running = False
        logger.info("Polymarket adapter stopped")
    
    async def fetch_markets(self) -> List[MarketData]:
        """
        获取市场数据
        
        Returns:
            市场数据列表
        """
        if not self.rust_engine:
            logger.error("Rust engine not available")
            return []
        
        try:
            markets = self.rust_engine.fetch_markets()
            logger.info(f"Fetched {len(markets)} markets from Rust engine")
            return markets
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []
    
    async def get_order_book(self, asset_id: str) -> Optional[OrderBook]:
        """
        获取订单簿
        
        Args:
            asset_id: 资产 ID
            
        Returns:
            订单簿数据
        """
        if not self.rust_engine:
            logger.error("Rust engine not available")
            return None
        
        try:
            order_book = self.rust_engine.get_order_book(asset_id)
            if order_book:
                logger.debug(f"Got order book for {asset_id}: {len(order_book.bids)} bids, {len(order_book.asks)} asks")
            return order_book
        except Exception as e:
            logger.error(f"Failed to get order book for {asset_id}: {e}")
            return None
    
    async def subscribe_asset(self, asset_id: str) -> bool:
        """
        订阅资产更新
        
        Args:
            asset_id: 资产 ID
            
        Returns:
            订阅是否成功
        """
        if not self.rust_engine:
            logger.error("Rust engine not available")
            return False
        
        try:
            self.rust_engine.subscribe_asset(asset_id)
            self.subscribed_assets.add(asset_id)
            logger.info(f"Subscribed to asset: {asset_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to asset {asset_id}: {e}")
            return False
    
    async def get_subscribed_markets(self) -> List[str]:
        """
        获取已订阅的市场列表
        
        Returns:
            已订阅的市场 ID 列表
        """
        return list(self.subscribed_assets)
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取适配器状态
        
        Returns:
            状态字典
        """
        return {
            "is_running": self.is_running,
            "rust_available": RUST_AVAILABLE,
            "subscribed_assets": list(self.subscribed_assets),
            "config": self.config,
        }


# 全局适配器实例
_polymarket_adapter: Optional[PolymarketRustAdapter] = None


def get_polymarket_adapter(config: Optional[Dict[str, Any]] = None) -> PolymarketRustAdapter:
    """
    获取全局 Polymarket 适配器实例
    
    Args:
        config: 配置字典
        
    Returns:
        适配器实例
    """
    global _polymarket_adapter
    
    if _polymarket_adapter is None:
        _polymarket_adapter = PolymarketRustAdapter(config)
    
    return _polymarket_adapter


async def initialize_polymarket(config: Optional[Dict[str, Any]] = None) -> bool:
    """
    初始化 Polymarket 适配器
    
    Args:
        config: 配置字典
        
    Returns:
        初始化是否成功
    """
    adapter = get_polymarket_adapter(config)
    return await adapter.start()


# 测试函数
async def test_polymarket_adapter():
    """测试 Polymarket 适配器"""
    logger.info("Testing Polymarket adapter...")
    
    adapter = get_polymarket_adapter()
    
    # 测试获取市场数据
    markets = await adapter.fetch_markets()
    logger.info(f"Test: fetched {len(markets)} markets")
    
    # 测试获取订单簿
    if markets:
        first_market = markets[0]
        if first_market.asset_ids:
            order_book = await adapter.get_order_book(first_market.asset_ids[0])
            if order_book:
                logger.info(f"Test: got order book with {len(order_book.bids)} bids")
    
    logger.info("Polymarket adapter test completed")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_polymarket_adapter())
