"""
Nautilus Trader 回测运行脚本

支持从配置文件运行回测，生成详细的性能报告。
"""

import argparse
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.engine import BacktestEngineConfig
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.backtest.modules import FXRolloverInterestModule
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from config.logging_config import configure_logging, get_logger


def load_config(config_path: str) -> dict:
    """加载回测配置"""
    import yaml
    
    with open(config_path) as f:
        return yaml.safe_load(f)


def setup_backtest_engine(config: dict) -> BacktestEngine:
    """设置回测引擎"""
    
    # 配置日志
    log = configure_logging(
        log_level=config.get('logging', {}).get('level', 'INFO'),
        json_format=False,
    )
    
    log.info("backtest_setup_started", config_path=config.get('_path'))
    
    # 创建引擎配置
    engine_config = BacktestEngineConfig(
        logging=LoggingConfig(
            log_level=config.get('logging', {}).get('level', 'INFO'),
        ),
    )
    
    # 创建引擎
    engine = BacktestEngine(config=engine_config)
    
    # 添加 venue
    venue = Venue(config['execution']['venue'])
    
    engine.add_venue(
        venue=venue,
        oms_type=OmsType[config['execution'].get('oms_type', 'NETTING')],
        account_type=AccountType[config['execution']['account_type']],
        base_currency=config['execution']['base_currency'],
        starting_balances=[
            Money(
                config['execution']['starting_balance'],
                USD,  # 简化处理，实际应该从配置读取
            )
        ],
    )
    
    log.info(
        "venue_added",
        venue=str(venue),
        account_type=config['execution']['account_type'],
        starting_balance=config['execution']['starting_balance'],
    )
    
    return engine


def load_data(engine: BacktestEngine, config: dict):
    """加载历史数据"""
    log = get_logger("backtest.data")
    
    catalog_path = config['data']['catalog_path']
    log.info("loading_data", catalog_path=catalog_path)
    
    # 创建数据目录
    catalog = ParquetDataCatalog(catalog_path)
    
    # 加载工具
    instruments = catalog.instruments()
    log.info("instruments_loaded", count=len(instruments))
    
    for instrument in instruments:
        engine.add_instrument(instrument)
        log.debug("instrument_added", instrument_id=str(instrument.id))
    
    # 加载 QuoteTick 数据
    for instrument_id in config['data']['instruments']:
        try:
            quote_ticks = catalog.quote_ticks(instrument_ids=[instrument_id])
            
            if quote_ticks:
                engine.add_data(quote_ticks)
                log.info(
                    "quote_ticks_loaded",
                    instrument_id=instrument_id,
                    count=len(quote_ticks),
                )
            else:
                log.warning("no_quote_ticks_found", instrument_id=instrument_id)
                
        except Exception as e:
            log.error(
                "data_load_failed",
                instrument_id=instrument_id,
                error=str(e),
                exc_info=True,
            )


def add_strategies(engine: BacktestEngine, config: dict):
    """添加策略"""
    log = get_logger("backtest.strategy")
    
    for strategy_config in config['strategies']:
        # 动态导入策略类
        module_path, class_name = strategy_config['strategy_path'].rsplit('.', 1)
        module = __import__(module_path, fromlist=[class_name])
        strategy_class = getattr(module, class_name)
        
        # 创建策略配置
        config_class_name = class_name.replace('Strategy', 'Config')
        config_class = getattr(module, config_class_name)
        
        strategy_cfg = config_class(**strategy_config['config'])
        
        # 添加策略
        strategy = strategy_class(config=strategy_cfg)
        engine.add_strategy(strategy)
        
        log.info(
            "strategy_added",
            strategy_class=class_name,
            config=strategy_config['config'],
        )


def run_backtest(config_path: str) -> dict:
    """运行回测"""
    log = get_logger("backtest")
    
    # 加载配置
    config = load_config(config_path)
    config['_path'] = config_path
    
    log.info("backtest_started", config_path=config_path)
    
    # 设置引擎
    engine = setup_backtest_engine(config)
    
    # 加载数据
    load_data(engine, config)
    
    # 添加策略
    add_strategies(engine, config)
    
    # 运行回测
    start_time = datetime.fromisoformat(config['backtest']['start'])
    end_time = datetime.fromisoformat(config['backtest']['end'])
    
    log.info(
        "backtest_running",
        start=config['backtest']['start'],
        end=config['backtest']['end'],
    )
    
    engine.run(
        start=start_time,
        end=end_time,
    )
    
    log.info("backtest_completed")
    
    # 生成报告
    results = generate_reports(engine, config)
    
    return results


def generate_reports(engine: BacktestEngine, config: dict) -> dict:
    """生成回测报告"""
    log = get_logger("backtest.report")
    
    log.info("generating_reports")
    
    # 账户报告
    account_report = engine.trader.generate_account_report(Venue(config['execution']['venue']))
    
    # 订单报告
    order_fills = engine.trader.generate_order_fills_report()
    
    # 持仓报告
    positions = engine.trader.generate_positions_report()
    
    # 汇总结果
    results = {
        'config': {
            'start': config['backtest']['start'],
            'end': config['backtest']['end'],
            'strategies': [s['strategy_path'] for s in config['strategies']],
        },
        'performance': {
            'total_pnl': str(account_report.total_pnl()) if hasattr(account_report, 'total_pnl') else 'N/A',
            'total_trades': len(order_fills),
            'total_positions': len(positions),
        },
        'account': str(account_report),
        'fills': str(order_fills),
        'positions': str(positions),
    }
    
    # 打印报告
    print("\n" + "=" * 80)
    print("BACKTEST RESULTS")
    print("=" * 80)
    print(f"\nPeriod: {config['backtest']['start']} to {config['backtest']['end']}")
    print(f"Strategies: {', '.join(results['config']['strategies'])}")
    print(f"\nTotal Trades: {results['performance']['total_trades']}")
    print(f"Total Positions: {results['performance']['total_positions']}")
    print(f"Total PnL: {results['performance']['total_pnl']}")
    print("\n" + "=" * 80)
    print("\nAccount Report:")
    print(results['account'])
    print("\n" + "=" * 80)
    
    # 保存结果
    if config['backtest'].get('save_results', True):
        output_dir = Path(config.get('output_dir', './backtest_results'))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"backtest_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        log.info("results_saved", output_file=str(output_file))
        print(f"\nResults saved to: {output_file}")
    
    return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Run Nautilus Trader backtest')
    parser.add_argument(
        '--config',
        type=str,
        required=True,
        help='Path to backtest configuration file (YAML)',
    )
    
    args = parser.parse_args()
    
    try:
        results = run_backtest(args.config)
        print("\n✅ Backtest completed successfully!")
        return 0
    except Exception as e:
        log = get_logger("backtest")
        log.error("backtest_failed", error=str(e), exc_info=True)
        print(f"\n❌ Backtest failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
