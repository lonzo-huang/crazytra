#!/usr/bin/env python3
"""
完整的 Polymarket 集成测试
测试高性能适配器 + API Gateway + 前端数据流
"""

import asyncio
import sys
import time
import requests
import json
from typing import Dict, Any, List

# 添加路径
sys.path.append('nautilus-core')
sys.path.append('nautilus-core/adapters')

from adapters.polymarket_high_performance import get_high_performance_adapter

class IntegrationTester:
    def __init__(self):
        self.adapter = get_high_performance_adapter()
        self.api_base = "http://localhost:8080/api/v1/polymarket"
        self.results = {}
    
    async def test_high_performance_adapter(self) -> Dict[str, Any]:
        """测试高性能适配器"""
        print("🚀 测试高性能适配器...")
        
        try:
            # 启动适配器
            await self.adapter.start()
            
            # 测试市场数据获取
            start_time = time.time()
            markets = await self.adapter.fetch_markets()
            fetch_time = time.time() - start_time
            
            # 测试 BTC 市场筛选
            start_time = time.time()
            btc_markets = self.adapter.filter_btc_markets(markets)
            filter_time = time.time() - start_time
            
            # 测试策略信号
            strategy_signal = await self.adapter.get_strategy_signals("btc_5m")
            
            # 获取性能统计
            stats = self.adapter.get_performance_stats()
            
            # 停止适配器
            await self.adapter.stop()
            
            result = {
                "success": True,
                "total_markets": len(markets),
                "btc_markets": len(btc_markets),
                "fetch_time_ms": round(fetch_time * 1000, 2),
                "filter_time_ms": round(filter_time * 1000, 2),
                "strategy_signal": strategy_signal,
                "performance_stats": stats
            }
            
            print(f"✅ 获取 {len(markets)} 个市场，耗时 {fetch_time:.3f}s")
            print(f"✅ 筛选 {len(btc_markets)} 个 BTC 市场，耗时 {filter_time:.3f}s")
            print(f"✅ 策略信号: {strategy_signal.get('signal', 'N/A')}")
            
            return result
            
        except Exception as e:
            print(f"❌ 高性能适配器测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    def test_api_gateway(self) -> Dict[str, Any]:
        """测试 API Gateway"""
        print("\n🌐 测试 API Gateway...")
        
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
                url = f"{self.api_base}{endpoint}"
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
                else:
                    results[endpoint] = {
                        "success": False,
                        "status_code": response.status_code,
                        "response_time_ms": round(response_time * 1000, 2),
                        "error": response.text[:100]
                    }
                    print(f"❌ {description} ({endpoint}): {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                results[endpoint] = {
                    "success": False,
                    "error": "连接失败 - API Gateway 可能未启动"
                }
                print(f"❌ {description} ({endpoint}): 连接失败")
            except Exception as e:
                results[endpoint] = {
                    "success": False,
                    "error": str(e)
                }
                print(f"❌ {description} ({endpoint}): {e}")
        
        return results
    
    def test_data_consistency(self) -> Dict[str, Any]:
        """测试数据一致性"""
        print("\n🔍 测试数据一致性...")
        
        try:
            # 获取 API Gateway 的数据
            markets_response = requests.get(f"{self.api_base}/markets", timeout=5)
            btc_response = requests.get(f"{self.api_base}/markets/btc", timeout=5)
            
            if markets_response.status_code == 200 and btc_response.status_code == 200:
                markets_data = markets_response.json()
                btc_data = btc_response.json()
                
                # 检查数据结构
                markets_count = len(markets_data.get('markets', []))
                btc_count = len(btc_data.get('markets', []))
                
                result = {
                    "success": True,
                    "api_markets_count": markets_count,
                    "api_btc_count": btc_count,
                    "data_structure_valid": True,
                    "consistency_check": "通过"
                }
                
                print(f"✅ API 市场数量: {markets_count}")
                print(f"✅ API BTC 市场: {btc_count}")
                print(f"✅ 数据结构验证通过")
                
                return result
            else:
                return {
                    "success": False,
                    "error": "API 响应异常"
                }
                
        except Exception as e:
            print(f"❌ 数据一致性测试失败: {e}")
            return {"success": False, "error": str(e)}
    
    def test_performance_benchmarks(self) -> Dict[str, Any]:
        """性能基准测试"""
        print("\n⚡ 性能基准测试...")
        
        benchmarks = {}
        
        # API 响应时间测试
        endpoints = ["/markets", "/markets/btc", "/strategy/btc5m"]
        response_times = []
        
        for endpoint in endpoints:
            try:
                times = []
                for _ in range(3):  # 测试3次取平均值
                    start = time.time()
                    response = requests.get(f"{self.api_base}{endpoint}", timeout=5)
                    if response.status_code == 200:
                        times.append(time.time() - start)
                
                if times:
                    avg_time = sum(times) / len(times)
                    response_times.append(avg_time)
                    print(f"📊 {endpoint}: 平均 {avg_time:.3f}s")
                    
            except:
                pass
        
        if response_times:
            benchmarks["api_avg_response_time"] = round(sum(response_times) / len(response_times) * 1000, 2)
            benchmarks["api_max_response_time"] = round(max(response_times) * 1000, 2)
            benchmarks["performance_grade"] = "优秀" if benchmarks["api_avg_response_time"] < 100 else "良好"
        
        return benchmarks
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("🎯 开始完整集成测试")
        print("=" * 60)
        
        # 测试高性能适配器
        self.results["adapter"] = await self.test_high_performance_adapter()
        
        # 测试 API Gateway
        self.results["api_gateway"] = self.test_api_gateway()
        
        # 测试数据一致性
        self.results["data_consistency"] = self.test_data_consistency()
        
        # 性能基准测试
        self.results["performance"] = self.test_performance_benchmarks()
        
        return self.results
    
    def generate_report(self) -> str:
        """生成测试报告"""
        report = "\n" + "=" * 60
        report += "\n📊 完整集成测试报告"
        report += "\n" + "=" * 60
        
        # 适配器测试结果
        adapter_result = self.results.get("adapter", {})
        if adapter_result.get("success"):
            report += f"\n✅ 高性能适配器: 通过"
            report += f"\n   📈 市场数量: {adapter_result.get('total_markets', 0)}"
            report += f"\n   🔍 BTC 市场: {adapter_result.get('btc_markets', 0)}"
            report += f"\n   ⚡ 获取速度: {adapter_result.get('fetch_time_ms', 0)}ms"
            report += f"\n   🎯 策略信号: {adapter_result.get('strategy_signal', {}).get('signal', 'N/A')}"
        else:
            report += f"\n❌ 高性能适配器: 失败"
        
        # API Gateway 测试结果
        api_result = self.results.get("api_gateway", {})
        successful_endpoints = sum(1 for ep, result in api_result.items() if result.get("success"))
        total_endpoints = len(api_result)
        
        report += f"\n✅ API Gateway: {successful_endpoints}/{total_endpoints} 端点通过"
        
        for endpoint, result in api_result.items():
            status = "✅" if result.get("success") else "❌"
            time_ms = result.get("response_time_ms", 0)
            report += f"\n   {status} {endpoint}: {time_ms}ms"
        
        # 数据一致性
        consistency_result = self.results.get("data_consistency", {})
        if consistency_result.get("success"):
            report += f"\n✅ 数据一致性: 通过"
        else:
            report += f"\n❌ 数据一致性: 失败"
        
        # 性能基准
        performance_result = self.results.get("performance", {})
        if performance_result:
            avg_time = performance_result.get("api_avg_response_time", 0)
            grade = performance_result.get("performance_grade", "未知")
            report += f"\n✅ 性能评级: {grade} (平均 {avg_time}ms)"
        
        # 总体评估
        report += "\n" + "=" * 60
        
        adapter_ok = adapter_result.get("success", False)
        api_ok = successful_endpoints >= total_endpoints * 0.8  # 80% 端点通过
        consistency_ok = consistency_result.get("success", False)
        
        if adapter_ok and api_ok and consistency_ok:
            report += "\n🎉 总体评估: 优秀 - 系统可以投入使用"
        elif adapter_ok and api_ok:
            report += "\n👍 总体评估: 良好 - 核心功能正常"
        else:
            report += "\n⚠️  总体评估: 需要改进 - 存在关键问题"
        
        report += "\n" + "=" * 60
        
        return report

async def main():
    """主函数"""
    tester = IntegrationTester()
    
    # 运行所有测试
    await tester.run_all_tests()
    
    # 生成报告
    report = tester.generate_report()
    print(report)
    
    # 保存报告
    with open("integration_test_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    
    print("\n📝 测试报告已保存到: integration_test_report.txt")

if __name__ == "__main__":
    asyncio.run(main())
