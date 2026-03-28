#!/usr/bin/env python3
"""
Polymarket 数据服务
为 API Gateway 提供 Redis 数据填充
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
import redis.asyncio as redis

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入适配器
from adapters.polymarket_python_fallback import get_polymarket_adapter

class PolymarketDataService:
    """Polymarket 数据服务"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.adapter = get_polymarket_adapter()
        
    async def start(self):
        """启动服务"""
        try:
            # 连接 Redis
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("Redis 连接成功")
            
            # 启动适配器
            await self.adapter.start()
            logger.info("Polymarket 适配器启动成功")
            
            return True
        except Exception as e:
            logger.error(f"启动服务失败: {e}")
            return False
    
    async def stop(self):
        """停止服务"""
        if self.adapter:
            await self.adapter.stop()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("服务已停止")
    
    async def fetch_and_cache_markets(self):
        """获取并缓存市场数据"""
        try:
            # 获取市场数据
            markets = await self.adapter.fetch_markets()
            logger.info(f"获取到 {len(markets)} 个市场")
            
            if not markets:
                logger.warning("没有获取到市场数据")
                return
            
            # 清理旧数据
            await self.redis_client.delete("polymarket:markets:active")
            
            # 缓存市场数据
            pipe = self.redis_client.pipeline()
            active_markets = []
            
            for market in markets:
                # 市场数据
                market_key = f"polymarket:market:{market.id}"
                market_data = {
                    "condition_id": market.condition_id,
                    "question": market.question,
                    "description": "",
                    "volume": market.volume,
                    "liquidity": market.liquidity,
                    "end_date_iso": market.end_date,
                    "tokens": [
                        {"token_id": token_id, "outcome": "yes"}
                        for token_id in market.asset_ids[:2]
                    ],
                    "active": market.active
                }
                
                pipe.set(market_key, json.dumps(market_data))
                
                # 活跃市场列表（按流动性排序）
                if market.active and market.liquidity > 0:
                    pipe.zadd("polymarket:markets:active", {market.id: market.liquidity})
                    active_markets.append(market.id)
            
            # 设置市场总数
            pipe.set("polymarket:markets:count", str(len(markets)))
            
            # 执行批量操作
            await pipe.execute()
            
            logger.info(f"成功缓存 {len(markets)} 个市场，其中 {len(active_markets)} 个活跃")
            
        except Exception as e:
            logger.error(f"缓存市场数据失败: {e}")
    
    async def fetch_and_cache_order_books(self):
        """获取并缓存订单簿数据"""
        try:
            # 获取市场数据
            markets = await self.adapter.fetch_markets()
            
            cached_count = 0
            for market in markets:
                if not market.asset_ids:
                    continue
                
                # 获取第一个资产的订单簿
                order_book = await self.adapter.get_order_book(market.asset_ids[0])
                if order_book:
                    # 转换格式
                    book_data = {
                        "instrument_id": order_book.instrument_id,
                        "bids": [[price, size] for price, size in order_book.bids],
                        "asks": [[price, size] for price, size in order_book.asks],
                        "last_update": order_book.last_update.isoformat()
                    }
                    
                    # 缓存订单簿（5分钟过期）
                    key = f"polymarket:orderbook:{order_book.instrument_id}"
                    await self.redis_client.setex(key, 300, json.dumps(book_data))
                    cached_count += 1
            
            logger.info(f"成功缓存 {cached_count} 个订单簿")
            
        except Exception as e:
            logger.error(f"缓存订单簿失败: {e}")
    
    async def generate_strategy_signals(self):
        """生成策略信号（模拟）"""
        try:
            # 获取 BTC 市场
            markets = await self.adapter.fetch_markets()
            btc_markets = [m for m in markets if 'btc' in m.question.lower()]
            
            signals = []
            for market in btc_markets[:3]:  # 只为前3个市场生成信号
                if market.asset_ids:
                    signal = {
                        "strategy": "Btc5mBinaryEV",
                        "asset_id": market.asset_ids[0],
                        "action": "buy",
                        "side": "yes" if hash(market.id) % 2 == 0 else "no",
                        "price": 0.5 + (hash(market.id) % 100) / 1000.0,
                        "size": 100.0,
                        "confidence": 0.6 + (hash(market.id) % 40) / 100.0,
                        "reason": f"t={120}s,P_yes={50 + hash(market.id) % 20}%,edge={5 + hash(market.id) % 10}%",
                        "timestamp": datetime.now().isoformat()
                    }
                    signals.append(signal)
            
            if signals:
                # 缓存策略信号（列表格式）
                signals_key = "polymarket:strategy:btc5m:signals"
                
                # 清理旧信号
                await self.redis_client.delete(signals_key)
                
                # 添加新信号
                pipe = self.redis_client.pipeline()
                for signal in signals:
                    pipe.lpush(signals_key, json.dumps(signal))
                
                # 设置过期时间（1分钟）
                pipe.expire(signals_key, 60)
                
                await pipe.execute()
                logger.info(f"生成 {len(signals)} 个策略信号")
            
        except Exception as e:
            logger.error(f"生成策略信号失败: {e}")
    
    async def run_continuous(self):
        """持续运行服务"""
        logger.info("开始持续运行数据服务...")
        
        while True:
            try:
                # 获取并缓存数据
                await self.fetch_and_cache_markets()
                await self.fetch_and_cache_order_books()
                await self.generate_strategy_signals()
                
                # 等待30秒
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"运行时错误: {e}")
                await asyncio.sleep(10)  # 错误时等待10秒

async def main():
    """主函数"""
    print("🚀 MirrorQuant Polymarket 数据服务")
    print("=" * 50)
    
    service = PolymarketDataService()
    
    if await service.start():
        print("✅ 服务启动成功")
        
        try:
            # 先运行一次数据获取
            await service.fetch_and_cache_markets()
            await service.fetch_and_cache_order_books()
            await service.generate_strategy_signals()
            
            print("✅ 初始数据缓存完成")
            print("🔄 开始持续运行...")
            
            # 持续运行
            await service.run_continuous()
            
        except KeyboardInterrupt:
            print("\n⏹️  收到停止信号")
        finally:
            await service.stop()
    else:
        print("❌ 服务启动失败")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
