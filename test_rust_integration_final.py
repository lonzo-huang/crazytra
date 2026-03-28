#!/usr/bin/env python3
"""
最终 Rust 集成测试
测试 Rust PolymarketDataEngine 的完整功能
"""

import sys
import os
import time
import asyncio
from pathlib import Path

# 添加 Rust 库路径
rust_lib_path = Path(__file__).parent / "nautilus-core" / "rust" / "target" / "release"
sys.path.insert(0, str(rust_lib_path))

def test_rust_module_import():
    """测试 Rust 模块导入"""
    print("🦀 测试 Rust 模块导入...")
    
    try:
        import nautilus_core
        print("✅ nautilus_core 模块导入成功")
        
        # 检查可用的类
        available_classes = [
            'PolymarketDataEngine',
            'MarketData', 
            'QuoteTick',
            'TradeTick',
            'OrderBook'
        ]
        
        for class_name in available_classes:
            if hasattr(nautilus_core, class_name):
                print(f"✅ {class_name}: 可用")
            else:
                print(f"❌ {class_name}: 不可用")
        
        return True, nautilus_core
        
    except ImportError as e:
        print(f"❌ Rust 模块导入失败: {e}")
        print("💡 可能的原因:")
        print("   1. Rust 库未正确构建")
        print("   2. Python 版本不兼容")
        print("   3. 库路径不正确")
        return False, None

def test_rust_data_engine(nautilus_core):
    """测试 Rust 数据引擎"""
    print("\n🚀 测试 Rust PolymarketDataEngine...")
    
    try:
        # 创建数据引擎实例
        engine = nautilus_core.PolymarketDataEngine()
        print("✅ PolymarketDataEngine 创建成功")
        
        # 测试获取市场数据
        print("📊 测试获取市场数据...")
        start_time = time.time()
        
        markets = engine.fetch_markets()
        end_time = time.time()
        
        print(f"✅ 获取到 {len(markets)} 个市场")
        print(f"⏱️  耗时: {end_time - start_time:.3f}s")
        
        # 显示一些示例市场
        if markets:
            print("📝 示例市场:")
            for i, market in enumerate(markets[:3]):
                print(f"   {i+1}. {market.question[:50]}...")
                print(f"      流动性: {market.liquidity:.2f}")
                print(f"      活跃: {market.active}")
        
        # 测试缓存功能
        print("\n💾 测试缓存功能...")
        cached_markets = engine.get_cached_markets()
        print(f"✅ 缓存市场数量: {len(cached_markets)}")
        
        # 测试资产订阅
        print("\n🔔 测试资产订阅...")
        if markets:
            first_market = markets[0]
            if first_market.asset_ids:
                asset_id = first_market.asset_ids[0]
                engine.subscribe_asset(asset_id)
                print(f"✅ 已订阅资产: {asset_id}")
        
        return True, engine
        
    except Exception as e:
        print(f"❌ Rust 数据引擎测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_performance_comparison():
    """性能对比测试"""
    print("\n⚡ 性能对比测试...")
    
    try:
        import nautilus_core
        
        # Rust 实现
        engine = nautilus_core.PolymarketDataEngine()
        
        rust_times = []
        for i in range(3):
            start_time = time.time()
            markets = engine.fetch_markets()
            end_time = time.time()
            rust_times.append(end_time - start_time)
            print(f"🦀 Rust 测试 {i+1}: {end_time - start_time:.3f}s, {len(markets)} 市场")
        
        rust_avg = sum(rust_times) / len(rust_times)
        
        # Python 实现对比
        python_times = []
        sys.path.append('nautilus-core')
        sys.path.append('nautilus-core/adapters')
        
        try:
            from adapters.polymarket_python_fallback import PolymarketPythonAdapter
            
            async def test_python():
                adapter = PolymarketPythonAdapter()
                await adapter.start()
                start_time = time.time()
                markets = await adapter.fetch_markets()
                end_time = time.time()
                await adapter.stop()
                return end_time - start_time, len(markets)
            
            for i in range(3):
                py_time, py_count = asyncio.run(test_python())
                python_times.append(py_time)
                print(f"🐍 Python 测试 {i+1}: {py_time:.3f}s, {py_count} 市场")
            
            python_avg = sum(python_times) / len(python_times)
            
            # 计算性能提升
            if python_avg > 0:
                speedup = python_avg / rust_avg
                print(f"\n📊 性能对比结果:")
                print(f"   🦀 Rust 平均: {rust_avg:.3f}s")
                print(f"   🐍 Python 平均: {python_avg:.3f}s")
                print(f"   🚀 性能提升: {speedup:.1f}x")
                
                if speedup > 10:
                    print("   🎉 显著性能提升！")
                elif speedup > 2:
                    print("   👍 良好性能提升")
                else:
                    print("   ⚠️  性能提升有限")
            
        except ImportError:
            print("⚠️  Python 适配器不可用，跳过对比测试")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        return False

def test_data_structures():
    """测试数据结构"""
    print("\n🏗️  测试数据结构...")
    
    try:
        import nautilus_core
        
        # 测试 MarketData
        print("📊 测试 MarketData...")
        market = nautilus_core.MarketData(
            id="test-123",
            condition_id="cond-456", 
            question="测试市场",
            volume=1000000.0,
            liquidity=50000.0,
            end_date="2024-12-31",
            active=True,
            category="crypto",
            asset_ids=["token1", "token2"]
        )
        print(f"✅ MarketData: {market.question}")
        
        # 测试 QuoteTick
        print("💹 测试 QuoteTick...")
        quote = nautilus_core.QuoteTick(
            instrument_id="BTC-USD",
            bid=45000.0,
            ask=45100.0,
            bid_size=1.5,
            ask_size=2.0,
            ts_event=int(time.time() * 1e9),
            ts_init=int(time.time() * 1e9)
        )
        print(f"✅ QuoteTick: 买价 {quote.bid}, 卖价 {quote.ask}")
        
        # 测试 TradeTick
        print("📈 测试 TradeTick...")
        trade = nautilus_core.TradeTick(
            instrument_id="BTC-USD",
            price=45050.0,
            size=1.0,
            side="buy",
            trade_id="trade-789",
            ts_event=int(time.time() * 1e9),
            ts_init=int(time.time() * 1e9)
        )
        print(f"✅ TradeTick: 价格 {trade.price}, 方向 {trade.side}")
        
        # 测试 OrderBook
        print("📚 测试 OrderBook...")
        orderbook = nautilus_core.OrderBook(
            instrument_id="BTC-USD",
            bids=[(44900.0, 1.0), (44800.0, 2.0)],
            asks=[(45100.0, 1.5), (45200.0, 1.0)],
            last_update=int(time.time() * 1e9)
        )
        print(f"✅ OrderBook: {len(orderbook.bids)} 买单, {len(orderbook.asks)} 卖单")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据结构测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("🎯 Rust PolymarketDataEngine 最终集成测试")
    print("=" * 60)
    
    # 测试模块导入
    import_success, nautilus_core = test_rust_module_import()
    if not import_success:
        print("\n❌ 模块导入失败，无法继续测试")
        return False
    
    # 测试数据引擎
    engine_success, engine = test_rust_data_engine(nautilus_core)
    if not engine_success:
        print("\n❌ 数据引擎测试失败")
        return False
    
    # 测试数据结构
    struct_success = test_data_structures()
    
    # 性能测试
    perf_success = test_performance_comparison()
    
    # 生成测试报告
    print("\n" + "=" * 60)
    print("📊 最终测试报告")
    print("=" * 60)
    
    results = {
        "模块导入": import_success,
        "数据引擎": engine_success,
        "数据结构": struct_success,
        "性能测试": perf_success
    }
    
    passed_tests = sum(results.values())
    total_tests = len(results)
    
    for test_name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n🎯 总体结果: {passed_tests}/{total_tests} 测试通过")
    
    if passed_tests == total_tests:
        print("🎉 所有测试通过！Rust 集成成功！")
        print("🚀 系统已准备好进行高性能 Polymarket 交易")
    elif passed_tests >= total_tests * 0.8:
        print("👍 大部分测试通过，系统基本可用")
    else:
        print("⚠️  多个测试失败，需要进一步调试")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
