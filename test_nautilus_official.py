#!/usr/bin/env python3
"""
测试 NautilusTrader 官方 Polymarket 集成
"""

import asyncio
from nautilus_trader.adapters.polymarket import PolymarketDataLoader

async def test_official_integration():
    """测试官方集成"""
    print("🎯 测试 NautilusTrader 官方 Polymarket 集成")
    print("=" * 50)
    
    try:
        # 使用官方的 PolymarketDataLoader
        print("📊 创建 PolymarketDataLoader...")
        
        # 从市场 slug 创建加载器
        loader = await PolymarketDataLoader.from_market_slug("gta-vi-released-before-june-2026")
        
        print(f"✅ 加载器创建成功")
        print(f"   Instrument: {loader.instrument}")
        print(f"   Token ID: {loader.token_id}")
        
        # 获取市场数据
        print("\n📈 获取市场数据...")
        markets = await loader.fetch_markets(active=True, limit=5)
        print(f"✅ 获取到 {len(markets)} 个活跃市场")
        
        # 获取事件数据
        print("\n📋 获取事件数据...")
        events = await loader.fetch_events(active=True)
        print(f"✅ 获取到 {len(events)} 个活跃事件")
        
        # 获取交易历史
        print("\n💱 获取交易历史...")
        trades = await loader.load_trades()
        print(f"✅ 获取到 {len(trades)} 笔交易")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_query_methods():
    """测试查询方法"""
    print("\n🔍 测试查询方法")
    print("=" * 30)
    
    try:
        # 查询市场（不需要加载器）
        print("📊 查询市场...")
        market = await PolymarketDataLoader.query_market_by_slug("gta-vi-released-before-june-2026")
        print(f"✅ 市场查询成功: {market}")
        
        # 查询事件
        print("\n📋 查询事件...")
        event = await PolymarketDataLoader.query_event_by_slug("gta-vi-released-before-june-2026")
        print(f"✅ 事件查询成功: {event}")
        
        return True
        
    except Exception as e:
        print(f"❌ 查询错误: {e}")
        return False

async def main():
    """主函数"""
    print("🚀 NautilusTrader 官方 Polymarket 集成测试")
    print("=" * 60)
    
    # 1. 测试官方集成
    success1 = await test_official_integration()
    
    # 2. 测试查询方法
    success2 = await test_query_methods()
    
    if success1 and success2:
        print("\n🎉 所有测试通过！官方集成工作正常")
        print("\n💡 建议：使用官方集成替代我们的自定义 Rust 实现")
    else:
        print("\n❌ 部分测试失败")

if __name__ == "__main__":
    asyncio.run(main())
