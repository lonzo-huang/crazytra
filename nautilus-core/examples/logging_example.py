"""
日志使用示例

展示如何在 Nautilus 策略中正确使用日志。
"""

from decimal import Decimal

from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId

from config.logging_config import get_logger
from strategies.base_strategy import CrazytraStrategy, CrazytraStrategyConfig


class LoggingExampleConfig(CrazytraStrategyConfig):
    """示例策略配置"""
    instrument_id: str
    threshold: Decimal = Decimal("0.5")


class LoggingExampleStrategy(CrazytraStrategy):
    """
    日志使用示例策略
    
    展示如何在策略中正确记录日志。
    """
    
    def __init__(self, config: LoggingExampleConfig):
        super().__init__(config)
        
        # 获取 logger（带策略名称）
        self.log = get_logger(f"strategy.{self.__class__.__name__}")
        
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.threshold = config.threshold
        
        # 内部状态
        self._tick_count = 0
        self._signal_count = 0
        self._order_count = 0
    
    def on_start(self) -> None:
        """策略启动"""
        super().on_start()
        
        # INFO: 记录策略启动
        self.log.info(
            "strategy_started",
            strategy_id=self.id,
            instrument=str(self.instrument_id),
            threshold=str(self.threshold),
            llm_enabled=self.config.enable_llm,
        )
        
        # 订阅数据
        self.subscribe_quote_ticks(self.instrument_id)
        
        self.log.info(
            "subscribed_to_quotes",
            instrument=str(self.instrument_id),
        )
    
    def on_stop(self) -> None:
        """策略停止"""
        # INFO: 记录策略停止和统计
        self.log.info(
            "strategy_stopped",
            strategy_id=self.id,
            tick_count=self._tick_count,
            signal_count=self._signal_count,
            order_count=self._order_count,
        )
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        """处理 quote tick"""
        self._tick_count += 1
        
        # DEBUG: 详细的 tick 信息（仅开发环境）
        self.log.debug(
            "tick_received",
            symbol=str(tick.instrument_id),
            bid=str(tick.bid_price),
            ask=str(tick.ask_price),
            bid_size=str(tick.bid_size),
            ask_size=str(tick.ask_size),
        )
        
        # 计算信号
        try:
            strength = self.calculate_signal_strength(tick)
            direction = self.calculate_signal_direction(tick)
            
            # DEBUG: 信号计算结果
            self.log.debug(
                "signal_calculated",
                symbol=str(tick.instrument_id),
                strength=f"{strength:.4f}",
                direction=direction,
            )
            
            # 如果信号强度超过阈值
            if strength >= float(self.threshold):
                self._on_signal_triggered(tick, direction, strength)
                
        except Exception as e:
            # ERROR: 记录异常（包含堆栈）
            self.log.error(
                "tick_processing_failed",
                symbol=str(tick.instrument_id),
                error=str(e),
                exc_info=True,
            )
    
    def _on_signal_triggered(
        self,
        tick: QuoteTick,
        direction: str,
        strength: float,
    ) -> None:
        """信号触发"""
        self._signal_count += 1
        
        # 获取 LLM 因子
        symbol = self._convert_instrument_to_symbol(tick.instrument_id)
        llm_factor = self.get_effective_llm_factor(symbol)
        
        # INFO: 记录信号生成
        self.log.info(
            "signal_generated",
            signal_id=f"SIG-{self._signal_count:04d}",
            symbol=symbol,
            direction=direction,
            strength=f"{strength:.4f}",
            llm_factor=f"{llm_factor:.4f}",
            threshold=str(self.threshold),
        )
        
        # 计算调整后的仓位
        base_size = Decimal("0.01")
        adjusted_size = float(base_size) * strength * llm_factor
        
        # WARNING: 如果调整后仓位太小
        if adjusted_size < 0.001:
            self.log.warning(
                "signal_size_too_small",
                signal_id=f"SIG-{self._signal_count:04d}",
                adjusted_size=f"{adjusted_size:.6f}",
                min_size=0.001,
                action="skipped",
            )
            return
        
        # 提交订单
        self._submit_order(tick, direction, Decimal(str(adjusted_size)))
    
    def _submit_order(
        self,
        tick: QuoteTick,
        direction: str,
        size: Decimal,
    ) -> None:
        """提交订单"""
        self._order_count += 1
        
        # 确定订单方向
        side = OrderSide.BUY if direction == "long" else OrderSide.SELL
        
        # INFO: 记录订单提交前
        self.log.info(
            "order_submitting",
            order_id=f"ORD-{self._order_count:04d}",
            symbol=str(tick.instrument_id),
            side=str(side),
            size=str(size),
            current_bid=str(tick.bid_price),
            current_ask=str(tick.ask_price),
        )
        
        try:
            # 创建市价单
            order = self.order_factory.market(
                instrument_id=tick.instrument_id,
                order_side=side,
                quantity=size,
            )
            
            # 提交订单
            self.submit_order(order)
            
            # INFO: 订单提交成功
            self.log.info(
                "order_submitted",
                order_id=str(order.client_order_id),
                venue_order_id=str(order.venue_order_id) if order.venue_order_id else None,
                symbol=str(tick.instrument_id),
                side=str(side),
                quantity=str(size),
            )
            
        except Exception as e:
            # ERROR: 订单提交失败
            self.log.error(
                "order_submission_failed",
                order_id=f"ORD-{self._order_count:04d}",
                symbol=str(tick.instrument_id),
                error=str(e),
                exc_info=True,
            )
    
    def on_order_filled(self, event) -> None:
        """订单成交"""
        # INFO: 记录订单成交（审计日志）
        self.log.info(
            "order_filled",
            order_id=str(event.client_order_id),
            venue_order_id=str(event.venue_order_id),
            symbol=str(event.instrument_id),
            side=str(event.order_side),
            fill_price=str(event.last_px),
            fill_qty=str(event.last_qty),
            commission=str(event.commission),
            liquidity_side=str(event.liquidity_side),
            ts_event=event.ts_event,
        )
    
    def on_llm_weight_updated(
        self,
        symbol: str,
        score: float,
        confidence: float,
        metadata: dict,
    ) -> None:
        """LLM 权重更新"""
        # INFO: 记录 LLM 权重更新
        self.log.info(
            "llm_weight_updated",
            symbol=symbol,
            score=f"{score:.4f}",
            confidence=f"{confidence:.4f}",
            horizon=metadata.get("horizon"),
            model=metadata.get("model_used"),
            key_drivers=metadata.get("key_drivers", [])[:3],
        )
        
        # WARNING: 如果 LLM 信号与当前持仓冲突
        if confidence > 0.8:
            if score < -0.5 and self._position_side == "long":
                self.log.warning(
                    "llm_position_conflict",
                    symbol=symbol,
                    llm_signal="strongly_bearish",
                    current_position="long",
                    llm_score=f"{score:.4f}",
                    confidence=f"{confidence:.4f}",
                    recommendation="consider_closing",
                )
            elif score > 0.5 and self._position_side == "short":
                self.log.warning(
                    "llm_position_conflict",
                    symbol=symbol,
                    llm_signal="strongly_bullish",
                    current_position="short",
                    llm_score=f"{score:.4f}",
                    confidence=f"{confidence:.4f}",
                    recommendation="consider_closing",
                )
    
    def calculate_signal_strength(self, tick: QuoteTick) -> float:
        """计算信号强度"""
        # 简单示例：基于买卖价差
        spread = float(tick.ask_price - tick.bid_price)
        mid_price = float((tick.bid_price + tick.ask_price) / 2)
        
        if mid_price == 0:
            return 0.0
        
        spread_pct = spread / mid_price
        
        # 价差越小，信号越强
        strength = max(0.0, min(1.0, 1.0 - spread_pct * 100))
        
        return strength
    
    def calculate_signal_direction(self, tick: QuoteTick) -> str:
        """计算信号方向"""
        # 简单示例：随机方向（实际应该基于技术指标）
        import random
        return random.choice(["long", "short", "hold"])
    
    def _convert_instrument_to_symbol(self, instrument_id: InstrumentId) -> str:
        """转换 InstrumentId 到 symbol"""
        symbol_str = instrument_id.symbol.value
        if "USDT" in symbol_str:
            base = symbol_str.replace("USDT", "")
            return f"{base}-USDT"
        return symbol_str


# 使用示例
if __name__ == "__main__":
    import asyncio
    from nautilus_trader.config import TradingNodeConfig
    from nautilus_trader.live.node import TradingNode
    from nautilus_trader.model.identifiers import TraderId
    
    async def main():
        # 配置策略
        config = LoggingExampleConfig(
            instrument_id="BTCUSDT.BINANCE",
            threshold=Decimal("0.6"),
            enable_llm=True,
        )
        
        # 创建交易节点
        node_config = TradingNodeConfig(
            trader_id=TraderId("LOGGER-001"),
            strategies=[config],
        )
        
        node = TradingNode(config=node_config)
        
        try:
            await node.start()
            
            print("策略运行中，查看日志输出...")
            print("按 Ctrl+C 停止")
            
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n正在停止...")
        finally:
            await node.stop()
    
    asyncio.run(main())
