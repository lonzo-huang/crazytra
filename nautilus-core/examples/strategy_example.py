"""
策略使用示例

展示如何配置和运行 CrazytraStrategy 策略。
"""

import asyncio
from decimal import Decimal

from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.identifiers import TraderId

from strategies.ma_cross_llm import MACrossLLMConfig


async def main():
    """主函数"""
    
    # 1. 创建策略配置
    strategy_config = MACrossLLMConfig(
        # 基础配置
        instrument_id="BTCUSDT.BINANCE",
        
        # 均线参数
        fast_period=10,
        slow_period=30,
        trade_size=Decimal("0.01"),
        
        # LLM 配置
        enable_llm=True,
        llm_weight_factor=0.5,  # LLM 权重影响系数
        min_confidence=0.3,     # 最小置信度阈值
    )
    
    # 2. 创建交易节点配置
    node_config = TradingNodeConfig(
        trader_id=TraderId("TRADER-001"),
        logging=LoggingConfig(log_level="INFO"),
        
        # 策略列表
        strategies=[strategy_config],
        
        # 数据客户端（需要配置 Binance）
        data_clients={
            "BINANCE": {
                "api_key": "your_api_key",
                "api_secret": "your_api_secret",
            },
        },
        
        # 执行客户端（纸面交易）
        exec_clients={
            "BINANCE": {
                "api_key": "your_api_key",
                "api_secret": "your_api_secret",
                "paper_trading": True,
            },
        },
    )
    
    # 3. 创建并启动交易节点
    node = TradingNode(config=node_config)
    
    try:
        await node.start()
        
        print("策略运行中...")
        print("按 Ctrl+C 停止")
        
        # 保持运行
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n正在停止...")
    finally:
        await node.stop()


if __name__ == "__main__":
    asyncio.run(main())
