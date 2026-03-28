#!/usr/bin/env python3
"""
MirrorQuant Tick 标准类型定义（Python Pydantic）
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class OrderBookLevel(BaseModel):
    """订单簿档位"""
    price: float = Field(ge=0, description="价格")
    size: float = Field(ge=0, description="数量")


class OrderBook(BaseModel):
    """完整订单簿"""
    bids: List[OrderBookLevel] = Field(default_factory=list, description="买单")
    asks: List[OrderBookLevel] = Field(default_factory=list, description="卖单")


class PolymarketExtension(BaseModel):
    """Polymarket 专用扩展字段"""
    outcome: Optional[Literal["YES", "NO"]] = Field(None, description="预测结果")
    liquidity: Optional[float] = Field(None, ge=0, description="流动性")
    probability: Optional[float] = Field(None, ge=0, le=1, description="隐含概率")
    market_type: Optional[Literal["binary", "categorical"]] = Field(None, description="市场类型")


class MQTickPayload(BaseModel):
    """MQ Tick 核心数据"""
    symbol: str = Field(..., pattern=r"^[A-Z]+:[A-Z0-9_]+$", description="MQ 统一符号")
    market_id: str = Field(..., description="交易所原始市场 ID")
    instrument_type: Literal["prediction", "spot", "future", "option", "swap"] = Field(..., description="资产类型")
    exchange: str = Field(..., description="交易所名称")
    
    # 最佳买卖价
    bid: Optional[float] = Field(None, ge=0, description="最优买价")
    ask: Optional[float] = Field(None, ge=0, description="最优卖价")
    mid: Optional[float] = Field(None, ge=0, description="中间价")
    
    # 最佳买卖量
    bid_size: Optional[float] = Field(None, ge=0, description="最优买量")
    ask_size: Optional[float] = Field(None, ge=0, description="最优卖量")
    
    # 最新成交
    last_price: Optional[float] = Field(None, ge=0, description="最新成交价")
    last_size: Optional[float] = Field(None, ge=0, description="最新成交量")
    last_side: Optional[Literal["buy", "sell"]] = Field(None, description="最新成交方向")
    
    # 市场统计
    volume_24h: Optional[float] = Field(None, ge=0, description="24小时成交量")
    open_interest: Optional[float] = Field(None, ge=0, description="未平仓量")
    
    # 完整订单簿（可选）
    orderbook: Optional[OrderBook] = Field(None, description="完整订单簿")
    
    # Polymarket 专用扩展
    polymarket: Optional[PolymarketExtension] = Field(None, description="Polymarket 扩展字段")


class MQTickEvent(BaseModel):
    """MQ Tick 完整事件（顶层 Envelope）"""
    type: Literal["market_tick"] = Field("market_tick", description="事件类型")
    ts_event: int = Field(..., ge=0, description="MQ 接收时间戳（毫秒）")
    ts_exchange: int = Field(..., ge=0, description="交易所事件时间戳（毫秒）")
    source: Literal["polymarket", "binance", "trading212", "tiger", "okx", "bybit"] = Field(..., description="数据来源")
    payload: MQTickPayload = Field(..., description="Tick 核心数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "market_tick",
                "ts_event": 1710000000123,
                "ts_exchange": 1710000000100,
                "source": "polymarket",
                "payload": {
                    "symbol": "POLY:TRUMP_WIN",
                    "market_id": "0xabc123",
                    "instrument_type": "prediction",
                    "exchange": "polymarket",
                    "bid": 0.62,
                    "ask": 0.63,
                    "mid": 0.625,
                    "bid_size": 1200,
                    "ask_size": 900,
                    "last_price": 0.63,
                    "last_size": 100,
                    "last_side": "buy",
                    "volume_24h": 120000,
                    "polymarket": {
                        "outcome": "YES",
                        "probability": 0.63,
                        "market_type": "binary"
                    }
                }
            }
        }


# ============================================================================
# NT Tick → MQ Tick 转换器
# ============================================================================

class NTToMQTickConverter:
    """NautilusTrader Tick → MirrorQuant Tick 转换器"""
    
    @staticmethod
    def convert_polymarket_tick(nt_tick: dict, market_data: dict) -> MQTickEvent:
        """
        将 NT 的 Polymarket Tick 转换为 MQ Tick
        
        Args:
            nt_tick: NautilusTrader 的 Tick 数据（dict 格式）
            market_data: Polymarket 市场元数据
            
        Returns:
            MQTickEvent: MQ 标准化 Tick 事件
        """
        import time
        
        # 构建 MQ 符号
        symbol = f"POLY:{market_data.get('id', 'UNKNOWN')}"
        
        # 提取价格数据
        bid = nt_tick.get('bid_price') or nt_tick.get('best_bid_price')
        ask = nt_tick.get('ask_price') or nt_tick.get('best_ask_price')
        mid = (bid + ask) / 2 if bid and ask else None
        
        # 构建 Payload
        payload = MQTickPayload(
            symbol=symbol,
            market_id=market_data.get('id', ''),
            instrument_type="prediction",
            exchange="polymarket",
            bid=bid,
            ask=ask,
            mid=mid,
            bid_size=nt_tick.get('bid_size'),
            ask_size=nt_tick.get('ask_size'),
            last_price=nt_tick.get('last_price'),
            last_size=nt_tick.get('last_size'),
            last_side=nt_tick.get('last_side'),
            volume_24h=market_data.get('volume', 0),
            polymarket=PolymarketExtension(
                liquidity=market_data.get('liquidity'),
                probability=mid,  # 价格即为隐含概率
                market_type="binary"
            )
        )
        
        # 构建完整事件
        return MQTickEvent(
            type="market_tick",
            ts_event=int(time.time() * 1000),
            ts_exchange=nt_tick.get('ts_event', int(time.time() * 1000)),
            source="polymarket",
            payload=payload
        )
    
    @staticmethod
    def convert_from_polymarket_simple(market: dict) -> MQTickEvent:
        """
        从简化的 Polymarket 市场数据创建 MQ Tick
        
        Args:
            market: Polymarket 市场数据（来自 polymarket_simple_data.py）
            
        Returns:
            MQTickEvent: MQ 标准化 Tick 事件
        """
        import time
        
        # 模拟价格（实际应该从订单簿获取）
        mid_price = 0.5  # 默认中间价
        spread = 0.01
        
        payload = MQTickPayload(
            symbol=f"POLY:{market.get('id', 'UNKNOWN')}",
            market_id=market.get('id', ''),
            instrument_type="prediction",
            exchange="polymarket",
            bid=mid_price - spread / 2,
            ask=mid_price + spread / 2,
            mid=mid_price,
            bid_size=1000,
            ask_size=1000,
            volume_24h=float(market.get('volume', 0)),
            polymarket=PolymarketExtension(
                liquidity=float(market.get('liquidity', 0)),
                probability=mid_price,
                market_type="binary"
            )
        )
        
        return MQTickEvent(
            type="market_tick",
            ts_event=int(time.time() * 1000),
            ts_exchange=int(time.time() * 1000),
            source="polymarket",
            payload=payload
        )


# ============================================================================
# 测试和示例
# ============================================================================

def test_mq_tick_types():
    """测试 MQ Tick 类型定义"""
    import json
    
    print("🧪 测试 MQ Tick 类型定义")
    print("=" * 50)
    
    # 1. 创建示例 Tick
    tick = MQTickEvent(
        type="market_tick",
        ts_event=1710000000123,
        ts_exchange=1710000000100,
        source="polymarket",
        payload=MQTickPayload(
            symbol="POLY:TRUMP_WIN",
            market_id="0xabc123",
            instrument_type="prediction",
            exchange="polymarket",
            bid=0.62,
            ask=0.63,
            mid=0.625,
            bid_size=1200,
            ask_size=900,
            last_price=0.63,
            last_size=100,
            last_side="buy",
            volume_24h=120000,
            polymarket=PolymarketExtension(
                outcome="YES",
                probability=0.63,
                market_type="binary"
            )
        )
    )
    
    print("✅ MQ Tick 创建成功")
    
    # 2. 序列化为 JSON
    tick_json = tick.model_dump_json(indent=2)
    print("\n📋 JSON 格式:")
    print(tick_json)
    
    # 3. 反序列化
    tick_restored = MQTickEvent.model_validate_json(tick_json)
    print("\n✅ JSON 反序列化成功")
    
    # 4. 验证字段
    assert tick_restored.payload.symbol == "POLY:TRUMP_WIN"
    assert tick_restored.payload.bid == 0.62
    assert tick_restored.payload.polymarket.probability == 0.63
    print("✅ 字段验证通过")
    
    # 5. 测试转换器
    print("\n🔄 测试 NT → MQ 转换器...")
    from polymarket_simple_data import PolymarketSimpleDataLoader
    
    loader = PolymarketSimpleDataLoader()
    markets = loader.fetch_markets(active=True, limit=1)
    
    if markets:
        market_dict = {
            'id': markets[0].id,
            'volume': markets[0].volume,
            'liquidity': markets[0].liquidity
        }
        
        mq_tick = NTToMQTickConverter.convert_from_polymarket_simple(market_dict)
        print(f"✅ 转换成功: {mq_tick.payload.symbol}")
        print(f"   价格: {mq_tick.payload.mid}")
        print(f"   成交量: {mq_tick.payload.volume_24h}")


if __name__ == "__main__":
    test_mq_tick_types()
