"""
Polymarket 适配器配置
"""

from decimal import Decimal
from typing import Optional

from nautilus_trader.config import LiveDataClientConfig
from nautilus_trader.config import LiveExecClientConfig


class PolymarketDataClientConfig(LiveDataClientConfig):
    """Polymarket 数据客户端配置"""
    
    api_key: Optional[str] = None
    poll_interval_secs: int = 5
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        poll_interval_secs: int = 5,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.poll_interval_secs = poll_interval_secs


class PolymarketExecClientConfig(LiveExecClientConfig):
    """Polymarket 执行客户端配置"""
    
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    paper_trading: bool = True
    initial_balance: Decimal = Decimal("10000.00")
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        paper_trading: bool = True,
        initial_balance: Decimal = Decimal("10000.00"),
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.api_secret = api_secret
        self.paper_trading = paper_trading
        self.initial_balance = initial_balance


# Polymarket 市场定义
class PolymarketMarketConfig:
    """Polymarket 市场配置"""
    
    def __init__(
        self,
        condition_id: str,
        asset_id: str,
        slug: str,
        question: str,
    ):
        self.condition_id = condition_id
        self.asset_id = asset_id
        self.slug = slug
        self.question = question
    
    def to_instrument_id(self) -> str:
        """转换为 Nautilus InstrumentId 格式"""
        # 格式：SLUG.POLYMARKET
        return f"{self.slug.upper().replace('-', '_')}.POLYMARKET"


# 示例市场配置
EXAMPLE_MARKETS = [
    PolymarketMarketConfig(
        condition_id="0x...",  # 实际的 condition_id
        asset_id="0x...",      # 实际的 asset_id
        slug="will-bitcoin-hit-100k-by-2024",
        question="Will Bitcoin hit $100k by end of 2024?",
    ),
    PolymarketMarketConfig(
        condition_id="0x...",
        asset_id="0x...",
        slug="trump-wins-2024",
        question="Will Trump win the 2024 election?",
    ),
]
