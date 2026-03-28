"""
BTC 5分钟二元期权期望值策略
从 pmbot 迁移到 MirrorQuant 架构

这个策略基于 BTC 5分钟价格变动，计算期望值并寻找交易机会
"""

import asyncio
import logging
import math
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

import sys
import os

# 添加父目录到路径以导入模块
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from strategies.temp_base_strategy import MirrorQuantStrategy
from adapters.polymarket_python_fallback import get_polymarket_adapter

logger = logging.getLogger(__name__)


# 临时数据类型定义
@dataclass
class QuoteTick:
    instrument_id: str
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    ts_event: datetime
    ts_init: datetime


@dataclass
class TradeTick:
    instrument_id: str
    price: float
    size: float
    side: str
    trade_id: str
    ts_event: datetime
    ts_init: datetime


@dataclass
class Btc5mState:
    """BTC 5分钟状态数据"""
    start_time_ms: int
    start_price: float
    current_price: float
    sigma_per_second: float
    updated_at_ms: int


class Btc5mBinaryEVStrategy(MirrorQuantStrategy):
    """
    BTC 5分钟二元期权期望值策略
    
    基于几何布朗运动模型，计算 Yes/No 期权的期望值
    当期望值超过阈值时进行交易
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化策略
        
        Args:
            config: 策略配置
        """
        super().__init__("Btc5mBinaryEV", config)
        
        # 策略参数
        self.T = 300  # 5分钟 = 300秒
        self.min_entry_sec = 60
        self.max_entry_sec = 240
        self.late_entry_sec = 290
        self.ev_threshold = 0.05
        self.late_ev_threshold = 0.10
        self.max_late_price = 0.92
        
        # BTC 状态缓存
        self._btc_state: Optional[Btc5mState] = None
        self._last_state_update = 0
        
        # Polymarket 适配器
        self.polymarket_adapter = get_polymarket_adapter()
        
        logger.info("Btc5mBinaryEV strategy initialized")
    
    async def on_start(self) -> None:
        """策略启动时的初始化"""
        logger.info("Starting Btc5mBinaryEV strategy")
        
        # 启动 Polymarket 适配器
        if not self.polymarket_adapter.is_running:
            await self.polymarket_adapter.start()
        
        # 获取初始市场数据
        await self._update_btc_state()
        
        logger.info("Btc5mBinaryEV strategy started")
    
    async def on_stop(self) -> None:
        """策略停止时的清理"""
        logger.info("Stopping Btc5mBinaryEV strategy")
        
        # 停止 Polymarket 适配器
        if self.polymarket_adapter.is_running:
            await self.polymarket_adapter.stop()
        
        logger.info("Btc5mBinaryEV strategy stopped")
    
    async def on_quote_tick(self, tick: QuoteTick) -> None:
        """
        处理报价数据
        
        Args:
            tick: 报价数据
        """
        # 检查是否为 BTC 相关的 Polymarket 市场
        if not self._is_btc_market(tick.instrument_id):
            return
        
        # 更新 BTC 状态
        await self._update_btc_state()
        
        # 分析交易机会
        signal = await self._analyze_market(tick.instrument_id, tick)
        
        if signal:
            await self._execute_signal(signal)
    
    async def on_trade_tick(self, tick: TradeTick) -> None:
        """
        处理成交数据
        
        Args:
            tick: 成交数据
        """
        # 检查是否为 BTC 相关的 Polymarket 市场
        if not self._is_btc_market(tick.instrument_id):
            return
        
        # 更新 BTC 状态
        await self._update_btc_state()
        
        logger.debug(f"Trade tick for {tick.instrument_id}: {tick.price} x {tick.size}")
    
    async def _update_btc_state(self) -> None:
        """更新 BTC 状态数据"""
        now = datetime.now()
        
        # 检查是否需要更新（5秒缓存）
        if (now.timestamp() * 1000 - self._last_state_update) < 5000:
            return
        
        try:
            # 这里应该从外部数据源获取 BTC 5分钟状态
            # 暂时使用模拟数据
            self._btc_state = Btc5mState(
                start_time_ms=int((now - timedelta(minutes=2)).timestamp() * 1000),
                start_price=65000.0,
                current_price=65200.0,
                sigma_per_second=0.0001,  # 波动率
                updated_at_ms=int(now.timestamp() * 1000)
            )
            self._last_state_update = int(now.timestamp() * 1000)
            
            logger.debug("BTC state updated")
            
        except Exception as e:
            logger.error(f"Failed to update BTC state: {e}")
    
    def _is_btc_market(self, instrument_id: str) -> bool:
        """
        检查是否为 BTC 相关市场
        
        Args:
            instrument_id: 市场标识符
            
        Returns:
            是否为 BTC 市场
        """
        instrument_id_lower = instrument_id.lower()
        return ('btc' in instrument_id_lower or 
                'bitcoin' in instrument_id_lower) and \
               ('5m' in instrument_id_lower or 
                '5min' in instrument_id_lower or
                '5-minute' in instrument_id_lower)
    
    async def _analyze_market(self, asset_id: str, tick: QuoteTick) -> Optional[Dict[str, Any]]:
        """
        分析市场并生成交易信号
        
        Args:
            asset_id: 资产 ID
            tick: 报价数据
            
        Returns:
            交易信号或 None
        """
        if not self._btc_state:
            return None
        
        # 获取市场数据
        markets = await self.polymarket_adapter.fetch_markets()
        market = None
        for m in markets:
            if asset_id in m.asset_ids:
                market = m
                break
        
        if not market:
            logger.warning(f"Market not found for asset: {asset_id}")
            return None
        
        # 检查市场是否符合条件
        if not self._is_eligible_market(market):
            return None
        
        # 获取 Yes/No 价格
        yes_ask = tick.ask  # 假设当前 tick 是 Yes
        no_ask = 1.0 - yes_ask  # 简化计算
        
        # 计算期望值
        signal = self._calculate_ev_signal(
            asset_id, yes_ask, no_ask, market
        )
        
        return signal
    
    def _is_eligible_market(self, market) -> bool:
        """
        检查市场是否符合策略条件
        
        Args:
            market: 市场数据
            
        Returns:
            是否符合条件
        """
        question_lower = market.question.lower()
        
        # 检查是否为 BTC 5分钟市场
        is_btc = 'bitcoin' in question_lower or 'btc' in question_lower
        is_5m = '5' in question_lower and ('min' in question_lower or 'minute' in question_lower)
        
        if not (is_btc and is_5m):
            return False
        
        # 检查流动性
        if market.liquidity < 1000:
            return False
        
        # 检查是否活跃
        if not market.active:
            return False
        
        return True
    
    def _calculate_ev_signal(self, asset_id: str, yes_price: float, no_price: float, market) -> Optional[Dict[str, Any]]:
        """
        计算期望值信号
        
        Args:
            asset_id: 资产 ID
            yes_price: Yes 价格
            no_price: No 价格
            market: 市场数据
            
        Returns:
            交易信号或 None
        """
        if not self._btc_state:
            return None
        
        now = datetime.now().timestamp() * 1000
        elapsed_sec = (now - self._btc_state.start_time_ms) / 1000
        
        # 检查入场时间窗口
        if elapsed_sec < self.min_entry_sec or elapsed_sec > self.late_entry_sec:
            return None
        
        # 计算剩余时间
        remaining_sec = max(1, self.T - elapsed_sec)
        
        # 计算波动率
        sigma_rem = self._btc_state.sigma_per_second * math.sqrt(remaining_sec)
        if sigma_rem <= 0 or not math.isfinite(sigma_rem):
            return None
        
        # 计算价格变动
        delta = math.log(self._btc_state.current_price / self._btc_state.start_price)
        z = delta / sigma_rem
        
        # 计算 Yes 概率（标准正态分布 CDF）
        p_yes = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        
        # 计算期望值
        edge_yes = p_yes - yes_price
        edge_no = (1 - p_yes) - no_price
        
        # 确定阈值
        threshold = self.ev_threshold if elapsed_sec <= self.max_entry_sec else self.late_ev_threshold
        max_price = 0.98 if elapsed_sec <= self.max_entry_sec else self.max_late_price
        
        # 选择最优方向
        chosen = None
        if edge_yes > threshold and yes_price <= max_price:
            chosen = {
                'side': 'yes',
                'price': yes_price,
                'edge': edge_yes,
                'probability': p_yes
            }
        
        if edge_no > threshold and no_price <= max_price:
            if not chosen or edge_no > chosen['edge']:
                chosen = {
                    'side': 'no',
                    'price': no_price,
                    'edge': edge_no,
                    'probability': 1 - p_yes
                }
        
        if not chosen:
            return None
        
        # 计算置信度和仓位大小
        confidence = min(1.0, max(0.0, chosen['edge'] / 0.20))
        position_size = max(10.0, self.config.get('max_position_size', 100.0) * 
                          min(1.0, max(0.2, (chosen['edge'] - threshold) / 0.15)))
        
        signal = {
            'strategy': self.name,
            'asset_id': asset_id,
            'action': 'buy',
            'side': chosen['side'],
            'price': chosen['price'],
            'size': position_size,
            'confidence': confidence,
            'reason': f"t={elapsed_sec:.0f}s,P_{chosen['side']}={chosen['probability']*100:.1f}%,edge={chosen['edge']*100:.1f}%",
            'timestamp': datetime.now(),
            'market': market
        }
        
        logger.info(f"Signal generated: {signal['reason']}")
        return signal
    
    async def _execute_signal(self, signal: Dict[str, Any]) -> None:
        """
        执行交易信号
        
        Args:
            signal: 交易信号
        """
        try:
            # 这里应该调用执行引擎
            # 暂时只记录信号
            logger.info(f"Executing signal: {signal['side']} {signal['size']} @ {signal['price']}")
            
            # 更新策略状态
            self.state.total_trades += 1
            self.state.last_trade_time = datetime.now()
            
        except Exception as e:
            logger.error(f"Failed to execute signal: {e}")


# 策略工厂函数
def create_btc_5m_binary_ev_strategy(config: Optional[Dict[str, Any]] = None) -> Btc5mBinaryEVStrategy:
    """
    创建 BTC 5分钟二元期权策略实例
    
    Args:
        config: 策略配置
        
    Returns:
        策略实例
    """
    return Btc5mBinaryEVStrategy(config)


if __name__ == "__main__":
    # 测试策略
    import asyncio
    
    async def test_strategy():
        strategy = Btc5mBinaryEVStrategy()
        await strategy.on_start()
        
        # 模拟报价数据
        tick = QuoteTick(
            instrument_id="btc-updown-5m-1234567890",
            bid=0.48,
            ask=0.52,
            bid_size=1000.0,
            ask_size=1000.0,
            ts_event=datetime.now(),
            ts_init=datetime.now()
        )
        
        await strategy.on_quote_tick(tick)
        
        await strategy.on_stop()
    
    asyncio.run(test_strategy())
