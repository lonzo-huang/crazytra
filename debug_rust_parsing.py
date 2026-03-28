#!/usr/bin/env python3
"""
调试 Rust JSON 解析问题
"""

import sys
import requests
import json
from pathlib import Path

# 添加 Rust 库路径
rust_lib_path = Path(__file__).parent / "nautilus-core" / "rust" / "target" / "release"
sys.path.insert(0, str(rust_lib_path))

def debug_api_response():
    """调试 API 响应格式"""
    print("🔍 调试 Polymarket API 响应...")
    
    response = requests.get('https://gamma-api.polymarket.com/markets?active=true&limit=1')
    data = response.json()
    
    if not data:
        print("❌ 没有数据")
        return
    
    market = data[0]
    print("✅ 获取到市场数据")
    
    # 检查每个字段的类型和值
    field_mappings = {
        'id': 'id',
        'conditionId': 'condition_id', 
        'question': 'question',
        'description': 'description',
        'volume': 'volume',
        'liquidity': 'liquidity',
        'endDateIso': 'end_date_iso',
        'active': 'active',
        'closed': 'closed',
        'resolved': 'resolved',
        'clobTokenIds': 'clob_token_ids',
        'category': 'category',
        'startDateIso': 'start_date_iso'
    }
    
    print("\n📊 字段分析:")
    for api_field, rust_field in field_mappings.items():
        value = market.get(api_field)
        value_type = type(value).__name__
        
        print(f"  {api_field} -> {rust_field}")
        print(f"    值: {repr(value)}")
        print(f"    类型: {value_type}")
        
        # 特殊处理
        if api_field in ['volume', 'liquidity']:
            try:
                parsed = float(value)
                print(f"    解析为 f64: {parsed}")
            except:
                print(f"    ❌ 无法解析为 f64")
        elif api_field == 'clobTokenIds':
            try:
                parsed = json.loads(value)
                print(f"    JSON 解析: {parsed}")
                print(f"    解析类型: {type(parsed)}")
            except:
                print(f"    ❌ 无法解析为 JSON")
        print()

def test_rust_directly():
    """直接测试 Rust 模块"""
    print("🦀 直接测试 Rust 模块...")
    
    try:
        import nautilus_core
        engine = nautilus_core.PolymarketDataEngine()
        
        # 手动调用内部方法来调试
        print("✅ Rust 模块导入成功")
        
        # 尝试获取原始数据
        import requests
        response = requests.get('https://gamma-api.polymarket.com/markets?active=true&limit=1')
        raw_data = response.json()
        
        print(f"📊 原始数据类型: {type(raw_data)}")
        print(f"📊 数据长度: {len(raw_data)}")
        
        if raw_data:
            print("📝 第一个市场的字段:")
            for key, value in raw_data[0].items():
                print(f"  {key}: {type(value).__name__} = {repr(value)[:100]}")
        
        # 尝试调用 Rust 方法
        print("\n🚀 调用 Rust fetch_markets()...")
        markets = engine.fetch_markets()
        print(f"✅ 成功获取 {len(markets)} 个市场")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🎯 Rust JSON 解析调试")
    print("=" * 50)
    
    # 1. 调试 API 响应
    debug_api_response()
    
    print("\n" + "=" * 50)
    
    # 2. 测试 Rust 模块
    success = test_rust_directly()
    
    if success:
        print("\n🎉 调试完成，Rust 模块工作正常！")
    else:
        print("\n❌ 调试发现问题，需要进一步修复")

if __name__ == "__main__":
    main()
