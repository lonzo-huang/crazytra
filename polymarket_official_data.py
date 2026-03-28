#!/usr/bin/env python3
"""
基于 NautilusTrader 官方文档的 Polymarket 数据获取器
简化版本，不依赖复杂的 CLOB 客户端
"""

import asyncio
import aiohttp
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class PolymarketMarket:
    """Polymarket 市场数据结构"""
    id: str
    condition_id: str
    question: str
    description: Optional[str]
    volume: float
    liquidity: float
    end_date: str
    active: bool
    closed: bool
    resolved: bool
    clob_token_ids: List[str]
    category: Optional[str]
    start_date: Optional[str]

class PolymarketDataLoader:
    """简化的 Polymarket 数据加载器"""
    
    def __init__(self):
        self.gamma_api_url = "https://gamma-api.polymarket.com"
        self.clob_api_url = "https://clob.polymarket.com"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_markets(self, active: bool = True, limit: int = 100) -> List[PolymarketMarket]:
        """获取市场数据"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            params = {"limit": limit}
            if active:
                params["active"] = "true"
            
            async with self.session.get(f"{self.gamma_api_url}/markets", params=params) as response:
                response.raise_for_status()
                data = await response.json()
                
                markets = []
                for market_data in data:
                    # 解析 clobTokenIds (JSON 字符串)
                    clob_token_ids = []
                    if market_data.get("clobTokenIds"):
                        try:
                            clob_token_ids = json.loads(market_data["clobTokenIds"])
                        except (json.JSONDecodeError, TypeError):
                            clob_token_ids = []
                    
                    market = PolymarketMarket(
                        id=market_data.get("id", ""),
                        condition_id=market_data.get("conditionId", ""),
                        question=market_data.get("question", ""),
                        description=market_data.get("description"),
                        volume=float(market_data.get("volume", "0")),
                        liquidity=float(market_data.get("liquidity", "0")),
                        end_date=market_data.get("endDateIso", ""),
                        active=market_data.get("active", False),
                        closed=market_data.get("closed", False),
                        resolved=market_data.get("resolved", False),
                        clob_token_ids=clob_token_ids,
                        category=market_data.get("category"),
                        start_date=market_data.get("startDateIso")
                    )
                    markets.append(market)
                
                return markets
                
        except Exception as e:
            print(f"❌ 获取市场数据失败: {e}")
            return []
    
    async def fetch_events(self, active: bool = True) -> List[Dict[str, Any]]:
        """获取事件数据"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            params = {}
            if active:
                params["active"] = "true"
            
            async with self.session.get(f"{self.gamma_api_url}/events", params=params) as response:
                response.raise_for_status()
                data = await response.json()
                return data
                
        except Exception as e:
            print(f"❌ 获取事件数据失败: {e}")
            return []
    
    async def query_market_by_slug(self, slug: str) -> Optional[PolymarketMarket]:
        """根据 slug 查询市场"""
        markets = await self.fetch_markets(active=True, limit=1000)
        for market in markets:
            if slug in market.question.lower() or slug in market.id:
                return market
        return None
    
    async def query_event_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """根据 slug 查询事件"""
        events = await self.fetch_events(active=True)
        for event in events:
            if slug in event.get("question", "").lower() or slug in event.get("id", ""):
                return event
        return None

async def test_polymarket_data():
    """测试 Polymarket 数据获取"""
    print("🎯 测试简化的 Polymarket 数据获取器")
    print("=" * 50)
    
    async with PolymarketDataLoader() as loader:
        # 1. 获取市场数据
        print("📊 获取市场数据...")
        markets = await loader.fetch_markets(active=True, limit=5)
        print(f"✅ 获取到 {len(markets)} 个活跃市场")
        
        if markets:
            print("\n📋 市场示例:")
            for i, market in enumerate(markets[:3], 1):
                print(f"  {i}. {market.question}")
                print(f"     ID: {market.id}")
                print(f"     成交量: {market.volume}")
                print(f"     流动性: {market.liquidity}")
                print(f"     代币数量: {len(market.clob_token_ids)}")
                print()
        
        # 2. 获取事件数据
        print("📋 获取事件数据...")
        events = await loader.fetch_events(active=True)
        print(f"✅ 获取到 {len(events)} 个活跃事件")
        
        # 3. 查询特定市场
        print("\n🔍 查询特定市场...")
        market = await loader.query_market_by_slug("gta")
        if market:
            print(f"✅ 找到市场: {market.question}")
        else:
            print("❌ 未找到相关市场")
        
        # 4. 查询特定事件
        print("\n🔍 查询特定事件...")
        event = await loader.query_event_by_slug("gta")
        if event:
            print(f"✅ 找到事件: {event.get('question', 'N/A')}")
        else:
            print("❌ 未找到相关事件")

if __name__ == "__main__":
    asyncio.run(test_polymarket_data())
