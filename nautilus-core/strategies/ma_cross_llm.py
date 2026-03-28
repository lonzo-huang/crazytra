"""
均线交叉策略 + LLM 权重增强
演示如何在 Nautilus 策略中使用 LLM 权重
"""
from collections import deque
from decimal import Decimal

from nautilus_trader.indicators.average.ema import ExponentialMovingAverage
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.orders import MarketOrder
from pydantic import Field

from nautilus_core.strategies.base_strategy import MirrorQuantStrategy, MirrorQuantStrategyConfig


class MACrossLLMConfig(MirrorQuantStrategyConfig):
    """均线交叉策略配置"""
    instrument_id: str
    fast_period: int = Field(default=10, ge=2, le=100)
    slow_period: int = Field(default=30, ge=5, le=200)
    trade_size: Decimal = Field(default=Decimal("0.01"))
    # LLM 配置继承自 MirrorQuantStrategyConfig
    enable_llm: bool = True
    llm_weight_factor: float = 0.5


class MACrossLLMStrategy(MirrorQuantStrategy):
    """
    均线交叉策略 + LLM 权重增强
    
    逻辑：
    1. 快线上穿慢线 → 做多信号
    2. 快线下穿慢线 → 做空信号
    3. LLM 权重调整仓位大小：
       - LLM 看涨 → 增加多头仓位
       - LLM 看跌 → 减少多头仓位或增加空头仓位
    """
    
    def __init__(self, config: MACrossLLMConfig):
        super().__init__(config)
        
        # 策略配置
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.trade_size = config.trade_size
        
        # 技术指标
        self.fast_ema: ExponentialMovingAverage | None = None
        self.slow_ema: ExponentialMovingAverage | None = None
        
        # 状态追踪
        self._last_cross: str | None = None  # "golden" or "death"
        self._position_side: str | None = None  # "long" or "short" or None
        
        # 价格历史（用于计算 EMA）
        self._price_history: deque = deque(maxlen=config.slow_period * 2)
    
    def on_start(self) -> None:
        """策略启动"""
        super().on_start()
        
        # 订阅行情
        self.subscribe_quote_ticks(self.instrument_id)
        
        # 初始化指标
        self.fast_ema = ExponentialMovingAverage(self.config.fast_period)
        self.slow_ema = ExponentialMovingAverage(self.config.slow_period)
        
        self.log.info(
            f"MACrossLLM started: {self.instrument_id}, "
            f"fast={self.config.fast_period}, slow={self.config.slow_period}, "
            f"llm_enabled={self.config.enable_llm}"
        )
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        """处理行情 tick"""
        # 计算中间价
        mid_price = (tick.bid_price + tick.ask_price) / 2
        
        # 更新指标
        self.fast_ema.update_raw(float(mid_price))
        self.slow_ema.update_raw(float(mid_price))
        
        # 等待指标预热
        if not self.fast_ema.initialized or not self.slow_ema.initialized:
            return
        
        # 检测交叉
        fast_value = self.fast_ema.value
        slow_value = self.slow_ema.value
        
        # 金叉：快线上穿慢线
        if fast_value > slow_value and self._last_cross != "golden":
            self._last_cross = "golden"
            self._on_golden_cross(tick)
        
        # 死叉：快线下穿慢线
        elif fast_value < slow_value and self._last_cross != "death":
            self._last_cross = "death"
            self._on_death_cross(tick)
    
    def _on_golden_cross(self, tick: QuoteTick) -> None:
        """金叉信号处理"""
        self.log.info(f"Golden cross detected at {tick.bid_price}")
        
        # 计算基础信号强度
        base_strength = self.calculate_signal_strength(tick)
        
        # 获取 LLM 调整因子
        symbol = self._convert_instrument_to_symbol(tick.instrument_id)
        llm_factor = self.get_effective_llm_factor(symbol)
        
        # 调整后的仓位大小
        adjusted_size = float(self.trade_size) * base_strength * llm_factor
        
        self.log.info(
            f"Golden cross: base_strength={base_strength:.2f}, "
            f"llm_factor={llm_factor:.2f}, adjusted_size={adjusted_size:.4f}"
        )
        
        # 如果已有空头仓位，先平仓
        if self._position_side == "short":
            self._close_position(tick)
        
        # 开多头仓位
        if adjusted_size > 0.001:  # 最小仓位阈值
            self._open_long(tick, Decimal(str(adjusted_size)))
    
    def _on_death_cross(self, tick: QuoteTick) -> None:
        """死叉信号处理"""
        self.log.info(f"Death cross detected at {tick.ask_price}")
        
        # 计算基础信号强度
        base_strength = self.calculate_signal_strength(tick)
        
        # 获取 LLM 调整因子
        symbol = self._convert_instrument_to_symbol(tick.instrument_id)
        llm_factor = self.get_effective_llm_factor(symbol)
        
        # LLM 看跌时增强空头信号
        # llm_factor < 1.0 表示看跌
        adjusted_factor = 2.0 - llm_factor if llm_factor < 1.0 else 1.0
        adjusted_size = float(self.trade_size) * base_strength * adjusted_factor
        
        self.log.info(
            f"Death cross: base_strength={base_strength:.2f}, "
            f"llm_factor={llm_factor:.2f}, adjusted_size={adjusted_size:.4f}"
        )
        
        # 如果已有多头仓位，先平仓
        if self._position_side == "long":
            self._close_position(tick)
        
        # 开空头仓位
        if adjusted_size > 0.001:
            self._open_short(tick, Decimal(str(adjusted_size)))
    
    def _open_long(self, tick: QuoteTick, size: Decimal) -> None:
        """开多头仓位"""
        order = self.order_factory.market(
            instrument_id=tick.instrument_id,
            order_side=OrderSide.BUY,
            quantity=size,
        )
        self.submit_order(order)
        self._position_side = "long"
    
    def _open_short(self, tick: QuoteTick, size: Decimal) -> None:
        """开空头仓位"""
        order = self.order_factory.market(
            instrument_id=tick.instrument_id,
            order_side=OrderSide.SELL,
            quantity=size,
        )
        self.submit_order(order)
        self._position_side = "short"
    
    def _close_position(self, tick: QuoteTick) -> None:
        """平仓"""
        if not self._position_side:
            return
        
        # 获取当前持仓
        position = self.cache.position(tick.instrument_id)
        if not position or position.is_closed:
            self._position_side = None
            return
        
        # 反向平仓
        side = OrderSide.SELL if position.is_long else OrderSide.BUY
        order = self.order_factory.market(
            instrument_id=tick.instrument_id,
            order_side=side,
            quantity=position.quantity,
        )
        self.submit_order(order)
        self._position_side = None
    
    def calculate_signal_strength(self, tick: QuoteTick) -> float:
        """
        计算信号强度
        
        基于快慢线的距离
        """
        if not self.fast_ema or not self.slow_ema:
            return 0.0
        
        fast_value = self.fast_ema.value
        slow_value = self.slow_ema.value
        
        # 距离越大，信号越强
        distance = abs(fast_value - slow_value) / slow_value
        
        # 归一化到 [0, 1]
        strength = min(distance * 10, 1.0)
        
        return strength
    
    def calculate_signal_direction(self, tick: QuoteTick) -> str:
        """计算信号方向"""
        if not self.fast_ema or not self.slow_ema:
            return "hold"
        
        if self.fast_ema.value > self.slow_ema.value:
            return "long"
        elif self.fast_ema.value < self.slow_ema.value:
            return "short"
        else:
            return "hold"
    
    def on_llm_weight_updated(
        self,
        symbol: str,
        score: float,
        confidence: float,
        metadata: dict,
    ) -> None:
        """LLM 权重更新回调"""
        self.log.info(
            f"LLM weight updated for {symbol}: "
            f"score={score:.3f}, confidence={confidence:.3f}, "
            f"horizon={metadata.get('horizon')}"
        )
        
        # 如果 LLM 信号与当前持仓方向相反且置信度很高，考虑平仓
        if confidence > 0.8:
            if score < -0.5 and self._position_side == "long":
                self.log.warning("LLM strongly bearish, consider closing long position")
            elif score > 0.5 and self._position_side == "short":
                self.log.warning("LLM strongly bullish, consider closing short position")
    
    def _convert_instrument_to_symbol(self, instrument_id: InstrumentId) -> str:
        """转换 InstrumentId 到我们的 symbol 格式"""
        symbol_str = instrument_id.symbol.value
        if "USDT" in symbol_str:
            base = symbol_str.replace("USDT", "")
            return f"{base}-USDT"
        return symbol_str
    
    def export_state(self) -> dict:
        """导出状态"""
        state = super().export_state()
        state.update({
            "last_cross": self._last_cross,
            "position_side": self._position_side,
        })
        return state
    
    def import_state(self, state: dict) -> None:
        """导入状态"""
        super().import_state(state)
        self._last_cross = state.get("last_cross")
        self._position_side = state.get("position_side")
