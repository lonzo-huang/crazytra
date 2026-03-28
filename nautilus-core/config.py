"""
Nautilus Trader 配置
遵循 SYSTEM_SPEC.md 第 13 章规范
"""
from decimal import Decimal
from pathlib import Path

from nautilus_trader.config import (
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    CacheConfig,
    DataEngineConfig,
    ExecEngineConfig,
    ImportableStrategyConfig,
    LoggingConfig,
    RiskEngineConfig,
    StreamingConfig,
)
from nautilus_trader.model.identifiers import TraderId, Venue


# 基础配置
TRADER_ID = TraderId("MIRRORQUANT-001")
REDIS_URL = "redis://localhost:6379"
REDIS_DB = 0

# 日志配置
LOGGING_CONFIG = LoggingConfig(
    log_level="INFO",
    log_level_file="DEBUG",
    log_directory=Path("logs"),
    log_file_format="json",
    log_colors=True,
)

# 缓存配置
CACHE_CONFIG = CacheConfig(
    database_type="redis",
    encoding="msgpack",
    timestamps_as_iso8601=True,
    buffer_interval_ms=100,
)

# 数据引擎配置
DATA_ENGINE_CONFIG = DataEngineConfig(
    time_bars_build_with_no_updates=False,
    time_bars_timestamp_on_close=True,
    validate_data_sequence=True,
)

# 风控引擎配置
RISK_ENGINE_CONFIG = RiskEngineConfig(
    bypass=False,  # 不绕过风控
    max_order_submit_rate="100/00:00:01",  # 每秒最多 100 单
    max_order_modify_rate="100/00:00:01",
    max_notional_per_order={
        "BTC/USDT.BINANCE": Decimal("50000"),  # BTC 单笔最大 5 万 USDT
        "ETH/USDT.BINANCE": Decimal("30000"),  # ETH 单笔最大 3 万 USDT
    },
)

# 执行引擎配置
EXEC_ENGINE_CONFIG = ExecEngineConfig(
    load_cache=True,
    allow_cash_positions=True,
)

# Binance 场地配置（回测用）
BINANCE_VENUE_CONFIG = BacktestVenueConfig(
    name="BINANCE",
    oms_type="NETTING",
    account_type="CASH",
    base_currency="USDT",
    starting_balances=["100000 USDT"],
    book_type="L2_MBP",  # Level 2 Market By Price
    routing=False,
    frozen_account=False,
    bar_execution=True,
    reject_stop_orders=False,
    support_gtd_orders=True,
    support_contingent_orders=True,
)

# Polymarket 场地配置（回测用）
POLYMARKET_VENUE_CONFIG = BacktestVenueConfig(
    name="POLYMARKET",
    oms_type="NETTING",
    account_type="CASH",
    base_currency="USDC",
    starting_balances=["100000 USDC"],
    book_type="L2_MBP",
    routing=False,
    frozen_account=False,
    bar_execution=True,
    reject_stop_orders=True,  # Polymarket 不支持止损单
    support_gtd_orders=False,
    support_contingent_orders=False,
)

# 回测引擎配置
def get_backtest_config(
    strategy_configs: list[ImportableStrategyConfig],
    data_path: Path,
    start: str,
    end: str,
) -> BacktestRunConfig:
    """
    创建回测配置
    
    Args:
        strategy_configs: 策略配置列表
        data_path: 数据文件路径
        start: 开始时间 (ISO 8601)
        end: 结束时间 (ISO 8601)
    """
    return BacktestRunConfig(
        engine=BacktestEngineConfig(
            trader_id=TRADER_ID,
            logging=LOGGING_CONFIG,
            cache=CACHE_CONFIG,
            data_engine=DATA_ENGINE_CONFIG,
            risk_engine=RISK_ENGINE_CONFIG,
            exec_engine=EXEC_ENGINE_CONFIG,
            streaming=StreamingConfig(
                catalog_path=str(data_path),
                fs_protocol="file",
                flush_interval_ms=1000,
            ),
        ),
        venues=[BINANCE_VENUE_CONFIG, POLYMARKET_VENUE_CONFIG],
        data=[],  # 数据配置在运行时动态添加
        strategies=strategy_configs,
    )


# 实盘配置环境变量映射
LIVE_CONFIG_ENV_VARS = {
    "BINANCE_API_KEY": "binance_api_key",
    "BINANCE_SECRET": "binance_api_secret",
    "BINANCE_TESTNET": "binance_testnet",
    "POLYMARKET_API_KEY": "polymarket_api_key",
    "POLYMARKET_WALLET_ADDRESS": "polymarket_wallet_address",
    "TRADING_MODE": "trading_mode",  # paper / live
}
