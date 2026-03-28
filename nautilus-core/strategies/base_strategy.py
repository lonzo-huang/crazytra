"""
自定义策略基类 - 扩展 Nautilus Strategy 以支持 LLM 权重
遵循 SYSTEM_SPEC.md 第 6 章和第 13 章规范

关键特性：
1. 继承 Nautilus Strategy，保持回测=实盘的特性
2. 添加 LLM 权重注入接口
3. 支持热重载状态迁移
4. 保持与原有策略层的兼容性
"""
from abc import abstractmethod
from decimal import Decimal
from typing import Any

from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy, StrategyConfig


class MirrorQuantStrategyConfig(StrategyConfig):
    """
    MirrorQuant 策略配置基类
    
    所有策略参数必须继承此类
    """
    # 是否启用 LLM 权重
    enable_llm: bool = True
    # LLM 权重影响系数（0-1）
    llm_weight_factor: float = 0.5
    # 最小置信度阈值
    min_confidence: float = 0.3


class MirrorQuantStrategy(Strategy):
    """
    MirrorQuant 策略基类
    
    扩展 Nautilus Strategy，添加 LLM 权重支持
    """
    
    def __init__(self, config: MirrorQuantStrategyConfig | None = None):
        super().__init__(config)
        
        # LLM 权重存储 {symbol: (score, confidence, metadata)}
        self._llm_weights: dict[str, tuple[float, float, dict]] = {}
        
        # 策略自定义状态（用于热重载）
        self._custom_state: dict[str, Any] = {}
    
    def on_start(self) -> None:
        """
        策略启动时调用
        
        子类应该覆盖此方法来订阅数据和初始化状态
        """
        self.log.info(f"{self.__class__.__name__} started")
        
        # 订阅 LLM 权重更新事件
        # 注意：需要在 LLMWeightActor 中发布 LLMWeightUpdate 事件
        # 这里订阅该事件类型
        from nautilus_core.actors.llm_weight_actor import LLMWeightUpdate
        self.subscribe_data(data_type=LLMWeightUpdate)
    
    def on_stop(self) -> None:
        """策略停止时调用"""
        self.log.info(f"{self.__class__.__name__} stopped")
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        """
        处理 quote tick
        
        子类必须实现此方法
        """
        pass
    
    def on_order_filled(self, event: OrderFilled) -> None:
        """
        处理订单成交事件
        
        子类可以覆盖此方法来更新内部状态
        """
        pass
    
    def on_data(self, data: Any) -> None:
        """
        处理自定义数据事件
        
        这里处理 LLM 权重更新
        """
        from nautilus_core.actors.llm_weight_actor import LLMWeightUpdate
        
        if isinstance(data, LLMWeightUpdate):
            self._on_llm_weight_update(data)
    
    def _on_llm_weight_update(self, update: Any) -> None:
        """
        处理 LLM 权重更新
        
        Args:
            update: LLMWeightUpdate 事件
        """
        symbol = update.symbol
        score = update.score
        confidence = update.confidence
        metadata = update.metadata
        
        # 存储权重
        self._llm_weights[symbol] = (score, confidence, metadata)
        
        self.log.info(
            f"LLM weight updated for {symbol}: "
            f"score={score:.3f}, confidence={confidence:.3f}"
        )
        
        # 调用子类的处理方法
        self.on_llm_weight_updated(symbol, score, confidence, metadata)
    
    def on_llm_weight_updated(
        self,
        symbol: str,
        score: float,
        confidence: float,
        metadata: dict,
    ) -> None:
        """
        LLM 权重更新回调
        
        子类可以覆盖此方法来响应权重变化
        
        Args:
            symbol: 标的符号
            score: LLM 评分 [-1.0, 1.0]
            confidence: 置信度 [0.0, 1.0]
            metadata: 元数据（horizon, key_drivers, risk_events）
        """
        pass
    
    def get_llm_weight(self, symbol: str) -> tuple[float, float] | None:
        """
        获取指定标的的 LLM 权重
        
        Returns:
            (score, confidence) 或 None
        """
        if symbol in self._llm_weights:
            score, confidence, _ = self._llm_weights[symbol]
            return (score, confidence)
        return None
    
    def get_effective_llm_factor(self, symbol: str) -> float:
        """
        获取有效的 LLM 影响因子
        
        根据 SYSTEM_SPEC.md 7.5 节：
        effective_score = llm_score × confidence
        
        Returns:
            影响因子 [0.0, 2.0]，1.0 表示中性
        """
        weight = self.get_llm_weight(symbol)
        if not weight:
            return 1.0  # 无权重时返回中性
        
        score, confidence = weight
        
        # 检查最小置信度阈值
        if confidence < self.config.min_confidence:
            return 1.0
        
        # 转换为影响因子
        # score ∈ [-1, 1] → factor ∈ [0.5, 2.0]
        # score = -1 (强烈看跌) → factor = 0.5
        # score = 0 (中性) → factor = 1.0
        # score = 1 (强烈看涨) → factor = 2.0
        effective_score = score * confidence
        factor = 1.0 + effective_score
        
        # 应用配置的权重系数
        # 如果 llm_weight_factor = 0.5，则影响减半
        adjusted_factor = 1.0 + (factor - 1.0) * self.config.llm_weight_factor
        
        return max(0.5, min(2.0, adjusted_factor))
    
    # ===== 热重载支持 =====
    
    def export_state(self) -> dict:
        """
        导出策略状态（用于热重载）
        
        子类应该覆盖此方法来导出自定义状态
        """
        return {
            "llm_weights": self._llm_weights,
            "custom_state": self._custom_state,
        }
    
    def import_state(self, state: dict) -> None:
        """
        导入策略状态（用于热重载）
        
        子类应该覆盖此方法来导入自定义状态
        """
        self._llm_weights = state.get("llm_weights", {})
        self._custom_state = state.get("custom_state", {})
    
    # ===== 辅助方法 =====
    
    def _convert_symbol_to_instrument_id(self, symbol: str) -> InstrumentId | None:
        """
        转换我们的 symbol 格式到 Nautilus InstrumentId
        
        BTC-USDT → BTCUSDT.BINANCE
        """
        # 简化实现，实际需要根据配置映射
        if "-" in symbol:
            base, quote = symbol.split("-")
            # 假设默认是 Binance
            return InstrumentId.from_str(f"{base}{quote}.BINANCE")
        return None
    
    @abstractmethod
    def calculate_signal_strength(self, tick: QuoteTick) -> float:
        """
        计算信号强度（子类必须实现）
        
        Returns:
            信号强度 [0.0, 1.0]
        """
        pass
    
    @abstractmethod
    def calculate_signal_direction(self, tick: QuoteTick) -> str:
        """
        计算信号方向（子类必须实现）
        
        Returns:
            "long" | "short" | "exit" | "hold"
        """
        pass
