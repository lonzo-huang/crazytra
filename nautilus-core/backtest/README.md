# Nautilus Trader 回测指南

本指南介绍如何使用 Nautilus Trader 进行策略回测。

## 回测优势

- ✅ **回测=实盘**：完全相同的策略代码
- ✅ **事件驱动**：真实的订单执行模拟
- ✅ **高性能**：Rust 核心，快速回测
- ✅ **准确性**：考虑滑点、手续费、延迟

## 快速开始

### 1. 准备历史数据

Nautilus 支持多种数据格式，推荐使用 Parquet 格式。

#### 数据格式要求

```python
# QuoteTick 数据（推荐）
columns = [
    'timestamp',      # int64, 纳秒时间戳
    'instrument_id',  # str, 如 'BTCUSDT.BINANCE'
    'bid_price',      # float64
    'ask_price',      # float64
    'bid_size',       # float64
    'ask_size',       # float64
]

# TradeTick 数据（可选）
columns = [
    'timestamp',      # int64, 纳秒时间戳
    'instrument_id',  # str
    'price',          # float64
    'size',           # float64
    'aggressor_side', # str, 'BUY' or 'SELL'
]
```

### 2. 下载示例数据

```bash
cd nautilus-core/backtest
python scripts/download_sample_data.py --symbol BTCUSDT --days 30
```

### 3. 运行回测

```bash
cd nautilus-core
python backtest/run_backtest.py --config backtest/configs/ma_cross_example.yaml
```

## 数据准备

### 方法 1：从 CSV 转换

```python
import pandas as pd
from nautilus_trader.persistence.catalog import ParquetDataCatalog

# 读取 CSV
df = pd.read_csv('historical_data.csv')

# 转换时间戳为纳秒
df['timestamp'] = pd.to_datetime(df['timestamp']).astype('int64')

# 保存为 Parquet
catalog = ParquetDataCatalog('./catalog')
catalog.write_data([df], data_cls=QuoteTick)
```

### 方法 2：从交易所下载

```python
from nautilus_trader.adapters.binance import BinanceDataClient
from datetime import datetime, timedelta

# 创建数据客户端
client = BinanceDataClient()

# 下载历史数据
start = datetime.now() - timedelta(days=30)
end = datetime.now()

data = await client.request_quote_ticks(
    instrument_id=InstrumentId.from_str('BTCUSDT.BINANCE'),
    start=start,
    end=end,
)

# 保存到 catalog
catalog.write_data(data)
```

### 方法 3：使用提供的脚本

```bash
# 下载 Binance 数据
python scripts/download_binance_data.py \
    --symbol BTCUSDT \
    --start 2024-01-01 \
    --end 2024-01-31 \
    --interval 1m

# 下载 Polymarket 数据
python scripts/download_polymarket_data.py \
    --market "will-btc-hit-100k" \
    --days 30
```

## 回测配置

### 基础配置

```yaml
# backtest/configs/basic_backtest.yaml

# 回测引擎配置
backtest:
  start: "2024-01-01T00:00:00Z"
  end: "2024-01-31T23:59:59Z"
  
# 数据配置
data:
  catalog_path: "./catalog"
  instruments:
    - BTCUSDT.BINANCE
  
# 策略配置
strategies:
  - strategy_path: "strategies.ma_cross_llm.MACrossLLMStrategy"
    config:
      instrument_id: "BTCUSDT.BINANCE"
      fast_period: 10
      slow_period: 30
      trade_size: 0.01
      enable_llm: false  # 回测时禁用 LLM

# 执行配置
execution:
  venue: BINANCE
  account_type: MARGIN
  base_currency: USDT
  starting_balance: 10000.0
  
# 风险配置
risk:
  max_order_size: 1.0
  max_notional_per_order: 10000.0

# 手续费配置
fees:
  maker_fee: 0.001  # 0.1%
  taker_fee: 0.001  # 0.1%
```

### 高级配置

```yaml
# backtest/configs/advanced_backtest.yaml

backtest:
  start: "2024-01-01T00:00:00Z"
  end: "2024-01-31T23:59:59Z"
  run_analysis: true
  
data:
  catalog_path: "./catalog"
  instruments:
    - BTCUSDT.BINANCE
    - ETHUSDT.BINANCE
  
strategies:
  # 多策略回测
  - strategy_path: "strategies.ma_cross_llm.MACrossLLMStrategy"
    config:
      instrument_id: "BTCUSDT.BINANCE"
      fast_period: 10
      slow_period: 30
      trade_size: 0.01
  
  - strategy_path: "strategies.ma_cross_llm.MACrossLLMStrategy"
    config:
      instrument_id: "ETHUSDT.BINANCE"
      fast_period: 20
      slow_period: 50
      trade_size: 0.1

execution:
  venue: BINANCE
  account_type: MARGIN
  base_currency: USDT
  starting_balance: 100000.0
  
  # 滑点模型
  slippage:
    model: "fixed"
    value: 0.0001  # 1 bps
  
  # 延迟模型
  latency:
    model: "fixed"
    value_ms: 10

risk:
  max_order_size: 10.0
  max_notional_per_order: 100000.0
  max_position_size: 50000.0

fees:
  maker_fee: 0.0001  # 0.01%
  taker_fee: 0.001   # 0.1%
```

## 回测脚本

### 基础回测

```python
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.config import BacktestEngineConfig
from nautilus_trader.persistence.catalog import ParquetDataCatalog

from strategies.ma_cross_llm import MACrossLLMConfig

# 创建数据目录
catalog = ParquetDataCatalog('./catalog')

# 加载数据
instruments = catalog.instruments()
quote_ticks = catalog.quote_ticks()

# 配置回测引擎
config = BacktestEngineConfig(
    strategies=[
        MACrossLLMConfig(
            instrument_id="BTCUSDT.BINANCE",
            fast_period=10,
            slow_period=30,
            trade_size=Decimal("0.01"),
            enable_llm=False,
        ),
    ],
)

# 创建回测节点
node = BacktestNode(config=config)

# 添加数据
for instrument in instruments:
    node.add_instrument(instrument)

for tick in quote_ticks:
    node.add_data(tick)

# 运行回测
node.run()

# 获取结果
result = node.trader.generate_account_report()
print(result)
```

### 批量回测（参数优化）

```python
from itertools import product

# 参数网格
fast_periods = [5, 10, 20]
slow_periods = [20, 30, 50]

results = []

for fast, slow in product(fast_periods, slow_periods):
    if fast >= slow:
        continue
    
    config = MACrossLLMConfig(
        instrument_id="BTCUSDT.BINANCE",
        fast_period=fast,
        slow_period=slow,
        trade_size=Decimal("0.01"),
        enable_llm=False,
    )
    
    # 运行回测
    node = BacktestNode(config=config)
    # ... 添加数据 ...
    node.run()
    
    # 记录结果
    stats = node.trader.generate_account_report()
    results.append({
        'fast': fast,
        'slow': slow,
        'total_return': stats.total_return,
        'sharpe_ratio': stats.sharpe_ratio,
        'max_drawdown': stats.max_drawdown,
    })

# 找到最佳参数
best = max(results, key=lambda x: x['sharpe_ratio'])
print(f"Best parameters: fast={best['fast']}, slow={best['slow']}")
```

## 性能指标

### 标准指标

Nautilus 自动计算以下指标：

```python
# 收益指标
- total_return        # 总收益率
- annual_return       # 年化收益率
- monthly_return      # 月度收益率

# 风险指标
- sharpe_ratio        # 夏普比率
- sortino_ratio       # 索提诺比率
- max_drawdown        # 最大回撤
- calmar_ratio        # 卡玛比率

# 交易指标
- total_trades        # 总交易次数
- win_rate            # 胜率
- profit_factor       # 盈亏比
- avg_win             # 平均盈利
- avg_loss            # 平均亏损
```

### 自定义指标

```python
from nautilus_trader.analysis.statistics import PortfolioStatistics

class CustomStatistics(PortfolioStatistics):
    def calculate_custom_metric(self) -> float:
        # 自定义指标计算
        pass

# 使用自定义统计
stats = CustomStatistics(node.trader.portfolio)
custom_value = stats.calculate_custom_metric()
```

## 结果分析

### 生成报告

```python
# 账户报告
account_report = node.trader.generate_account_report()
print(account_report)

# 订单报告
order_report = node.trader.generate_order_report()
print(order_report)

# 持仓报告
position_report = node.trader.generate_position_report()
print(position_report)
```

### 导出结果

```python
import json

# 导出为 JSON
results = {
    'config': config.dict(),
    'stats': account_report.dict(),
    'trades': [trade.dict() for trade in node.trader.trades()],
}

with open('backtest_results.json', 'w') as f:
    json.dump(results, f, indent=2)
```

### 可视化

```python
import matplotlib.pyplot as plt

# 权益曲线
equity = node.trader.portfolio.equity_curve()
plt.plot(equity)
plt.title('Equity Curve')
plt.xlabel('Time')
plt.ylabel('Equity')
plt.savefig('equity_curve.png')

# 回撤曲线
drawdown = node.trader.portfolio.drawdown_curve()
plt.plot(drawdown)
plt.title('Drawdown')
plt.savefig('drawdown.png')
```

## LLM 权重回测

### 准备 LLM 数据

```python
# 生成模拟 LLM 权重数据
import pandas as pd

llm_data = pd.DataFrame({
    'timestamp': timestamps,
    'symbol': ['BTC-USDT'] * len(timestamps),
    'llm_score': [0.3, 0.5, -0.2, ...],  # [-1, 1]
    'confidence': [0.7, 0.8, 0.6, ...],  # [0, 1]
})

llm_data.to_parquet('llm_weights.parquet')
```

### 回测配置

```yaml
strategies:
  - strategy_path: "strategies.ma_cross_llm.MACrossLLMStrategy"
    config:
      instrument_id: "BTCUSDT.BINANCE"
      fast_period: 10
      slow_period: 30
      trade_size: 0.01
      enable_llm: true
      llm_weight_factor: 0.5

# LLM 数据
llm_data:
  path: "llm_weights.parquet"
```

### 对比测试

```python
# 不使用 LLM
config_no_llm = MACrossLLMConfig(enable_llm=False)
result_no_llm = run_backtest(config_no_llm)

# 使用 LLM
config_with_llm = MACrossLLMConfig(enable_llm=True)
result_with_llm = run_backtest(config_with_llm)

# 对比
print(f"Without LLM: Sharpe={result_no_llm.sharpe_ratio:.2f}")
print(f"With LLM: Sharpe={result_with_llm.sharpe_ratio:.2f}")
print(f"Improvement: {(result_with_llm.sharpe_ratio / result_no_llm.sharpe_ratio - 1) * 100:.1f}%")
```

## 常见问题

### 问题：数据加载失败

```
FileNotFoundError: catalog not found
```

**解决方案**：
1. 检查 catalog 路径
2. 确保已下载数据
3. 验证数据格式

### 问题：回测速度慢

**优化方案**：
1. 使用 Parquet 格式（比 CSV 快 10x）
2. 减少数据量（按时间范围筛选）
3. 禁用不必要的日志
4. 使用多进程并行回测

### 问题：结果不准确

**检查清单**：
1. ✅ 数据质量（缺失值、异常值）
2. ✅ 手续费设置
3. ✅ 滑点模型
4. ✅ 前视偏差（look-ahead bias）
5. ✅ 生存偏差（survivorship bias）

## 最佳实践

### DO ✅

1. **使用真实数据**：包含买卖价差
2. **考虑成本**：手续费、滑点
3. **避免过拟合**：使用样本外测试
4. **记录所有参数**：便于复现
5. **多次回测**：不同时间段验证
6. **保守估计**：宁可低估收益

### DON'T ❌

1. **不要使用未来数据**：前视偏差
2. **不要忽略成本**：手续费很重要
3. **不要过度优化**：曲线拟合
4. **不要只看收益**：关注风险指标
5. **不要假设流动性**：大单可能无法成交

## 参考资料

- [Nautilus Trader 文档](https://nautilustrader.io/docs/latest/concepts/backtesting)
- [回测最佳实践](https://www.quantstart.com/articles/Backtesting/)
- [避免回测陷阱](https://www.quantopian.com/posts/common-backtesting-mistakes)
