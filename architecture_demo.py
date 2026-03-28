#!/usr/bin/env python3
"""
MirrorQuant 专业三层架构演示
不依赖外部服务的简化版本
"""

import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from polymarket_simple_data import PolymarketSimpleDataLoader, PolymarketMarket

# ============================================================================
# 专业三层架构核心组件
# ============================================================================

@dataclass
class MarketTickEvent:
    """市场行情事件"""
    symbol: str
    exchange: str
    price: float
    volume: float
    timestamp: int
    event_type: str = "market.tick"

@dataclass 
class OrderRequestEvent:
    """订单请求事件"""
    account_id: str
    symbol: str
    side: str  # BUY/SELL
    order_type: str  # MARKET/LIMIT
    quantity: float
    price: Optional[float]
    timestamp: int
    event_type: str = "order.request"

@dataclass
class OrderEvent:
    """订单事件"""
    account_id: str
    order_id: str
    symbol: str
    side: str
    status: str  # NEW/FILL/CANCEL/REJECT
    quantity: float
    price: Optional[float]
    timestamp: int
    event_type: str = "order.event"

class MockRedisStreamsEventBus:
    """模拟 Redis Streams 事件总线"""
    
    def __init__(self):
        self.events = []
        self.streams = {
            "market_tick": "market.tick.{exchange}.{symbol}",
            "order_request": "order.request.{account_id}",
            "order_event": "order.event.{account_id}",
            "position_update": "position.update.{account_id}",
            "account_state": "account.state.{account_id}",
            "llm_weight": "llm.weight.{strategy_id}"
        }
    
    def publish_market_tick(self, exchange: str, symbol: str, tick: MarketTickEvent) -> str:
        """发布市场行情事件"""
        stream_key = self.streams["market_tick"].format(exchange=exchange, symbol=symbol)
        event_data = asdict(tick)
        event_id = f"event_{len(self.events)}"
        self.events.append({
            "stream": stream_key,
            "id": event_id,
            "data": event_data,
            "timestamp": time.time()
        })
        print(f"📡 发布市场事件: {stream_key} -> {event_id}")
        return event_id
    
    def publish_order_request(self, account_id: str, request: OrderRequestEvent) -> str:
        """发布订单请求事件"""
        stream_key = self.streams["order_request"].format(account_id=account_id)
        event_data = asdict(request)
        event_id = f"event_{len(self.events)}"
        self.events.append({
            "stream": stream_key,
            "id": event_id,
            "data": event_data,
            "timestamp": time.time()
        })
        print(f"📡 发布订单请求: {stream_key} -> {event_id}")
        return event_id
    
    def publish_order_event(self, account_id: str, event: OrderEvent) -> str:
        """发布订单事件"""
        stream_key = self.streams["order_event"].format(account_id=account_id)
        event_data = asdict(event)
        event_id = f"event_{len(self.events)}"
        self.events.append({
            "stream": stream_key,
            "id": event_id,
            "data": event_data,
            "timestamp": time.time()
        })
        print(f"📡 发布订单事件: {stream_key} -> {event_id}")
        return event_id
    
    def get_events_by_stream(self, stream_pattern: str) -> List[Dict]:
        """获取指定流的事件"""
        return [event for event in self.events if stream_pattern in event["stream"]]

class MirrorQuantStrategyEngine:
    """MirrorQuant 策略引擎（平台层）"""
    
    def __init__(self, event_bus: MockRedisStreamsEventBus):
        self.event_bus = event_bus
        self.loader = PolymarketSimpleDataLoader()
        self.positions = {}
        self.order_counter = 1000
    
    def on_market_tick(self, tick: MarketTickEvent):
        """处理市场行情事件"""
        print(f"📊 策略引擎收到行情: {tick.symbol} @ {tick.price} (成交量: {tick.volume})")
        
        # 简单策略逻辑
        if tick.price > 0.5 and tick.volume > 1000:
            print(f"🎯 策略触发: 价格 {tick.price} > 0.5 且成交量 {tick.volume} > 1000")
            
            # 生成订单请求
            order_request = OrderRequestEvent(
                account_id="demo_account",
                symbol=tick.symbol,
                side="BUY",
                order_type="MARKET",
                quantity=10.0,
                price=None,
                timestamp=int(time.time() * 1000)
            )
            
            # 发送给风控引擎
            self.send_to_risk_engine(order_request)
        else:
            print(f"⏸️ 策略条件不满足，跳过")
    
    def send_to_risk_engine(self, order_request: OrderRequestEvent):
        """发送订单请求给风控引擎"""
        print(f"🛡️ 风控引擎检查: {order_request.symbol} {order_request.side} {order_request.quantity}")
        
        # 风控检查
        risk_check = self.risk_engine_check(order_request)
        
        if risk_check["passed"]:
            print(f"✅ 风控通过: {risk_check['reason']}")
            # 发送给执行引擎
            self.send_to_execution_engine(order_request)
        else:
            print(f"❌ 风控拒绝: {risk_check['reason']}")
    
    def risk_engine_check(self, order_request: OrderRequestEvent) -> Dict[str, Any]:
        """风控引擎检查"""
        # 简化风控逻辑
        checks = []
        
        # 数量检查
        if order_request.quantity > 100:
            checks.append("数量过大")
        
        # 频率检查
        if time.time() - getattr(self, '_last_order_time', 0) < 1:
            checks.append("频率过高")
        
        self._last_order_time = time.time()
        
        return {
            "passed": len(checks) == 0,
            "reason": "; ".join(checks) if checks else "检查通过"
        }
    
    def send_to_execution_engine(self, order_request: OrderRequestEvent):
        """发送给执行引擎"""
        print(f"🚀 执行引擎处理订单: {order_request.symbol}")
        
        # 发布到 Redis Streams
        event_id = self.event_bus.publish_order_request(
            order_request.account_id, 
            order_request
        )
        
        # 模拟执行引擎处理
        self.process_order_execution(order_request)
    
    def process_order_execution(self, order_request: OrderRequestEvent):
        """处理订单执行"""
        # 生成订单 ID
        order_id = f"MQ_ORDER_{self.order_counter}"
        self.order_counter += 1
        
        print(f"📋 执行引擎生成订单: {order_id}")
        
        # 模拟订单执行延迟
        time.sleep(0.1)
        
        # 发布订单事件
        order_event = OrderEvent(
            account_id=order_request.account_id,
            order_id=order_id,
            symbol=order_request.symbol,
            side=order_request.side,
            status="FILL",
            quantity=order_request.quantity,
            price=0.45,  # 模拟成交价格
            timestamp=int(time.time() * 1000)
        )
        
        event_id = self.event_bus.publish_order_event(
            order_request.account_id,
            order_event
        )
        
        # 通知策略引擎
        self.on_order_event(order_event)
    
    def on_order_event(self, event: OrderEvent):
        """处理订单事件"""
        print(f"📈 策略引擎收到订单事件: {event.order_id} {event.status}")
        
        # 更新持仓
        if event.status == "FILL":
            self.update_position(event)
    
    def update_position(self, event: OrderEvent):
        """更新持仓"""
        key = f"{event.account_id}:{event.symbol}"
        if key not in self.positions:
            self.positions[key] = {"quantity": 0, "avg_price": 0, "total_cost": 0}
        
        position = self.positions[key]
        
        if event.side == "BUY":
            new_quantity = position["quantity"] + event.quantity
            new_total_cost = position["total_cost"] + (event.quantity * event.price)
            position["quantity"] = new_quantity
            position["avg_price"] = new_total_cost / new_quantity if new_quantity > 0 else 0
            position["total_cost"] = new_total_cost
        else:
            position["quantity"] -= event.quantity
        
        print(f"💼 持仓更新: {key}")
        print(f"   数量: {position['quantity']:.2f}")
        print(f"   均价: {position['avg_price']:.4f}")

class NautilusTraderRunner:
    """NautilusTrader Runner（执行后端）"""
    
    def __init__(self, event_bus: MockRedisStreamsEventBus):
        self.event_bus = event_bus
        self.order_counter = 2000
        self.subscribed_streams = []
    
    def subscribe_to_order_requests(self, account_id: str):
        """订阅订单请求"""
        stream_key = f"order.request.{account_id}"
        print(f"🦀 NautilusTrader Runner 订阅: {stream_key}")
        self.subscribed_streams.append(stream_key)
        
        # 模拟处理订单请求
        self.process_pending_orders(account_id)
    
    def process_pending_orders(self, account_id: str):
        """处理待处理订单"""
        stream_key = f"order.request.{account_id}"
        events = self.event_bus.get_events_by_stream(stream_key)
        
        for event in events:
            if not event.get("processed", False):
                print(f"🦀 处理订单请求: {event['id']}")
                
                # 转换为 NT 内部格式
                order_request = event["data"]
                
                # 执行订单
                self.execute_order_with_nt(order_request)
                
                # 标记为已处理
                event["processed"] = True
    
    def execute_order_with_nt(self, order_request: Dict[str, Any]):
        """使用 NautilusTrader 执行订单"""
        print(f"🦀 NautilusTrader 执行订单:")
        print(f"   账户: {order_request['account_id']}")
        print(f"   标的: {order_request['symbol']}")
        print(f"   方向: {order_request['side']}")
        print(f"   数量: {order_request['quantity']}")
        
        # 生成 NT 订单 ID
        nt_order_id = f"NT_ORDER_{self.order_counter}"
        self.order_counter += 1
        
        # 模拟 NT 执行
        time.sleep(0.05)
        
        # 发布执行结果
        order_event = OrderEvent(
            account_id=order_request["account_id"],
            order_id=nt_order_id,
            symbol=order_request["symbol"],
            side=order_request["side"],
            status="FILL",
            quantity=order_request["quantity"],
            price=0.44,  # NT 执行价格
            timestamp=int(time.time() * 1000)
        )
        
        self.event_bus.publish_order_event(
            order_request["account_id"],
            order_event
        )
        
        print(f"🦀 NT 执行完成: {nt_order_id}")

# ============================================================================
# 演示和测试
# ============================================================================

def demonstrate_professional_architecture():
    """演示专业三层架构"""
    print("🎯 MirrorQuant 专业三层架构完整演示")
    print("=" * 70)
    
    # 1. 初始化事件总线
    print("\n📡 第1层：Redis Streams 事件总线")
    event_bus = MockRedisStreamsEventBus()
    print("✅ 事件总线初始化完成")
    
    # 2. 初始化平台层组件
    print("\n🏗️ 第2层：MirrorQuant 平台层")
    strategy_engine = MirrorQuantStrategyEngine(event_bus)
    print("✅ 策略引擎初始化完成")
    
    # 3. 初始化执行后端
    print("\n🦀 第3层：NautilusTrader Runner 执行后端")
    nautilus_runner = NautilusTraderRunner(event_bus)
    print("✅ NautilusTrader Runner 初始化完成")
    
    # 4. 模拟完整数据流
    print("\n🔄 完整数据流演示:")
    print("-" * 50)
    
    # 4.1 行情流：Polymarket → Redis → MirrorQuant
    print("\n📊 步骤1: 行情流 (Polymarket → Redis → MirrorQuant)")
    loader = PolymarketSimpleDataLoader()
    markets = loader.fetch_markets(active=True, limit=5)
    
    for i, market in enumerate(markets[:3], 1):
        print(f"\n  市场{i}: {market.question[:50]}...")
        
        # 创建行情事件
        tick = MarketTickEvent(
            symbol=f"POLY_{market.id}",
            exchange="POLYMARKET",
            price=0.45 + (market.volume / 100000),  # 模拟价格
            volume=market.volume,
            timestamp=int(time.time() * 1000)
        )
        
        # 发布到事件总线
        event_bus.publish_market_tick("POLYMARKET", f"POLY_{market.id}", tick)
        
        # 策略引擎处理
        strategy_engine.on_market_tick(tick)
        
        time.sleep(0.5)
    
    # 4.2 订单流：StrategyEngine → RiskEngine → ExecutionEngine → Redis → NautilusTrader
    print(f"\n🚀 步骤2: 订单流 (StrategyEngine → RiskEngine → ExecutionEngine → Redis → NautilusTrader)")
    nautilus_runner.subscribe_to_order_requests("demo_account")
    
    # 4.3 订单回报流：NautilusTrader → Redis → MirrorQuant
    print(f"\n📈 步骤3: 订单回报流 (NautilusTrader → Redis → MirrorQuant)")
    print("   (已在步骤2中处理)")
    
    # 5. 显示事件统计
    print(f"\n📊 事件统计:")
    print(f"   总事件数: {len(event_bus.events)}")
    
    market_events = event_bus.get_events_by_stream("market.tick")
    order_request_events = event_bus.get_events_by_stream("order.request")
    order_events = event_bus.get_events_by_stream("order.event")
    
    print(f"   行情事件: {len(market_events)}")
    print(f"   订单请求: {len(order_request_events)}")
    print(f"   订单事件: {len(order_events)}")
    
    # 6. 显示持仓状态
    print(f"\n💼 持仓状态:")
    if strategy_engine.positions:
        for key, position in strategy_engine.positions.items():
            print(f"   {key}: {position}")
    else:
        print("   暂无持仓")
    
    print(f"\n🎉 专业三层架构演示完成！")
    
    # 7. 总结架构优势
    print(f"\n✨ 架构优势总结:")
    print(f"   🏗️  三层解耦: 平台层、事件层、执行层完全分离")
    print(f"   📡 事件驱动: Redis Streams 提供完全解耦的异步通信")
    print(f"   🔄 可扩展: 每层都可独立水平扩展")
    print(f"   💼 多租户: Redis 命名空间天然支持用户隔离")
    print(f"   🦀 高性能: NautilusTrader 提供专业级执行引擎")
    print(f"   🎯 专业化: 基于官方 NautilusTrader Polymarket 集成")
    print(f"   🧪 可测试: 每层都可独立测试和验证")

def main():
    """主函数"""
    print("🚀 MirrorQuant × NautilusTrader × Polymarket 专业架构解决方案")
    print("=" * 80)
    print("基于官方 NautilusTrader 文档和专业三层事件驱动架构")
    
    # 1. 测试 Polymarket 数据获取
    print(f"\n📊 测试 Polymarket 数据获取...")
    loader = PolymarketSimpleDataLoader()
    markets = loader.fetch_markets(active=True, limit=5)
    print(f"✅ 成功获取 {len(markets)} 个活跃 Polymarket 市场")
    
    # 2. 演示专业架构
    demonstrate_professional_architecture()
    
    print(f"\n🎯 解决方案完成状态:")
    print(f"   ✅ 基于官方 NautilusTrader Polymarket 文档")
    print(f"   ✅ 实现专业三层事件驱动架构")
    print(f"   ✅ 支持 Polymarket 实时数据获取")
    print(f"   ✅ Redis Streams 事件总线模拟")
    print(f"   ✅ 完整的订单执行流程")
    print(f"   ✅ 多租户 SaaS 友好设计")
    print(f"   ✅ 可水平扩展架构")
    print(f"   ✅ 风控和持仓管理")
    
    print(f"\n🚀 下一步开发重点:")
    print(f"   1. 🔧 修复 Rust JSON 解析问题")
    print(f"   2. 📡 集成真实 Redis Streams")
    print(f"   3. 🦀 集成真实 NautilusTrader Runner")
    print(f"   4. 💼 实现多租户用户管理")
    print(f"   5. 🎯 完善策略和风控逻辑")

if __name__ == "__main__":
    main()
