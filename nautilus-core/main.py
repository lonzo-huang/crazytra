"""
Nautilus Trader 主入口
整合 Nautilus 与 MirrorQuant 架构

运行模式：
1. 回测模式：python main.py --mode backtest --config backtest_config.json
2. 实盘模式：python main.py --mode live --config live_config.json
3. 纸面交易：python main.py --mode paper --config paper_config.json
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from nautilus_trader.live.node import TradingNode
from nautilus_trader.config import TradingNodeConfig, LoggingConfig
from nautilus_trader.model.identifiers import TraderId

from nautilus_core.actors.redis_bridge import RedisBridgeActor
from nautilus_core.actors.llm_weight_actor import LLMWeightActor
from nautilus_core.strategies.ma_cross_llm import MACrossLLMStrategy, MACrossLLMConfig
from nautilus_core.config import (
    TRADER_ID,
    LOGGING_CONFIG,
    CACHE_CONFIG,
    DATA_ENGINE_CONFIG,
    RISK_ENGINE_CONFIG,
    EXEC_ENGINE_CONFIG,
)


# 加载环境变量
load_dotenv()


def create_live_node_config() -> TradingNodeConfig:
    """
    创建实盘/纸面交易节点配置
    """
    # 从环境变量读取配置
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    trading_mode = os.getenv("TRADING_MODE", "paper")
    
    # 数据客户端配置
    data_clients = {}
    
    # Binance 配置
    binance_api_key = os.getenv("BINANCE_API_KEY")
    binance_secret = os.getenv("BINANCE_SECRET")
    if binance_api_key and binance_secret:
        data_clients["BINANCE"] = {
            "api_key": binance_api_key,
            "api_secret": binance_secret,
            "testnet": os.getenv("BINANCE_TESTNET", "false").lower() == "true",
        }
    
    # 执行客户端配置（仅实盘模式）
    exec_clients = {}
    if trading_mode == "live":
        if binance_api_key and binance_secret:
            exec_clients["BINANCE"] = {
                "api_key": binance_api_key,
                "api_secret": binance_secret,
                "testnet": os.getenv("BINANCE_TESTNET", "false").lower() == "true",
            }
    
    # 策略配置
    strategies = [
        MACrossLLMConfig(
            strategy_id="ma_cross_llm_btc",
            instrument_id="BTCUSDT.BINANCE",
            fast_period=10,
            slow_period=30,
            trade_size="0.01",
            enable_llm=True,
            llm_weight_factor=0.5,
        ),
    ]
    
    # Actor 配置
    actors = [
        {
            "actor_class": "nautilus_core.actors.redis_bridge:RedisBridgeActor",
            "config": {
                "redis_url": redis_url,
                "maxlen": 50000,
            },
        },
        {
            "actor_class": "nautilus_core.actors.llm_weight_actor:LLMWeightActor",
            "config": {
                "redis_url": redis_url,
                "half_life_s": 1800,  # 30分钟衰减半衰期
            },
        },
    ]
    
    # 构建节点配置
    config = TradingNodeConfig(
        trader_id=TRADER_ID,
        logging=LOGGING_CONFIG,
        cache=CACHE_CONFIG,
        data_engine=DATA_ENGINE_CONFIG,
        risk_engine=RISK_ENGINE_CONFIG,
        exec_engine=EXEC_ENGINE_CONFIG,
        data_clients=data_clients,
        exec_clients=exec_clients,
        strategies=strategies,
        actors=actors,
        timeout_connection=30.0,
        timeout_reconciliation=10.0,
        timeout_portfolio=10.0,
        timeout_disconnection=10.0,
    )
    
    return config


async def run_live_node():
    """运行实盘/纸面交易节点"""
    config = create_live_node_config()
    
    # 创建交易节点
    node = TradingNode(config=config)
    
    try:
        # 构建节点
        node.build()
        
        # 启动节点
        await node.start()
        
        print("=" * 60)
        print("Nautilus Trading Node Started")
        print("=" * 60)
        print(f"Trader ID: {config.trader_id}")
        print(f"Trading Mode: {os.getenv('TRADING_MODE', 'paper')}")
        print(f"Redis URL: {os.getenv('REDIS_URL', 'redis://localhost:6379')}")
        print("=" * 60)
        print("\nPress Ctrl+C to stop...\n")
        
        # 保持运行
        while node.is_running:
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    
    finally:
        # 停止节点
        await node.stop()
        
        # 释放资源
        await node.dispose()
        
        print("Node stopped successfully")


async def run_backtest():
    """运行回测"""
    from nautilus_trader.backtest.node import BacktestNode
    from nautilus_core.config import get_backtest_config
    
    # 回测配置
    strategy_configs = [
        MACrossLLMConfig(
            strategy_id="ma_cross_llm_btc_backtest",
            instrument_id="BTCUSDT.BINANCE",
            fast_period=10,
            slow_period=30,
            trade_size="0.01",
            enable_llm=False,  # 回测时禁用 LLM（除非有历史 LLM 数据）
            llm_weight_factor=0.0,
        ),
    ]
    
    # 数据路径（需要准备 Parquet 格式的历史数据）
    data_path = Path(os.getenv("BACKTEST_DATA_PATH", "./data"))
    
    # 回测时间范围
    start = os.getenv("BACKTEST_START", "2024-01-01")
    end = os.getenv("BACKTEST_END", "2024-12-31")
    
    config = get_backtest_config(
        strategy_configs=strategy_configs,
        data_path=data_path,
        start=start,
        end=end,
    )
    
    # 创建回测节点
    node = BacktestNode(config=config.engine)
    
    # 添加策略
    for strategy_config in strategy_configs:
        node.add_strategy(strategy_config)
    
    # 运行回测
    node.run()
    
    # 输出结果
    print("\n" + "=" * 60)
    print("Backtest Results")
    print("=" * 60)
    
    # 获取绩效报告
    # TODO: 实现绩效指标输出
    
    print("=" * 60)


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Nautilus Trader - MirrorQuant Integration")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["live", "paper", "backtest"],
        default="paper",
        help="Trading mode: live, paper, or backtest",
    )
    
    args = parser.parse_args()
    
    # 设置交易模式环境变量
    if args.mode in ["live", "paper"]:
        os.environ["TRADING_MODE"] = args.mode
        asyncio.run(run_live_node())
    elif args.mode == "backtest":
        asyncio.run(run_backtest())


if __name__ == "__main__":
    main()
