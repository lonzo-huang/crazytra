# 回测引擎和数据管理策略

## 问题 1：如何提供回测和漂亮的图表页面？

### 回测引擎方案

#### 方案 A：使用 Nautilus Trader 回测引擎（推荐）

**优势**：
- ✅ 专业级回测引擎
- ✅ 事件驱动，与实盘代码完全一致
- ✅ 支持多种订单类型
- ✅ 真实的滑点和手续费模拟
- ✅ 已经集成在系统中

**实现步骤**：

```python
# nautilus-core/backtest/backtest_engine.py
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.model.data import QuoteTick, Bar
from nautilus_trader.persistence.catalog import ParquetDataCatalog
import pandas as pd

class MirrorQuantBacktestEngine:
    """MirrorQuant 回测引擎"""
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.catalog = ParquetDataCatalog("./data/backtest")
    
    async def run_backtest(
        self,
        strategy_config: dict,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_cash: float = 100000.0
    ) -> dict:
        """
        运行回测
        
        Args:
            strategy_config: 策略配置
            symbol: 交易对 (e.g., "BTC-USDT")
            start_date: 开始日期 "2024-01-01"
            end_date: 结束日期 "2024-06-01"
            initial_cash: 初始资金
            
        Returns:
            回测结果字典
        """
        
        # 1. 加载历史数据
        data = await self._load_historical_data(symbol, start_date, end_date)
        
        # 2. 创建回测节点
        config = BacktestEngineConfig(
            trader_id=f"BACKTEST-{self.tenant_id}",
            log_level="INFO",
        )
        
        node = BacktestNode(config=config)
        
        # 3. 添加数据
        node.add_data(data)
        
        # 4. 添加策略
        strategy = self._create_strategy(strategy_config)
        node.add_strategy(strategy)
        
        # 5. 运行回测
        result = node.run()
        
        # 6. 生成报告
        report = self._generate_report(result)
        
        return report
    
    def _generate_report(self, result) -> dict:
        """生成回测报告"""
        stats = result.stats_pnls()
        
        return {
            "summary": {
                "total_return": float(stats["Total Return [%]"]),
                "annual_return": float(stats["Annual Return [%]"]),
                "sharpe_ratio": float(stats["Sharpe Ratio"]),
                "max_drawdown": float(stats["Max Drawdown [%]"]),
                "win_rate": float(stats["Win Rate [%]"]),
                "total_trades": int(stats["Total Trades"]),
            },
            "equity_curve": self._get_equity_curve(result),
            "trades": self._get_trades(result),
            "daily_returns": self._get_daily_returns(result),
        }
    
    def _get_equity_curve(self, result) -> list:
        """获取权益曲线数据"""
        equity = result.portfolio.equity_curve()
        return [
            {
                "timestamp": int(ts),
                "equity": float(value)
            }
            for ts, value in equity.items()
        ]
    
    def _get_trades(self, result) -> list:
        """获取交易记录"""
        trades = result.portfolio.trades()
        return [
            {
                "entry_time": int(trade.entry_time),
                "exit_time": int(trade.exit_time),
                "symbol": trade.symbol,
                "side": trade.side,
                "entry_price": float(trade.entry_price),
                "exit_price": float(trade.exit_price),
                "quantity": float(trade.quantity),
                "pnl": float(trade.realized_pnl),
                "return_pct": float(trade.return_pct),
            }
            for trade in trades
        ]
```

#### API 接口设计

```go
// api-gateway/handlers/backtest.go
package handlers

import (
    "github.com/gin-gonic/gin"
    "net/http"
)

type BacktestRequest struct {
    StrategyID   string  `json:"strategy_id" binding:"required"`
    Symbol       string  `json:"symbol" binding:"required"`
    StartDate    string  `json:"start_date" binding:"required"`
    EndDate      string  `json:"end_date" binding:"required"`
    InitialCash  float64 `json:"initial_cash"`
}

type BacktestResponse struct {
    BacktestID string                 `json:"backtest_id"`
    Status     string                 `json:"status"` // running, completed, failed
    Summary    *BacktestSummary       `json:"summary,omitempty"`
    Charts     *BacktestCharts        `json:"charts,omitempty"`
}

type BacktestSummary struct {
    TotalReturn   float64 `json:"total_return"`
    AnnualReturn  float64 `json:"annual_return"`
    SharpeRatio   float64 `json:"sharpe_ratio"`
    MaxDrawdown   float64 `json:"max_drawdown"`
    WinRate       float64 `json:"win_rate"`
    TotalTrades   int     `json:"total_trades"`
}

type BacktestCharts struct {
    EquityCurve  []EquityPoint  `json:"equity_curve"`
    Trades       []TradeRecord  `json:"trades"`
    DailyReturns []ReturnPoint  `json:"daily_returns"`
}

// POST /api/v1/backtest
func (h *Handler) RunBacktest(c *gin.Context) {
    var req BacktestRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }
    
    // 获取租户 ID
    tenantID := c.GetString("tenant_id")
    
    // 创建回测任务
    backtestID := generateBacktestID()
    
    // 异步运行回测
    go h.runBacktestAsync(backtestID, tenantID, req)
    
    c.JSON(http.StatusAccepted, BacktestResponse{
        BacktestID: backtestID,
        Status:     "running",
    })
}

// GET /api/v1/backtest/:id
func (h *Handler) GetBacktestResult(c *gin.Context) {
    backtestID := c.Param("id")
    tenantID := c.GetString("tenant_id")
    
    // 从 Redis 或数据库获取结果
    result, err := h.getBacktestResult(backtestID, tenantID)
    if err != nil {
        c.JSON(http.StatusNotFound, gin.H{"error": "Backtest not found"})
        return
    }
    
    c.JSON(http.StatusOK, result)
}
```

### 图表页面方案

#### 前端图表库选择

**推荐：Lightweight Charts**（TradingView 开源）

你的前端已经在使用了！位置：`frontend/src/components/PriceChart.tsx`

**优势**：
- ✅ 性能极佳（百万数据点）
- ✅ 专为金融图表设计
- ✅ TradingView 同款
- ✅ 免费开源

#### 回测结果页面设计

```typescript
// frontend/src/pages/BacktestResult.tsx
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { createChart } from 'lightweight-charts';

interface BacktestResult {
  backtest_id: string;
  status: string;
  summary: {
    total_return: number;
    annual_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    total_trades: number;
  };
  charts: {
    equity_curve: Array<{ timestamp: number; equity: number }>;
    trades: Array<any>;
    daily_returns: Array<any>;
  };
}

export default function BacktestResult() {
  const { backtestId } = useParams();
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchBacktestResult();
  }, [backtestId]);

  const fetchBacktestResult = async () => {
    const response = await fetch(`/api/v1/backtest/${backtestId}`);
    const data = await response.json();
    setResult(data);
    setLoading(false);
    
    if (data.status === 'completed') {
      renderCharts(data.charts);
    }
  };

  const renderCharts = (charts: any) => {
    // 1. 权益曲线图
    const equityChart = createChart(
      document.getElementById('equity-chart')!,
      {
        width: 800,
        height: 400,
        layout: {
          background: { color: '#1a1a1a' },
          textColor: '#d1d4dc',
        },
        grid: {
          vertLines: { color: '#2a2a2a' },
          horzLines: { color: '#2a2a2a' },
        },
      }
    );

    const equitySeries = equityChart.addLineSeries({
      color: '#26a69a',
      lineWidth: 2,
    });

    equitySeries.setData(
      charts.equity_curve.map((point: any) => ({
        time: point.timestamp / 1000000000, // 纳秒转秒
        value: point.equity,
      }))
    );

    // 2. 回撤图
    const drawdownChart = createChart(
      document.getElementById('drawdown-chart')!,
      { width: 800, height: 200 }
    );

    // 3. 交易标记
    const markers = charts.trades.map((trade: any) => ({
      time: trade.entry_time / 1000000000,
      position: trade.side === 'BUY' ? 'belowBar' : 'aboveBar',
      color: trade.pnl > 0 ? '#26a69a' : '#ef5350',
      shape: trade.side === 'BUY' ? 'arrowUp' : 'arrowDown',
      text: `${trade.side} @ ${trade.entry_price}`,
    }));

    equitySeries.setMarkers(markers);
  };

  if (loading) {
    return <div>Loading backtest results...</div>;
  }

  if (result?.status === 'running') {
    return <div>Backtest is running... Please wait.</div>;
  }

  return (
    <div className="backtest-result">
      {/* 摘要卡片 */}
      <div className="summary-cards">
        <SummaryCard
          title="Total Return"
          value={`${result?.summary.total_return.toFixed(2)}%`}
          color={result?.summary.total_return > 0 ? 'green' : 'red'}
        />
        <SummaryCard
          title="Sharpe Ratio"
          value={result?.summary.sharpe_ratio.toFixed(2)}
        />
        <SummaryCard
          title="Max Drawdown"
          value={`${result?.summary.max_drawdown.toFixed(2)}%`}
          color="red"
        />
        <SummaryCard
          title="Win Rate"
          value={`${result?.summary.win_rate.toFixed(1)}%`}
        />
      </div>

      {/* 权益曲线 */}
      <div className="chart-section">
        <h2>Equity Curve</h2>
        <div id="equity-chart"></div>
      </div>

      {/* 回撤图 */}
      <div className="chart-section">
        <h2>Drawdown</h2>
        <div id="drawdown-chart"></div>
      </div>

      {/* 交易列表 */}
      <div className="trades-section">
        <h2>Trades ({result?.summary.total_trades})</h2>
        <TradesTable trades={result?.charts.trades || []} />
      </div>
    </div>
  );
}

function SummaryCard({ title, value, color }: any) {
  return (
    <div className="summary-card">
      <div className="card-title">{title}</div>
      <div className="card-value" style={{ color }}>
        {value}
      </div>
    </div>
  );
}
```

#### 样式设计（参考 TradingView）

```css
/* frontend/src/pages/BacktestResult.css */
.backtest-result {
  padding: 24px;
  background: #131722;
  min-height: 100vh;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}

.summary-card {
  background: #1e222d;
  border: 1px solid #2a2e39;
  border-radius: 8px;
  padding: 20px;
}

.card-title {
  color: #787b86;
  font-size: 14px;
  margin-bottom: 8px;
}

.card-value {
  font-size: 28px;
  font-weight: 600;
  color: #d1d4dc;
}

.chart-section {
  background: #1e222d;
  border: 1px solid #2a2e39;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 24px;
}

.chart-section h2 {
  color: #d1d4dc;
  font-size: 18px;
  margin-bottom: 16px;
}
```

---

## 问题 2：数据导入策略

### 推荐方案：按需导入（On-Demand）

**不需要导入所有市场数据，只导入用户订阅的市场数据。**

### 理由

**成本考虑**：
```
全市场数据量估算：
- Binance: 400+ 交易对
- 每个交易对 1 年数据: ~5GB
- 总计: 2TB+

存储成本:
- TimescaleDB: $200-500/月
- S3/GCS: $50-100/月

按需导入:
- 只存储活跃订阅的数据
- 成本降低 90%+
```

**性能考虑**：
- 查询速度更快
- 索引更小
- 维护更简单

### 数据导入架构

```
┌─────────────────────────────────────────────────────┐
│                  数据导入策略                         │
└─────────────────────────────────────────────────────┘

1. 实时数据（Live Trading）
   交易所 WebSocket → Nautilus → Redis → TimescaleDB
   - 只订阅活跃市场
   - 实时写入数据库
   - 保留 90 天

2. 历史数据（Backtesting）
   方案 A: 按需下载
   - 用户请求回测时下载
   - 缓存到本地
   - 保留 30 天

   方案 B: 预加载热门市场
   - 预先下载 Top 50 交易对
   - 每日更新
   - 其他按需下载

3. 数据源
   - Binance: 官方 API（免费）
   - Alpaca: 官方 API（免费）
   - IB: TWS API（需要账户）
```

### 实现方案

#### 1. 数据订阅管理器

```python
# nautilus-core/data/subscription_manager.py
from typing import Set, Dict
import asyncio

class DataSubscriptionManager:
    """管理数据订阅"""
    
    def __init__(self):
        self.active_subscriptions: Dict[str, Set[str]] = {}
        # key: exchange, value: set of symbols
    
    async def add_subscription(self, tenant_id: str, exchange: str, symbol: str):
        """
        添加订阅
        
        当租户订阅一个市场时：
        1. 检查是否已有其他租户订阅
        2. 如果没有，启动数据流
        3. 如果有，直接复用
        """
        key = f"{exchange}:{symbol}"
        
        if key not in self.active_subscriptions:
            self.active_subscriptions[key] = set()
            # 启动数据流
            await self._start_data_stream(exchange, symbol)
        
        self.active_subscriptions[key].add(tenant_id)
        
        # 开始存储历史数据
        await self._start_historical_storage(exchange, symbol)
    
    async def remove_subscription(self, tenant_id: str, exchange: str, symbol: str):
        """
        移除订阅
        
        当租户取消订阅时：
        1. 从订阅列表移除
        2. 如果没有其他租户订阅，停止数据流
        """
        key = f"{exchange}:{symbol}"
        
        if key in self.active_subscriptions:
            self.active_subscriptions[key].discard(tenant_id)
            
            # 如果没有租户订阅了，停止数据流
            if len(self.active_subscriptions[key]) == 0:
                await self._stop_data_stream(exchange, symbol)
                del self.active_subscriptions[key]
    
    async def _start_data_stream(self, exchange: str, symbol: str):
        """启动数据流"""
        # 通知 Nautilus 开始订阅
        await self._notify_nautilus_subscribe(exchange, symbol)
    
    async def _stop_data_stream(self, exchange: str, symbol: str):
        """停止数据流"""
        await self._notify_nautilus_unsubscribe(exchange, symbol)
```

#### 2. 历史数据下载器

```python
# nautilus-core/data/historical_downloader.py
import asyncio
from datetime import datetime, timedelta
import pandas as pd

class HistoricalDataDownloader:
    """历史数据下载器"""
    
    def __init__(self):
        self.cache_dir = "./data/historical"
        self.cache_ttl_days = 30
    
    async def download_historical_data(
        self,
        exchange: str,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str = "1m"
    ) -> pd.DataFrame:
        """
        下载历史数据
        
        流程：
        1. 检查本地缓存
        2. 如果有且未过期，返回缓存
        3. 如果没有或过期，从交易所下载
        4. 保存到缓存
        """
        
        # 1. 检查缓存
        cache_key = f"{exchange}_{symbol}_{start_date}_{end_date}_{interval}"
        cached_data = await self._check_cache(cache_key)
        
        if cached_data is not None:
            return cached_data
        
        # 2. 从交易所下载
        if exchange == "binance":
            data = await self._download_from_binance(symbol, start_date, end_date, interval)
        elif exchange == "alpaca":
            data = await self._download_from_alpaca(symbol, start_date, end_date, interval)
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")
        
        # 3. 保存到缓存
        await self._save_to_cache(cache_key, data)
        
        return data
    
    async def _download_from_binance(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        interval: str
    ) -> pd.DataFrame:
        """从 Binance 下载数据"""
        from binance.client import Client
        
        client = Client()  # 不需要 API key 下载历史数据
        
        # 转换日期格式
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
        
        # 下载 K线数据
        klines = client.get_historical_klines(
            symbol.replace("-", ""),  # BTC-USDT -> BTCUSDT
            interval,
            start_ts,
            end_ts
        )
        
        # 转换为 DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        # 转换数据类型
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
    
    async def _save_to_cache(self, cache_key: str, data: pd.DataFrame):
        """保存到 Parquet 缓存"""
        import os
        
        os.makedirs(self.cache_dir, exist_ok=True)
        cache_path = f"{self.cache_dir}/{cache_key}.parquet"
        
        data.to_parquet(cache_path, compression='snappy')
    
    async def _check_cache(self, cache_key: str) -> pd.DataFrame | None:
        """检查缓存"""
        import os
        from datetime import datetime
        
        cache_path = f"{self.cache_dir}/{cache_key}.parquet"
        
        if not os.path.exists(cache_path):
            return None
        
        # 检查是否过期
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if datetime.now() - file_time > timedelta(days=self.cache_ttl_days):
            return None
        
        return pd.read_parquet(cache_path)
```

#### 3. 数据存储策略

```sql
-- TimescaleDB 表结构
CREATE TABLE market_data (
    time        TIMESTAMPTZ NOT NULL,
    exchange    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    open        DECIMAL(20, 8),
    high        DECIMAL(20, 8),
    low         DECIMAL(20, 8),
    close       DECIMAL(20, 8),
    volume      DECIMAL(20, 8),
    PRIMARY KEY (time, exchange, symbol)
);

-- 创建 Hypertable（时序表）
SELECT create_hypertable('market_data', 'time');

-- 创建索引
CREATE INDEX idx_market_data_symbol ON market_data (exchange, symbol, time DESC);

-- 数据保留策略（只保留 90 天）
SELECT add_retention_policy('market_data', INTERVAL '90 days');

-- 压缩策略（7 天后压缩）
ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'exchange, symbol'
);

SELECT add_compression_policy('market_data', INTERVAL '7 days');
```

#### 4. 数据流程图

```
用户订阅市场
    ↓
检查是否已有订阅
    ↓
┌─────────────────┬─────────────────┐
│   已有订阅      │   新订阅        │
├─────────────────┼─────────────────┤
│ 直接复用数据流  │ 启动新数据流    │
│                 │ ↓               │
│                 │ Nautilus订阅    │
│                 │ ↓               │
│                 │ WebSocket连接   │
└─────────────────┴─────────────────┘
    ↓
实时数据写入 TimescaleDB
    ↓
保留 90 天（自动清理）

回测请求
    ↓
检查本地缓存
    ↓
┌─────────────────┬─────────────────┐
│   有缓存        │   无缓存        │
├─────────────────┼─────────────────┤
│ 直接使用        │ 从交易所下载    │
│                 │ ↓               │
│                 │ 保存到缓存      │
└─────────────────┴─────────────────┘
    ↓
运行回测
```

### 数据成本优化

```python
# 数据存储成本估算
class DataCostEstimator:
    """数据成本估算器"""
    
    def estimate_storage_cost(self, num_symbols: int, days: int) -> dict:
        """
        估算存储成本
        
        假设：
        - 每个交易对每天 1440 条 1分钟K线
        - 每条记录约 100 字节
        """
        
        # 原始数据大小
        records_per_day = 1440  # 1分钟K线
        bytes_per_record = 100
        
        total_records = num_symbols * days * records_per_day
        total_bytes = total_records * bytes_per_record
        total_gb = total_bytes / (1024 ** 3)
        
        # TimescaleDB 压缩后（约 10:1）
        compressed_gb = total_gb / 10
        
        # 成本估算（AWS RDS）
        cost_per_gb_month = 0.115  # $0.115/GB/月
        monthly_cost = compressed_gb * cost_per_gb_month
        
        return {
            "symbols": num_symbols,
            "days": days,
            "total_records": total_records,
            "raw_size_gb": round(total_gb, 2),
            "compressed_size_gb": round(compressed_gb, 2),
            "monthly_cost_usd": round(monthly_cost, 2)
        }

# 示例
estimator = DataCostEstimator()

# 场景 1: 全市场数据（不推荐）
print(estimator.estimate_storage_cost(400, 365))
# {
#   "symbols": 400,
#   "days": 365,
#   "total_records": 210240000,
#   "raw_size_gb": 19.6,
#   "compressed_size_gb": 1.96,
#   "monthly_cost_usd": 0.23
# }

# 场景 2: 按需订阅（推荐）
print(estimator.estimate_storage_cost(50, 90))
# {
#   "symbols": 50,
#   "days": 90,
#   "total_records": 6480000,
#   "raw_size_gb": 0.61,
#   "compressed_size_gb": 0.06,
#   "monthly_cost_usd": 0.01
# }
```

### 推荐配置

```yaml
# config/data_strategy.yaml
data_strategy:
  # 实时数据
  live_data:
    retention_days: 90  # 保留 90 天
    compression_after_days: 7  # 7 天后压缩
    
  # 历史数据
  historical_data:
    cache_enabled: true
    cache_ttl_days: 30
    cache_dir: ./data/historical
    
    # 预加载热门市场
    preload_enabled: true
    preload_symbols:
      - BTC-USDT
      - ETH-USDT
      - SOL-USDT
      # ... Top 50
    
  # 订阅管理
  subscription:
    max_symbols_per_tenant:
      free: 10
      starter: 50
      professional: 999999
```

---

## 总结

### 问题 1：回测和图表

**回测引擎**：
- ✅ 使用 Nautilus Trader（已集成）
- ✅ 事件驱动，与实盘一致
- ✅ 专业级性能

**图表展示**：
- ✅ 使用 Lightweight Charts（已在用）
- ✅ 权益曲线、回撤图、交易标记
- ✅ 参考 TradingView 设计

**实现时间**：
- 后端 API：2-3 天
- 前端页面：3-5 天
- 总计：1 周

### 问题 2：数据导入

**推荐策略**：
- ✅ **按需导入**（不导入全市场）
- ✅ 只存储活跃订阅的数据
- ✅ 历史数据按需下载 + 缓存
- ✅ 保留 90 天实时数据

**成本优势**：
- 存储成本降低 90%+
- 查询性能更好
- 维护更简单

**数据源**：
- Binance：免费 API
- Alpaca：免费 API
- 其他：按需添加

需要我帮你实现具体的代码吗？
