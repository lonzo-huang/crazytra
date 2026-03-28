# 租户自定义订阅系统设计

## 概述

允许每个租户自由选择：
1. **订阅市场**：选择要交易的交易对和交易所
2. **订阅策略**：从策略市场选择或创建自定义策略

## 市场订阅系统

### 数据模型

```go
// 租户市场订阅
type TenantMarketSubscription struct {
    ID           string    `json:"id"`
    TenantID     string    `json:"tenant_id"`
    Exchange     string    `json:"exchange"`     // binance, polymarket, etc.
    Symbol       string    `json:"symbol"`       // BTC-USDT, ETH-USDT
    Status       string    `json:"status"`       // active, paused, stopped
    Priority     int       `json:"priority"`     // 优先级 1-10
    CreatedAt    time.Time `json:"created_at"`
    UpdatedAt    time.Time `json:"updated_at"`
    
    // 订阅配置
    Config       SubscriptionConfig `json:"config"`
}

type SubscriptionConfig struct {
    // 数据频率
    TickInterval     string `json:"tick_interval"`      // realtime, 1s, 5s
    DepthLevel       int    `json:"depth_level"`        // 订单簿深度
    
    // 数据保留
    HistoryDays      int    `json:"history_days"`       // 历史数据保留天数
    
    // 通知设置
    EnableNotify     bool   `json:"enable_notify"`      // 是否启用通知
    NotifyThreshold  float64 `json:"notify_threshold"`  // 价格变动通知阈值
}
```

### 可订阅的市场

```yaml
交易所:
  Binance:
    - 现货: BTC-USDT, ETH-USDT, SOL-USDT, etc.
    - 合约: BTC-USDT-PERP
    - 费用: Free
    
  Polymarket:
    - 预测市场: TRUMP-WINS, BTC-100K
    - 费用: Free
    
  Tiger Brokers:
    - 美股: AAPL, TSLA, NVDA
    - 费用: Professional Plan+
    
  Trading212:
    - 欧股: 各种欧洲股票
    - 费用: Professional Plan+

配额限制:
  Free Plan: 10 个交易对
  Starter Plan: 50 个交易对
  Professional Plan: 无限制
  Enterprise Plan: 无限制 + 自定义交易所
```

### API 接口

```go
// 获取可用市场列表
GET /api/v1/markets/available
Response:
{
  "exchanges": [
    {
      "id": "binance",
      "name": "Binance",
      "type": "crypto",
      "symbols": ["BTC-USDT", "ETH-USDT", ...],
      "available_in_plan": ["free", "starter", "professional", "enterprise"]
    }
  ]
}

// 订阅市场
POST /api/v1/tenant/subscriptions/markets
Request:
{
  "exchange": "binance",
  "symbol": "BTC-USDT",
  "config": {
    "tick_interval": "realtime",
    "depth_level": 20,
    "history_days": 30,
    "enable_notify": true,
    "notify_threshold": 0.05
  }
}

// 获取我的订阅
GET /api/v1/tenant/subscriptions/markets

// 更新订阅配置
PATCH /api/v1/tenant/subscriptions/markets/{id}

// 暂停/恢复订阅
POST /api/v1/tenant/subscriptions/markets/{id}/pause
POST /api/v1/tenant/subscriptions/markets/{id}/resume

// 取消订阅
DELETE /api/v1/tenant/subscriptions/markets/{id}
```

### 动态数据路由

```go
// 根据租户订阅动态路由数据
func RouteMarketData(tick *MarketTick) {
    // 查询订阅了这个市场的所有租户
    subscriptions := getActiveSubscriptions(tick.Exchange, tick.Symbol)
    
    for _, sub := range subscriptions {
        // 检查配额
        if !checkQuota(sub.TenantID) {
            continue
        }
        
        // 发送到租户的 Redis Stream
        key := fmt.Sprintf("tenant:%s:market.tick.%s.%s", 
            sub.TenantID, tick.Exchange, tick.Symbol)
        
        redis.XAdd(ctx, &redis.XAddArgs{
            Stream: key,
            Values: tick.ToMap(),
            MaxLen: sub.Config.HistoryDays * 86400, // 按天数限制
        })
        
        // 如果启用通知且价格变动超过阈值
        if sub.Config.EnableNotify && priceChangeExceeds(tick, sub.Config.NotifyThreshold) {
            sendPriceAlert(sub.TenantID, tick)
        }
    }
}
```

## 策略订阅系统

### 策略市场

```go
// 策略定义
type Strategy struct {
    ID              string          `json:"id"`
    Name            string          `json:"name"`
    Description     string          `json:"description"`
    Author          string          `json:"author"`
    Version         string          `json:"version"`
    Type            string          `json:"type"`        // public, private, premium
    Price           decimal.Decimal `json:"price"`       // 0 = free
    Rating          float64         `json:"rating"`
    Downloads       int             `json:"downloads"`
    
    // 策略元数据
    Category        string          `json:"category"`    // trend, mean_reversion, arbitrage
    Timeframe       string          `json:"timeframe"`   // 1m, 5m, 1h, 1d
    RiskLevel       string          `json:"risk_level"`  // low, medium, high
    
    // 性能指标
    Backtested      bool            `json:"backtested"`
    Sharpe          float64         `json:"sharpe"`
    MaxDrawdown     float64         `json:"max_drawdown"`
    WinRate         float64         `json:"win_rate"`
    
    // 代码
    CodeURL         string          `json:"code_url"`
    Parameters      []Parameter     `json:"parameters"`
    
    CreatedAt       time.Time       `json:"created_at"`
    UpdatedAt       time.Time       `json:"updated_at"`
}

type Parameter struct {
    Name            string      `json:"name"`
    Type            string      `json:"type"`        // int, float, string, bool
    Default         interface{} `json:"default"`
    Min             interface{} `json:"min,omitempty"`
    Max             interface{} `json:"max,omitempty"`
    Description     string      `json:"description"`
}
```

### 策略类型

```yaml
公开策略 (Public):
  - 免费使用
  - 社区贡献
  - 开源代码
  - 示例: MA Cross, RSI, MACD

私有策略 (Private):
  - 租户自己创建
  - 不对外公开
  - 完全自定义

高级策略 (Premium):
  - 付费策略
  - 专业团队开发
  - 经过回测验证
  - 持续更新
  - 价格: $10-$100/月
```

### 租户策略订阅

```go
// 租户策略订阅
type TenantStrategySubscription struct {
    ID              string                 `json:"id"`
    TenantID        string                 `json:"tenant_id"`
    StrategyID      string                 `json:"strategy_id"`
    Status          string                 `json:"status"`      // active, paused, stopped
    
    // 策略配置
    Parameters      map[string]interface{} `json:"parameters"`  // 自定义参数
    Symbols         []string               `json:"symbols"`     // 应用到哪些交易对
    
    // 资金管理
    MaxPositionSize decimal.Decimal        `json:"max_position_size"`
    MaxDailyLoss    decimal.Decimal        `json:"max_daily_loss"`
    
    // 性能追踪
    TotalTrades     int                    `json:"total_trades"`
    WinTrades       int                    `json:"win_trades"`
    TotalPnL        decimal.Decimal        `json:"total_pnl"`
    
    CreatedAt       time.Time              `json:"created_at"`
    UpdatedAt       time.Time              `json:"updated_at"`
}
```

### 策略市场 API

```go
// 浏览策略市场
GET /api/v1/strategies/marketplace
Query Parameters:
  - category: trend, mean_reversion, arbitrage
  - type: public, premium
  - min_rating: 4.0
  - sort: rating, downloads, newest

Response:
{
  "strategies": [
    {
      "id": "ma-cross-llm",
      "name": "MA Cross with LLM",
      "description": "均线交叉策略 + LLM 情感分析",
      "author": "MirrorQuant Team",
      "type": "public",
      "price": 0,
      "rating": 4.8,
      "downloads": 1250,
      "category": "trend",
      "backtested": true,
      "sharpe": 1.85,
      "win_rate": 0.62
    }
  ]
}

// 获取策略详情
GET /api/v1/strategies/{id}

// 订阅策略
POST /api/v1/tenant/subscriptions/strategies
Request:
{
  "strategy_id": "ma-cross-llm",
  "parameters": {
    "fast_period": 10,
    "slow_period": 30,
    "llm_weight": 0.3
  },
  "symbols": ["BTC-USDT", "ETH-USDT"],
  "max_position_size": 0.1,
  "max_daily_loss": 0.02
}

// 我的策略订阅
GET /api/v1/tenant/subscriptions/strategies

// 更新策略参数
PATCH /api/v1/tenant/subscriptions/strategies/{id}

// 暂停/恢复策略
POST /api/v1/tenant/subscriptions/strategies/{id}/pause
POST /api/v1/tenant/subscriptions/strategies/{id}/resume

// 取消订阅策略
DELETE /api/v1/tenant/subscriptions/strategies/{id}
```

### 策略执行引擎

```go
// 策略执行器
type StrategyExecutor struct {
    tenantID    string
    subscription *TenantStrategySubscription
    strategy    *Strategy
    instance    StrategyInstance
}

func (e *StrategyExecutor) Run() {
    // 订阅市场数据
    for _, symbol := range e.subscription.Symbols {
        key := fmt.Sprintf("tenant:%s:market.tick.%s", e.tenantID, symbol)
        
        // 消费市场数据
        go e.consumeMarketData(key, symbol)
    }
}

func (e *StrategyExecutor) consumeMarketData(streamKey, symbol string) {
    for {
        // 从 Redis Stream 读取数据
        result := redis.XRead(ctx, &redis.XReadArgs{
            Streams: []string{streamKey, "$"},
            Block:   time.Second,
        })
        
        for _, msg := range result {
            tick := parseMarketTick(msg)
            
            // 执行策略逻辑
            signals := e.instance.OnTick(tick)
            
            // 发布信号
            for _, signal := range signals {
                publishSignal(e.tenantID, signal)
            }
        }
    }
}
```

## 自定义策略开发

### 策略开发工作流

```
1. 在线编辑器
   ↓
2. 参数配置
   ↓
3. 回测验证
   ↓
4. 保存为私有策略
   ↓
5. 启用实盘交易
   ↓
6. (可选) 发布到市场
```

### 策略模板

```python
# 租户自定义策略模板
from mirrorquant import Strategy, Signal

class MyCustomStrategy(Strategy):
    """
    我的自定义策略
    """
    
    # 策略元数据
    STRATEGY_ID = "my-custom-strategy"
    STRATEGY_NAME = "My Custom Strategy"
    
    # 可配置参数
    PARAMETERS = {
        "threshold": {
            "type": "float",
            "default": 0.02,
            "min": 0.01,
            "max": 0.1,
            "description": "信号触发阈值"
        },
        "period": {
            "type": "int",
            "default": 20,
            "min": 5,
            "max": 100,
            "description": "计算周期"
        }
    }
    
    def __init__(self, params):
        super().__init__(params)
        self.threshold = params.get("threshold", 0.02)
        self.period = params.get("period", 20)
        self.prices = []
    
    def on_tick(self, tick):
        """处理市场数据"""
        self.prices.append(float(tick.last))
        
        if len(self.prices) < self.period:
            return []
        
        # 保持固定长度
        self.prices = self.prices[-self.period:]
        
        # 计算指标
        avg = sum(self.prices) / len(self.prices)
        current = self.prices[-1]
        change = (current - avg) / avg
        
        # 生成信号
        if change > self.threshold:
            return [Signal(
                symbol=tick.symbol,
                direction="long",
                strength=min(abs(change) / self.threshold, 1.0),
                reason=f"价格高于均线 {change:.2%}"
            )]
        elif change < -self.threshold:
            return [Signal(
                symbol=tick.symbol,
                direction="short",
                strength=min(abs(change) / self.threshold, 1.0),
                reason=f"价格低于均线 {change:.2%}"
            )]
        
        return []
```

### 在线策略编辑器

```typescript
// 前端策略编辑器组件
import { CodeEditor } from '@monaco-editor/react';

function StrategyEditor() {
  const [code, setCode] = useState(strategyTemplate);
  const [parameters, setParameters] = useState({});
  const [backtestResult, setBacktestResult] = useState(null);
  
  const handleBacktest = async () => {
    const result = await api.post('/api/v1/strategies/backtest', {
      code: code,
      parameters: parameters,
      symbols: ['BTC-USDT'],
      start_date: '2024-01-01',
      end_date: '2024-12-31'
    });
    setBacktestResult(result.data);
  };
  
  const handleSave = async () => {
    await api.post('/api/v1/strategies/custom', {
      name: 'My Strategy',
      code: code,
      parameters: parameters
    });
  };
  
  return (
    <div>
      <CodeEditor
        language="python"
        value={code}
        onChange={setCode}
      />
      <ParameterConfig
        parameters={parameters}
        onChange={setParameters}
      />
      <Button onClick={handleBacktest}>回测</Button>
      <Button onClick={handleSave}>保存</Button>
      {backtestResult && (
        <BacktestResults data={backtestResult} />
      )}
    </div>
  );
}
```

## 订阅管理界面

### Dashboard 订阅视图

```typescript
// 市场订阅管理
function MarketSubscriptions() {
  return (
    <div>
      <h2>我的市场订阅</h2>
      
      {/* 添加新订阅 */}
      <Button onClick={openMarketSelector}>
        + 添加市场
      </Button>
      
      {/* 订阅列表 */}
      <Table>
        <thead>
          <tr>
            <th>交易所</th>
            <th>交易对</th>
            <th>状态</th>
            <th>数据频率</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {subscriptions.map(sub => (
            <tr key={sub.id}>
              <td>{sub.exchange}</td>
              <td>{sub.symbol}</td>
              <td>
                <Badge color={sub.status === 'active' ? 'green' : 'gray'}>
                  {sub.status}
                </Badge>
              </td>
              <td>{sub.config.tick_interval}</td>
              <td>
                <Button onClick={() => pause(sub.id)}>暂停</Button>
                <Button onClick={() => configure(sub.id)}>配置</Button>
                <Button onClick={() => unsubscribe(sub.id)}>取消</Button>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}

// 策略订阅管理
function StrategySubscriptions() {
  return (
    <div>
      <h2>我的策略</h2>
      
      {/* 浏览策略市场 */}
      <Button onClick={openStrategyMarket}>
        浏览策略市场
      </Button>
      
      {/* 创建自定义策略 */}
      <Button onClick={openStrategyEditor}>
        创建自定义策略
      </Button>
      
      {/* 策略列表 */}
      <Grid>
        {strategies.map(strategy => (
          <StrategyCard
            key={strategy.id}
            strategy={strategy}
            onConfigure={configureStrategy}
            onPause={pauseStrategy}
            onResume={resumeStrategy}
          />
        ))}
      </Grid>
    </div>
  );
}
```

## 配额和计费

### 订阅配额

```go
type SubscriptionQuota struct {
    // 市场订阅配额
    MaxMarketSubscriptions int  // 最大市场订阅数
    MaxExchanges          int  // 可用交易所数量
    
    // 策略订阅配额
    MaxStrategySubscriptions int  // 最大策略订阅数
    MaxCustomStrategies      int  // 最大自定义策略数
    CanAccessPremium        bool // 是否可访问高级策略
    
    // 数据配额
    MaxHistoryDays          int  // 历史数据保留
    MaxTicksPerSecond       int  // 数据频率限制
}

// 不同计划的配额
var PlanQuotas = map[string]SubscriptionQuota{
    "free": {
        MaxMarketSubscriptions:   10,
        MaxExchanges:            1,  // 仅 Binance
        MaxStrategySubscriptions: 1,
        MaxCustomStrategies:     0,
        CanAccessPremium:        false,
        MaxHistoryDays:          7,
        MaxTicksPerSecond:       1,
    },
    "starter": {
        MaxMarketSubscriptions:   50,
        MaxExchanges:            2,
        MaxStrategySubscriptions: 3,
        MaxCustomStrategies:     1,
        CanAccessPremium:        false,
        MaxHistoryDays:          30,
        MaxTicksPerSecond:       10,
    },
    "professional": {
        MaxMarketSubscriptions:   -1, // 无限制
        MaxExchanges:            -1,
        MaxStrategySubscriptions: 10,
        MaxCustomStrategies:     5,
        CanAccessPremium:        true,
        MaxHistoryDays:          90,
        MaxTicksPerSecond:       100,
    },
}
```

### 高级策略计费

```go
// 策略订阅费用
type StrategyBilling struct {
    StrategyID      string
    StrategyName    string
    MonthlyFee      decimal.Decimal
    UsageFee        decimal.Decimal  // 基于交易量
    TotalFee        decimal.Decimal
}

// 计算策略费用
func calculateStrategyFees(tenant *Tenant) []StrategyBilling {
    var fees []StrategyBilling
    
    for _, sub := range tenant.StrategySubscriptions {
        strategy := getStrategy(sub.StrategyID)
        
        if strategy.Type == "premium" {
            fee := StrategyBilling{
                StrategyID:   strategy.ID,
                StrategyName: strategy.Name,
                MonthlyFee:   strategy.Price,
            }
            
            // 如果有基于使用量的费用
            if strategy.UsageBasedPricing {
                trades := countTrades(tenant.ID, sub.ID)
                fee.UsageFee = decimal.NewFromInt(trades).
                    Mul(strategy.PricePerTrade)
            }
            
            fee.TotalFee = fee.MonthlyFee.Add(fee.UsageFee)
            fees = append(fees, fee)
        }
    }
    
    return fees
}
```

## 通知和告警

### 订阅通知

```go
// 市场订阅通知
type SubscriptionNotification struct {
    Type        string  // price_alert, volume_spike, new_data
    TenantID    string
    Symbol      string
    Message     string
    Severity    string  // info, warning, critical
    Timestamp   time.Time
}

// 价格告警
func checkPriceAlert(sub *TenantMarketSubscription, tick *MarketTick) {
    if !sub.Config.EnableNotify {
        return
    }
    
    lastPrice := getLastPrice(sub.TenantID, tick.Symbol)
    change := (tick.Last - lastPrice) / lastPrice
    
    if math.Abs(change) >= sub.Config.NotifyThreshold {
        notification := &SubscriptionNotification{
            Type:     "price_alert",
            TenantID: sub.TenantID,
            Symbol:   tick.Symbol,
            Message:  fmt.Sprintf("%s 价格变动 %.2f%%", tick.Symbol, change*100),
            Severity: "warning",
        }
        
        sendNotification(notification)
    }
}
```

## 总结

租户自定义订阅系统提供：

✅ **灵活的市场选择**
- 多交易所支持
- 自由选择交易对
- 动态订阅/取消

✅ **丰富的策略市场**
- 公开免费策略
- 高级付费策略
- 自定义策略开发

✅ **精细的配额控制**
- 按计划分配配额
- 实时配额检查
- 超量自动限流

✅ **完整的管理界面**
- 可视化订阅管理
- 在线策略编辑器
- 回测和性能追踪

✅ **灵活的计费模式**
- 订阅费 + 使用费
- 高级策略单独计费
- 透明的费用明细
