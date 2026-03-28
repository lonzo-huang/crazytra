"""
临时策略基类
用于在 Rust 模块构建完成前测试策略功能
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MirrorQuantStrategyConfig:
    """临时策略配置类"""
    def __init__(self):
        self.enable_llm = True
        self.llm_weight_factor = 0.5
        self.min_confidence = 0.3


class MirrorQuantStrategy(ABC):
    """临时策略基类"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self.log = logger
        self.state = StrategyState()
        
        # LLM 权重存储
        self._llm_weights: Dict[str, tuple] = {}
    
    async def on_start(self) -> None:
        """策略启动"""
        self.log.info(f"{self.name} started")
    
    async def on_stop(self) -> None:
        """策略停止"""
        self.log.info(f"{self.name} stopped")
    
    async def on_quote_tick(self, tick) -> None:
        """处理报价数据"""
        pass
    
    async def on_trade_tick(self, tick) -> None:
        """处理成交数据"""
        pass
    
    def get_llm_weight(self, symbol: str) -> Optional[tuple]:
        """获取 LLM 权重"""
        return self._llm_weights.get(symbol)


class StrategyState:
    """策略状态"""
    def __init__(self):
        self.total_trades = 0
        self.last_trade_time = None
        self.total_pnl = 0.0
