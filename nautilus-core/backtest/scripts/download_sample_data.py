"""
下载示例历史数据用于回测

支持从多个来源下载数据：
- Binance（通过 ccxt）
- 本地 CSV 文件
- 模拟数据生成
"""

import argparse
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd

from config.logging_config import get_logger

log = get_logger("data_download")


def download_binance_data(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    interval: str = "1m",
) -> pd.DataFrame:
    """
    从 Binance 下载历史数据
    
    Args:
        symbol: 交易对，如 'BTCUSDT'
        start_date: 开始日期
        end_date: 结束日期
        interval: K线间隔（1m, 5m, 1h, 1d）
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    try:
        import ccxt
    except ImportError:
        log.error("ccxt_not_installed", message="Please install: pip install ccxt")
        raise
    
    log.info(
        "downloading_binance_data",
        symbol=symbol,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        interval=interval,
    )
    
    # 创建 Binance 客户端
    exchange = ccxt.binance({
        'enableRateLimit': True,
    })
    
    # 转换时间为毫秒
    since = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)
    
    # 下载数据
    all_ohlcv = []
    current = since
    
    while current < end_ms:
        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol,
                timeframe=interval,
                since=current,
                limit=1000,
            )
            
            if not ohlcv:
                break
            
            all_ohlcv.extend(ohlcv)
            current = ohlcv[-1][0] + 1
            
            log.debug(
                "batch_downloaded",
                count=len(ohlcv),
                last_timestamp=datetime.fromtimestamp(ohlcv[-1][0] / 1000),
            )
            
        except Exception as e:
            log.error("download_error", error=str(e))
            break
    
    # 转换为 DataFrame
    df = pd.DataFrame(
        all_ohlcv,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'],
    )
    
    log.info("download_completed", rows=len(df))
    
    return df


def convert_to_quote_ticks(
    df: pd.DataFrame,
    instrument_id: str,
    spread_bps: float = 1.0,
) -> pd.DataFrame:
    """
    将 OHLCV 数据转换为 QuoteTick 格式
    
    Args:
        df: OHLCV DataFrame
        instrument_id: 工具 ID，如 'BTCUSDT.BINANCE'
        spread_bps: 买卖价差（基点）
    
    Returns:
        QuoteTick DataFrame
    """
    log.info("converting_to_quote_ticks", rows=len(df))
    
    # 计算买卖价
    mid_price = (df['high'] + df['low']) / 2
    spread = mid_price * (spread_bps / 10000)
    
    quote_ticks = pd.DataFrame({
        'timestamp': pd.to_datetime(df['timestamp'], unit='ms').astype('int64'),
        'instrument_id': instrument_id,
        'bid_price': mid_price - spread / 2,
        'ask_price': mid_price + spread / 2,
        'bid_size': df['volume'] / 2,
        'ask_size': df['volume'] / 2,
    })
    
    log.info("conversion_completed", rows=len(quote_ticks))
    
    return quote_ticks


def generate_sample_data(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    interval_seconds: int = 60,
) -> pd.DataFrame:
    """
    生成模拟数据（用于测试）
    
    Args:
        symbol: 交易对
        start_date: 开始日期
        end_date: 结束日期
        interval_seconds: 数据间隔（秒）
    
    Returns:
        QuoteTick DataFrame
    """
    import numpy as np
    
    log.info(
        "generating_sample_data",
        symbol=symbol,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
    )
    
    # 生成时间序列
    timestamps = pd.date_range(
        start=start_date,
        end=end_date,
        freq=f'{interval_seconds}S',
    )
    
    # 生成价格（随机游走）
    np.random.seed(42)
    returns = np.random.normal(0, 0.001, len(timestamps))
    prices = 50000 * np.exp(np.cumsum(returns))  # 从 50000 开始
    
    # 生成买卖价
    spread = prices * 0.0001  # 1 bps spread
    
    df = pd.DataFrame({
        'timestamp': timestamps.astype('int64'),
        'instrument_id': f'{symbol}.SIMULATED',
        'bid_price': prices - spread / 2,
        'ask_price': prices + spread / 2,
        'bid_size': np.random.uniform(0.1, 10.0, len(timestamps)),
        'ask_size': np.random.uniform(0.1, 10.0, len(timestamps)),
    })
    
    log.info("sample_data_generated", rows=len(df))
    
    return df


def save_to_catalog(df: pd.DataFrame, catalog_path: str):
    """
    保存数据到 Nautilus catalog
    
    Args:
        df: QuoteTick DataFrame
        catalog_path: Catalog 路径
    """
    from nautilus_trader.model.data import QuoteTick
    from nautilus_trader.persistence.catalog import ParquetDataCatalog
    
    log.info("saving_to_catalog", catalog_path=catalog_path, rows=len(df))
    
    # 创建 catalog
    catalog = ParquetDataCatalog(catalog_path)
    
    # 保存数据
    # 注意：这里简化处理，实际需要转换为 Nautilus QuoteTick 对象
    output_path = Path(catalog_path) / "quote_ticks.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_parquet(output_path, index=False)
    
    log.info("data_saved", output_path=str(output_path))


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Download historical data for backtesting')
    parser.add_argument('--symbol', type=str, default='BTCUSDT', help='Trading symbol')
    parser.add_argument('--days', type=int, default=30, help='Number of days to download')
    parser.add_argument('--interval', type=str, default='1m', help='Data interval (1m, 5m, 1h, 1d)')
    parser.add_argument('--source', type=str, default='binance', choices=['binance', 'sample'], help='Data source')
    parser.add_argument('--output', type=str, default='./backtest/data/catalog', help='Output catalog path')
    
    args = parser.parse_args()
    
    # 计算日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    log.info(
        "download_started",
        symbol=args.symbol,
        source=args.source,
        days=args.days,
    )
    
    try:
        if args.source == 'binance':
            # 从 Binance 下载
            ohlcv_df = download_binance_data(
                symbol=args.symbol,
                start_date=start_date,
                end_date=end_date,
                interval=args.interval,
            )
            
            # 转换为 QuoteTick
            instrument_id = f"{args.symbol}.BINANCE"
            quote_ticks = convert_to_quote_ticks(ohlcv_df, instrument_id)
            
        elif args.source == 'sample':
            # 生成模拟数据
            quote_ticks = generate_sample_data(
                symbol=args.symbol,
                start_date=start_date,
                end_date=end_date,
            )
        
        # 保存到 catalog
        save_to_catalog(quote_ticks, args.output)
        
        print(f"\n✅ Downloaded {len(quote_ticks)} ticks")
        print(f"📁 Saved to: {args.output}")
        print(f"📊 Date range: {start_date.date()} to {end_date.date()}")
        
        return 0
        
    except Exception as e:
        log.error("download_failed", error=str(e), exc_info=True)
        print(f"\n❌ Download failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
