#!/usr/bin/env python3
"""
简化的 Polymarket 数据获取器
基于官方文档，使用 requests 库
"""

import requests
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

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

class PolymarketSimpleDataLoader:
    """简化的 Polymarket 数据加载器"""
    
    def __init__(self):
        self.gamma_api_url = "https://gamma-api.polymarket.com"
        self.clob_api_url = "https://clob.polymarket.com"
    
    def fetch_markets(self, active: bool = True, limit: int = 100) -> List[PolymarketMarket]:
        """获取市场数据"""
        try:
            params = {"limit": limit}
            if active:
                params["active"] = "true"
            
            response = requests.get(f"{self.gamma_api_url}/markets", params=params)
            response.raise_for_status()
            data = response.json()
            
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
    
    def fetch_events(self, active: bool = True) -> List[Dict[str, Any]]:
        """获取事件数据"""
        try:
            params = {}
            if active:
                params["active"] = "true"
            
            response = requests.get(f"{self.gamma_api_url}/events", params=params)
            response.raise_for_status()
            data = response.json()
            return data
            
        except Exception as e:
            print(f"❌ 获取事件数据失败: {e}")
            return []
    
    def query_market_by_slug(self, slug: str) -> Optional[PolymarketMarket]:
        """根据 slug 查询市场"""
        markets = self.fetch_markets(active=True, limit=1000)
        for market in markets:
            if slug.lower() in market.question.lower() or slug.lower() in market.id.lower():
                return market
        return None
    
    def query_event_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """根据 slug 查询事件"""
        events = self.fetch_events(active=True)
        for event in events:
            if slug.lower() in event.get("question", "").lower() or slug.lower() in event.get("id", "").lower():
                return event
        return None

def test_polymarket_data():
    """测试 Polymarket 数据获取"""
    print("🎯 测试简化的 Polymarket 数据获取器")
    print("=" * 50)
    
    loader = PolymarketSimpleDataLoader()
    
    # 1. 获取市场数据
    print("📊 获取市场数据...")
    markets = loader.fetch_markets(active=True, limit=5)
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
    events = loader.fetch_events(active=True)
    print(f"✅ 获取到 {len(events)} 个活跃事件")
    
    # 3. 查询特定市场
    print("\n🔍 查询特定市场...")
    market = loader.query_market_by_slug("gta")
    if market:
        print(f"✅ 找到市场: {market.question}")
    else:
        print("❌ 未找到相关市场")
    
    # 4. 查询特定事件
    print("\n🔍 查询特定事件...")
    event = loader.query_event_by_slug("gta")
    if event:
        print(f"✅ 找到事件: {event.get('question', 'N/A')}")
    else:
        print("❌ 未找到相关事件")
    
    # 5. 测试数据结构
    print("\n🧪 测试数据结构兼容性...")
    if markets:
        test_market = markets[0]
        print(f"✅ 数据结构测试通过:")
        print(f"   - ID: {test_market.id}")
        print(f"   - Condition ID: {test_market.condition_id}")
        print(f"   - Question: {test_market.question}")
        print(f"   - Volume: {test_market.volume}")
        print(f"   - Liquidity: {test_market.liquidity}")
        print(f"   - End Date: {test_market.end_date}")
        print(f"   - Active: {test_market.active}")
        print(f"   - Clob Tokens: {test_market.clob_token_ids}")
        print(f"   - Category: {test_market.category}")

if __name__ == "__main__":
    test_polymarket_data()
