#!/usr/bin/env python3
"""
API Gateway 测试 - 不依赖适配器
"""

import requests
import time
import json

def test_api_gateway():
    """测试 API Gateway 端点"""
    print("🌐 测试 API Gateway 端点...")
    
    api_base = "http://localhost:8080/api/v1/polymarket"
    
    endpoints = [
        ("/markets", "所有市场"),
        ("/markets/btc", "BTC 市场"),
        ("/strategy/btc5m", "BTC 策略"),
        ("/strategy/stats", "策略统计"),
        ("/stats", "系统统计")
    ]
    
    results = {}
    
    for endpoint, description in endpoints:
        try:
            url = f"{api_base}{endpoint}"
            start_time = time.time()
            
            response = requests.get(url, timeout=5)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                results[endpoint] = {
                    "success": True,
                    "status_code": response.status_code,
                    "response_time_ms": round(response_time * 1000, 2),
                    "data_keys": list(data.keys()) if isinstance(data, dict) else "array",
                    "data_size": len(str(data))
                }
                print(f"✅ {description} ({endpoint}): {response.status_code}, {response_time:.3f}s")
                
                # 显示一些关键数据
                if endpoint == "/markets":
                    markets = data.get('markets', [])
                    print(f"   📊 市场数量: {len(markets)}")
                    if markets:
                        print(f"   📝 示例市场: {markets[0].get('question', 'N/A')[:50]}...")
                
                elif endpoint == "/markets/btc":
                    btc_markets = data.get('markets', [])
                    print(f"   🔍 BTC 市场: {len(btc_markets)}")
                    if btc_markets:
                        print(f"   📝 BTC 示例: {btc_markets[0].get('question', 'N/A')[:50]}...")
                
                elif endpoint == "/strategy/btc5m":
                    if data.get('success'):
                        strategy_data = data.get('data', {})
                        print(f"   🎯 策略信号: {strategy_data.get('signal', 'N/A')}")
                        print(f"   📈 期望值: {strategy_data.get('expected_value', 'N/A')}")
                        print(f"   🔒 置信度: {strategy_data.get('confidence', 'N/A')}")
                
                elif endpoint == "/strategy/stats":
                    if data.get('success'):
                        stats = data.get('data', {})
                        performance = stats.get('performance', {})
                        print(f"   📊 日收益率: {performance.get('daily_return', 'N/A')}")
                        print(f"   📈 夏普比率: {performance.get('sharpe_ratio', 'N/A')}")
                
            else:
                results[endpoint] = {
                    "success": False,
                    "status_code": response.status_code,
                    "response_time_ms": round(response_time * 1000, 2),
                    "error": response.text[:100]
                }
                print(f"❌ {description} ({endpoint}): {response.status_code}")
                print(f"   📝 错误: {response.text[:100]}")
                
        except requests.exceptions.ConnectionError:
            results[endpoint] = {
                "success": False,
                "error": "连接失败 - API Gateway 可能未启动"
            }
            print(f"❌ {description} ({endpoint}): 连接失败")
            print(f"   💡 请确保 API Gateway 正在运行: cd api-gateway && go run src/main.go")
        except Exception as e:
            results[endpoint] = {
                "success": False,
                "error": str(e)
            }
            print(f"❌ {description} ({endpoint}): {e}")
    
    return results

def generate_summary(results):
    """生成测试总结"""
    print("\n" + "=" * 60)
    print("📊 API Gateway 测试总结")
    print("=" * 60)
    
    successful_endpoints = sum(1 for ep, result in results.items() if result.get("success"))
    total_endpoints = len(results)
    
    print(f"✅ 通过端点: {successful_endpoints}/{total_endpoints}")
    
    if successful_endpoints == total_endpoints:
        print("🎉 所有端点正常工作！")
        print("🚀 API Gateway 已准备就绪")
    elif successful_endpoints >= total_endpoints * 0.8:
        print("👍 大部分端点正常工作")
        print("⚠️  需要检查失败的端点")
    else:
        print("❌ 多个端点失败")
        print("🔧 需要修复 API Gateway")
    
    print("\n📋 详细结果:")
    for endpoint, result in results.items():
        status = "✅" if result.get("success") else "❌"
        time_ms = result.get("response_time_ms", 0)
        print(f"   {status} {endpoint}: {time_ms}ms")
    
    print("\n💡 下一步:")
    if successful_endpoints == total_endpoints:
        print("  🎨 开始前端集成测试")
        print("  📊 验证数据流完整性")
    else:
        print("  🔧 修复失败的 API 端点")
        print("  🔄 重新运行测试")

def main():
    """主函数"""
    print("🎯 API Gateway 集成测试")
    print("=" * 60)
    
    # 运行测试
    results = test_api_gateway()
    
    # 生成总结
    generate_summary(results)
    
    # 保存结果
    with open("api_gateway_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n📝 测试结果已保存到: api_gateway_test_results.json")

if __name__ == "__main__":
    main()
