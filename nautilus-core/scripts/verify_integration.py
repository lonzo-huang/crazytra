#!/usr/bin/env python3
"""
Nautilus 整合验证脚本

运行此脚本验证 Nautilus Trader 整合是否正确工作
"""
import asyncio
import json
import sys
import time
from decimal import Decimal
from typing import Any

import redis.asyncio as aioredis
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


class IntegrationVerifier:
    """整合验证器"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis: aioredis.Redis | None = None
        self.results: dict[str, bool] = {}
        
    async def connect_redis(self) -> bool:
        """连接 Redis"""
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.redis.ping()
            return True
        except Exception as e:
            console.print(f"[red]✗ Redis 连接失败: {e}[/red]")
            return False
    
    async def verify_redis_connection(self) -> bool:
        """验证 Redis 连接"""
        console.print("\n[bold cyan]1. 验证 Redis 连接[/bold cyan]")
        
        try:
            pong = await self.redis.ping()
            if pong:
                console.print("[green]✓ Redis 连接正常[/green]")
                
                # 获取 Redis 版本
                info = await self.redis.info("server")
                version = info.get("redis_version", "unknown")
                console.print(f"  版本: {version}")
                return True
        except Exception as e:
            console.print(f"[red]✗ Redis 连接失败: {e}[/red]")
            return False
    
    async def verify_redis_streams(self) -> bool:
        """验证 Redis Streams 配置"""
        console.print("\n[bold cyan]2. 验证 Redis Streams[/bold cyan]")
        
        required_streams = [
            "market.tick.binance.btcusdt",
            "llm.weight",
            "order.event",
        ]
        
        all_ok = True
        for stream in required_streams:
            try:
                # 检查 stream 是否存在
                exists = await self.redis.exists(stream)
                if exists:
                    # 获取最新消息
                    entries = await self.redis.xread(
                        streams={stream: "0"},
                        count=1,
                    )
                    if entries:
                        console.print(f"[green]✓ {stream} - 有数据[/green]")
                    else:
                        console.print(f"[yellow]⚠ {stream} - 存在但无数据[/yellow]")
                else:
                    console.print(f"[yellow]⚠ {stream} - 不存在（可能还未启动）[/yellow]")
                    all_ok = False
            except Exception as e:
                console.print(f"[red]✗ {stream} - 错误: {e}[/red]")
                all_ok = False
        
        return all_ok
    
    async def verify_tick_format(self) -> bool:
        """验证 tick 数据格式"""
        console.print("\n[bold cyan]3. 验证 Tick 数据格式[/bold cyan]")
        
        try:
            # 读取最新的 tick
            entries = await self.redis.xread(
                streams={"market.tick.binance.btcusdt": "0"},
                count=1,
            )
            
            if not entries:
                console.print("[yellow]⚠ 没有 tick 数据（RedisBridgeActor 可能未运行）[/yellow]")
                return False
            
            stream_name, messages = entries[0]
            message_id, fields = messages[0]
            
            # 解析 JSON
            data = json.loads(fields["data"])
            
            # 验证必需字段
            required_fields = [
                "symbol", "exchange", "timestamp_ns", "received_ns",
                "bid", "ask", "last", "latency_us"
            ]
            
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                console.print(f"[red]✗ 缺少字段: {missing_fields}[/red]")
                return False
            
            # 验证价格字段为字符串（关键！）
            price_fields = ["bid", "ask", "last"]
            for field in price_fields:
                if not isinstance(data[field], str):
                    console.print(f"[red]✗ {field} 不是字符串类型（应为字符串）[/red]")
                    return False
            
            # 验证可以转换为 Decimal
            try:
                bid = Decimal(data["bid"])
                ask = Decimal(data["ask"])
                last = Decimal(data["last"])
            except Exception as e:
                console.print(f"[red]✗ 价格无法转换为 Decimal: {e}[/red]")
                return False
            
            # 显示示例数据
            console.print("[green]✓ Tick 格式正确[/green]")
            console.print(f"  Symbol: {data['symbol']}")
            console.print(f"  Bid: {data['bid']}")
            console.print(f"  Ask: {data['ask']}")
            console.print(f"  Latency: {data['latency_us']} μs")
            
            return True
            
        except Exception as e:
            console.print(f"[red]✗ Tick 格式验证失败: {e}[/red]")
            return False
    
    async def verify_llm_weight_consumer(self) -> bool:
        """验证 LLM 权重消费者组"""
        console.print("\n[bold cyan]4. 验证 LLM 权重消费者组[/bold cyan]")
        
        try:
            # 检查消费者组
            groups = await self.redis.xinfo_groups("llm.weight")
            
            nautilus_group = None
            for group in groups:
                if group["name"] == "nautilus-llm-cg":
                    nautilus_group = group
                    break
            
            if not nautilus_group:
                console.print("[yellow]⚠ nautilus-llm-cg 消费者组不存在（LLMWeightActor 未启动）[/yellow]")
                return False
            
            # 检查消费者
            consumers = await self.redis.xinfo_consumers("llm.weight", "nautilus-llm-cg")
            
            if not consumers:
                console.print("[yellow]⚠ 消费者组存在但无活跃消费者[/yellow]")
                return False
            
            console.print(f"[green]✓ LLM 权重消费者组正常[/green]")
            console.print(f"  消费者数量: {len(consumers)}")
            console.print(f"  待处理消息: {nautilus_group['pending']}")
            
            return True
            
        except Exception as e:
            console.print(f"[yellow]⚠ LLM 权重消费者组检查失败: {e}[/yellow]")
            console.print("  （如果 LLMWeightActor 未启动，这是正常的）")
            return False
    
    async def test_llm_weight_injection(self) -> bool:
        """测试 LLM 权重注入"""
        console.print("\n[bold cyan]5. 测试 LLM 权重注入[/bold cyan]")
        
        try:
            # 构造测试权重
            test_weight = {
                "symbol": "BTC-USDT",
                "llm_score": 0.75,
                "confidence": 0.85,
                "horizon": "short",
                "key_drivers": ["Integration test"],
                "risk_events": [],
                "model_used": "test",
                "ts_ns": time.time_ns(),
                "ttl_ms": 300000,
            }
            
            # 发布到 Redis
            message_id = await self.redis.xadd(
                "llm.weight",
                fields={"data": json.dumps(test_weight)},
                maxlen=1000,
                approximate=True,
            )
            
            console.print(f"[green]✓ 测试权重已发布[/green]")
            console.print(f"  Message ID: {message_id}")
            console.print(f"  Score: {test_weight['llm_score']}")
            console.print(f"  Confidence: {test_weight['confidence']}")
            
            # 等待处理
            console.print("  等待 LLMWeightActor 处理...")
            await asyncio.sleep(2)
            
            # 检查是否被消费
            groups = await self.redis.xinfo_groups("llm.weight")
            for group in groups:
                if group["name"] == "nautilus-llm-cg":
                    if group["last-delivered-id"] >= message_id:
                        console.print("[green]✓ 权重已被消费[/green]")
                        return True
            
            console.print("[yellow]⚠ 权重未被消费（检查 LLMWeightActor 日志）[/yellow]")
            return False
            
        except Exception as e:
            console.print(f"[red]✗ LLM 权重注入测试失败: {e}[/red]")
            return False
    
    async def verify_order_event_format(self) -> bool:
        """验证订单事件格式"""
        console.print("\n[bold cyan]6. 验证订单事件格式[/bold cyan]")
        
        try:
            # 读取最新的订单事件
            entries = await self.redis.xread(
                streams={"order.event": "0"},
                count=1,
            )
            
            if not entries:
                console.print("[yellow]⚠ 没有订单事件（可能还未下单）[/yellow]")
                return False
            
            stream_name, messages = entries[0]
            message_id, fields = messages[0]
            
            # 解析 JSON
            data = json.loads(fields["data"])
            
            # 验证必需字段
            required_fields = ["event_id", "order_id", "symbol", "kind", "timestamp"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                console.print(f"[red]✗ 缺少字段: {missing_fields}[/red]")
                return False
            
            # 验证状态值
            valid_statuses = [
                "submitted", "accepted", "partial_filled",
                "filled", "cancelled", "rejected"
            ]
            if data["kind"] not in valid_statuses:
                console.print(f"[red]✗ 无效的订单状态: {data['kind']}[/red]")
                return False
            
            console.print("[green]✓ 订单事件格式正确[/green]")
            console.print(f"  Order ID: {data['order_id']}")
            console.print(f"  Symbol: {data['symbol']}")
            console.print(f"  Status: {data['kind']}")
            
            return True
            
        except Exception as e:
            console.print(f"[yellow]⚠ 订单事件验证失败: {e}[/yellow]")
            console.print("  （如果还未下单，这是正常的）")
            return False
    
    async def generate_report(self) -> None:
        """生成验证报告"""
        console.print("\n" + "=" * 60)
        console.print("[bold]验证报告[/bold]")
        console.print("=" * 60)
        
        # 创建表格
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("检查项", style="cyan", width=40)
        table.add_column("状态", width=10)
        table.add_column("说明", width=30)
        
        checks = [
            ("Redis 连接", self.results.get("redis_connection", False), "基础设施"),
            ("Redis Streams", self.results.get("redis_streams", False), "消息总线"),
            ("Tick 数据格式", self.results.get("tick_format", False), "RedisBridgeActor"),
            ("LLM 消费者组", self.results.get("llm_consumer", False), "LLMWeightActor"),
            ("LLM 权重注入", self.results.get("llm_injection", False), "权重流"),
            ("订单事件格式", self.results.get("order_format", False), "订单流"),
        ]
        
        passed = 0
        total = len(checks)
        
        for name, status, desc in checks:
            if status:
                table.add_row(name, "[green]✓ 通过[/green]", desc)
                passed += 1
            else:
                table.add_row(name, "[red]✗ 失败[/red]", desc)
        
        console.print(table)
        
        # 总结
        console.print(f"\n总计: {passed}/{total} 项通过")
        
        if passed == total:
            console.print(Panel(
                "[bold green]🎉 所有检查通过！Nautilus 整合正常工作。[/bold green]",
                title="成功",
                border_style="green"
            ))
        elif passed >= total * 0.7:
            console.print(Panel(
                f"[bold yellow]⚠ 部分检查未通过。请检查未启动的组件。[/bold yellow]",
                title="警告",
                border_style="yellow"
            ))
        else:
            console.print(Panel(
                "[bold red]❌ 多项检查失败。请检查配置和日志。[/bold red]",
                title="失败",
                border_style="red"
            ))
        
        # 下一步建议
        console.print("\n[bold]下一步建议：[/bold]")
        if not self.results.get("redis_connection"):
            console.print("  1. 启动 Redis: docker run -d -p 6379:6379 redis:alpine")
        if not self.results.get("tick_format"):
            console.print("  2. 启动 Nautilus 节点: python main.py --mode paper")
        if not self.results.get("llm_consumer"):
            console.print("  3. 检查 LLMWeightActor 是否在 main.py 中配置")
        if not self.results.get("order_format"):
            console.print("  4. 等待策略生成订单或手动测试下单")
    
    async def run(self) -> int:
        """运行所有验证"""
        console.print(Panel(
            "[bold]Nautilus Trader 整合验证[/bold]\n"
            "此脚本将验证 Nautilus 与 Redis 的集成是否正确",
            title="验证开始",
            border_style="blue"
        ))
        
        # 连接 Redis
        if not await self.connect_redis():
            return 1
        
        # 运行验证
        self.results["redis_connection"] = await self.verify_redis_connection()
        self.results["redis_streams"] = await self.verify_redis_streams()
        self.results["tick_format"] = await self.verify_tick_format()
        self.results["llm_consumer"] = await self.verify_llm_weight_consumer()
        self.results["llm_injection"] = await self.test_llm_weight_injection()
        self.results["order_format"] = await self.verify_order_event_format()
        
        # 生成报告
        await self.generate_report()
        
        # 关闭连接
        if self.redis:
            await self.redis.close()
        
        # 返回状态码
        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)
        
        return 0 if passed == total else 1


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="验证 Nautilus 整合")
    parser.add_argument(
        "--redis-url",
        default="redis://localhost:6379",
        help="Redis URL (默认: redis://localhost:6379)"
    )
    
    args = parser.parse_args()
    
    verifier = IntegrationVerifier(redis_url=args.redis_url)
    exit_code = await verifier.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]验证已取消[/yellow]")
        sys.exit(130)
