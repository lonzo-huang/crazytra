"""
Polymarket Data Adapter
获取 Polymarket 预测市场数据并推送到 Redis
"""

import asyncio
import aiohttp
import redis.asyncio as redis
import json
from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PolymarketAdapter:
    """Polymarket 数据适配器"""
    
    BASE_URL = "https://clob.polymarket.com"
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
    
    async def connect(self):
        """建立连接"""
        logger.info("Connecting to Polymarket and Redis...")
        
        # 连接 Redis
        self.redis_client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        
        # 创建 HTTP session
        self.session = aiohttp.ClientSession()
        
        logger.info("✅ Connected successfully")
    
    async def disconnect(self):
        """断开连接"""
        logger.info("Disconnecting...")
        
        self.running = False
        
        if self.session:
            await self.session.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("✅ Disconnected")
    
    async def get_markets(self, limit: int = 20, active: bool = True) -> List[Dict]:
        """获取市场列表"""
        url = f"{self.BASE_URL}/markets"
        params = {
            "limit": str(limit),
            "active": "true" if active else "false",
            "closed": "false"
        }
        
        try:
            async with self.session.get(url, params=params, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                
                # 处理不同的数据格式
                if isinstance(data, dict) and 'data' in data:
                    return data['data']
                elif isinstance(data, list):
                    return data
                else:
                    return [data] if isinstance(data, dict) else []
                    
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []
    
    async def get_market_orderbook(self, token_id: str) -> Optional[Dict]:
        """获取订单簿"""
        url = f"{self.BASE_URL}/book"
        params = {"token_id": token_id}
        
        try:
            async with self.session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Failed to fetch orderbook for {token_id}: {e}")
            return None
    
    async def publish_market_data(self, market: Dict):
        """发布市场数据到 Redis"""
        try:
            # 存储到 Redis Hash
            market_id = market.get('condition_id', 'unknown')
            key = f"polymarket:market:{market_id}"
            
            # 转换为 JSON 字符串
            market_json = json.dumps(market, default=str)
            
            # 存储市场数据
            await self.redis_client.set(key, market_json, ex=300)  # 5分钟过期
            
            # 发布到 Redis Pub/Sub
            channel = f"market.polymarket.{market_id}"
            await self.redis_client.publish(channel, market_json)
            
            # 添加到市场列表
            await self.redis_client.zadd(
                "polymarket:markets:active",
                {market_id: datetime.utcnow().timestamp()}
            )
            
            logger.debug(f"Published market: {market.get('question', 'N/A')[:50]}")
            
        except Exception as e:
            logger.error(f"Failed to publish market data: {e}")
    
    async def fetch_and_publish_markets(self):
        """获取并发布市场数据"""
        markets = await self.get_markets(limit=20)
        
        if not markets:
            logger.warning("No markets fetched")
            return
        
        logger.info(f"Fetched {len(markets)} markets")
        
        for market in markets:
            await self.publish_market_data(market)
        
        # 存储市场总数
        await self.redis_client.set(
            "polymarket:markets:count",
            len(markets),
            ex=300
        )
    
    async def run(self, interval: int = 30):
        """
        运行适配器，定期获取数据
        
        Args:
            interval: 更新间隔（秒），默认 30 秒
        """
        await self.connect()
        
        self.running = True
        logger.info(f"🚀 Polymarket adapter started (update interval: {interval}s)")
        
        try:
            while self.running:
                try:
                    await self.fetch_and_publish_markets()
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    await asyncio.sleep(5)  # 错误后等待 5 秒
                    
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.disconnect()


async def main():
    """主函数"""
    import os
    
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    update_interval = int(os.getenv("POLYMARKET_UPDATE_INTERVAL", "30"))
    
    adapter = PolymarketAdapter(redis_url=redis_url)
    await adapter.run(interval=update_interval)


if __name__ == "__main__":
    asyncio.run(main())
