# MirrorQuant 策略开发指南

本目录包含基于 Nautilus Trader 的策略实现，支持 LLM 权重增强。

## 策略架构

```
MirrorQuantStrategy (基类)
├── LLM 权重管理
├── 热重载支持
├── 状态导入/导出
└── 抽象方法定义

MACrossLLMStrategy (示例)
├── 继承 MirrorQuantStrategy
├── 均线交叉逻辑
├── LLM 权重调整仓位
└── 完整的订单管理
```

## 快速开始

### 1. 创建新策略

```python
from nautilus_core.strategies.base_strategy import MirrorQuantStrategy, MirrorQuantStrategyConfig
from nautilus_trader.model.data import QuoteTick
from pydantic import Field

class MyStrategyConfig(MirrorQuantStrategyConfig):
    """策略配置"""
    instrument_id: str
    my_param: int = Field(default=10, ge=1, le=100)
    # LLM 配置自动继承
    enable_llm: bool = True
    llm_weight_factor: float = 0.5

class MyStrategy(MirrorQuantStrategy):
    """我的策略"""
    
    def __init__(self, config: MyStrategyConfig):
        super().__init__(config)
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
    
    def on_start(self) -> None:
        """启动时订阅数据"""
        super().on_start()
        self.subscribe_quote_ticks(self.instrument_id)
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        """处理行情"""
        # 1. 计算基础信号
        strength = self.calculate_signal_strength(tick)
        direction = self.calculate_signal_direction(tick)
        
        # 2. 获取 LLM 调整因子
        symbol = self._convert_instrument_to_symbol(tick.instrument_id)
        llm_factor = self.get_effective_llm_factor(symbol)
        
        # 3. 调整仓位
        adjusted_size = base_size * strength * llm_factor
        
        # 4. 下单
        if direction == "long" and adjusted_size > 0.001:
            self._submit_buy_order(tick, adjusted_size)
    
    def calculate_signal_strength(self, tick: QuoteTick) -> float:
        """计算信号强度 [0, 1]"""
        # 实现你的逻辑
        return 0.5
    
    def calculate_signal_direction(self, tick: QuoteTick) -> str:
        """计算信号方向"""
        # 返回 "long", "short", "exit", "hold"
        return "long"
```

### 2. 配置策略

```python
from nautilus_trader.config import TradingNodeConfig
from nautilus_core.strategies.my_strategy import MyStrategyConfig

config = TradingNodeConfig(
    trader_id=TraderId("TRADER-001"),
    strategies=[
        MyStrategyConfig(
            instrument_id="BTCUSDT.BINANCE",
            my_param=20,
            enable_llm=True,
            llm_weight_factor=0.5,
        ),
    ],
)
```

### 3. 运行策略

```bash
cd nautilus-core
python main.py --mode paper  # 纸面交易
python main.py --mode live   # 实盘交易
```

## MirrorQuantStrategy 基类

### 核心功能

#### 1. LLM 权重管理

```python
# 获取 LLM 权重
weight = self.get_llm_weight("BTC-USDT")
if weight:
    score, confidence = weight
    print(f"Score: {score}, Confidence: {confidence}")

# 获取有效影响因子
llm_factor = self.get_effective_llm_factor("BTC-USDT")
# 返回 [0.5, 2.0]
# 1.0 = 中性
# < 1.0 = 看跌（减少多头仓位）
# > 1.0 = 看涨（增加多头仓位）
```

#### 2. LLM 权重更新回调

```python
def on_llm_weight_updated(
    self,
    symbol: str,
    score: float,        # [-1.0, 1.0]
    confidence: float,   # [0.0, 1.0]
    metadata: dict,
) -> None:
    """LLM 权重更新时调用"""
    # 可选：根据 LLM 信号调整策略
    if score < -0.8 and confidence > 0.9:
        # 强烈看跌信号，考虑平仓
        self._close_all_positions()
```

#### 3. 热重载支持

```python
def export_state(self) -> dict:
    """导出状态（用于热重载）"""
    state = super().export_state()
    state.update({
        "my_custom_state": self._my_state,
        "trade_count": self._trade_count,
    })
    return state

def import_state(self, state: dict) -> None:
    """导入状态"""
    super().import_state(state)
    self._my_state = state.get("my_custom_state")
    self._trade_count = state.get("trade_count", 0)
```

### 必须实现的方法

```python
@abstractmethod
def calculate_signal_strength(self, tick: QuoteTick) -> float:
    """计算信号强度 [0.0, 1.0]"""
    pass

@abstractmethod
def calculate_signal_direction(self, tick: QuoteTick) -> str:
    """计算信号方向 "long" | "short" | "exit" | "hold" """
    pass
```

## 配置参数

### MirrorQuantStrategyConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enable_llm` | bool | True | 是否启用 LLM 权重 |
| `llm_weight_factor` | float | 0.5 | LLM 权重影响系数 [0, 1] |
| `min_confidence` | float | 0.3 | 最小置信度阈值 |

### LLM 权重影响系数说明

```python
# llm_weight_factor = 0.0
# LLM 权重完全不影响仓位

# llm_weight_factor = 0.5 (默认)
# LLM 权重影响减半
# 例如：LLM score=1.0, confidence=1.0
# 原始 factor = 2.0
# 调整后 factor = 1.0 + (2.0 - 1.0) * 0.5 = 1.5

# llm_weight_factor = 1.0
# LLM 权重完全影响仓位
```

## 示例策略：MACrossLLM

均线交叉策略 + LLM 权重增强。

### 策略逻辑

1. **技术信号**：
   - 金叉（快线上穿慢线）→ 做多
   - 死叉（快线下穿慢线）→ 做空

2. **LLM 增强**：
   - LLM 看涨（score > 0）→ 增加多头仓位
   - LLM 看跌（score < 0）→ 减少多头仓位或增加空头仓位

3. **仓位计算**：
   ```python
   adjusted_size = base_size * signal_strength * llm_factor
   ```

### 配置示例

```python
MACrossLLMConfig(
    instrument_id="BTCUSDT.BINANCE",
    fast_period=10,      # 快线周期
    slow_period=30,      # 慢线周期
    trade_size=Decimal("0.01"),  # 基础仓位
    enable_llm=True,
    llm_weight_factor=0.5,
    min_confidence=0.3,
)
```

### 运行示例

```bash
cd nautilus-core
python examples/ma_cross_llm_example.py
```

## LLM 权重数据流

```
LLM 层 (独立进程)
    ↓ 发布到 Redis
Redis Stream: llm.weight
    ↓ 消费
LLMWeightActor
    ↓ 时间衰减融合
    ↓ 发布事件
MirrorQuantStrategy.on_llm_weight_updated()
    ↓ 调整仓位
订单提交
```

## 回测 vs 实盘

### 回测模式

```python
# 使用历史数据
python main.py --mode backtest --data historical_ticks.parquet
```

**关键特性**：
- ✅ 完全相同的策略代码
- ✅ 真实的订单簿模拟
- ✅ 滑点和手续费
- ✅ LLM 权重回放

### 实盘模式

```python
# 纸面交易
python main.py --mode paper

# 实盘交易
python main.py --mode live
```

**关键特性**：
- ✅ 实时市场数据
- ✅ 实时 LLM 权重
- ✅ 真实订单执行

## 最佳实践

### 1. 信号强度计算

```python
def calculate_signal_strength(self, tick: QuoteTick) -> float:
    """基于多个因素计算强度"""
    # 因素1：技术指标距离
    indicator_strength = self._calculate_indicator_strength()
    
    # 因素2：成交量
    volume_strength = self._calculate_volume_strength()
    
    # 因素3：波动率
    volatility_strength = self._calculate_volatility_strength()
    
    # 加权平均
    total_strength = (
        indicator_strength * 0.5 +
        volume_strength * 0.3 +
        volatility_strength * 0.2
    )
    
    return min(max(total_strength, 0.0), 1.0)
```

### 2. LLM 权重使用

```python
def on_quote_tick(self, tick: QuoteTick) -> None:
    # 获取技术信号
    tech_signal = self.calculate_signal_direction(tick)
    tech_strength = self.calculate_signal_strength(tick)
    
    # 获取 LLM 因子
    llm_factor = self.get_effective_llm_factor(symbol)
    
    # 组合决策
    if tech_signal == "long":
        # LLM 看涨时增强，看跌时减弱
        final_size = base_size * tech_strength * llm_factor
    elif tech_signal == "short":
        # LLM 看跌时增强
        adjusted_factor = 2.0 - llm_factor if llm_factor < 1.0 else 1.0
        final_size = base_size * tech_strength * adjusted_factor
```

### 3. 风险管理

```python
def _check_risk_limits(self, size: Decimal) -> bool:
    """检查风险限制"""
    # 检查最大仓位
    portfolio = self.portfolio
    if portfolio.net_position(self.instrument_id) + size > self.max_position:
        return False
    
    # 检查账户余额
    if portfolio.balance_total() < size * price:
        return False
    
    return True
```

## 故障排查

### 问题：LLM 权重未更新

**检查**：
1. LLMWeightActor 是否运行
2. Redis llm.weight stream 是否有数据
3. 策略是否订阅了 LLMWeightUpdate 事件

### 问题：策略不下单

**检查**：
1. 信号强度是否 > 0
2. LLM 因子是否合理
3. 调整后的仓位是否 > 最小阈值（0.001）

### 问题：回测结果与实盘不一致

**检查**：
1. 是否使用了相同的配置参数
2. 回测数据质量
3. 滑点和手续费设置

## 参考资料

- [Nautilus Trader 文档](https://nautilustrader.io)
- [ARCHITECTURE.md](../../ARCHITECTURE.md) - 系统架构
- [SYSTEM_SPEC.md](../../SYSTEM_SPEC.md) - 系统规范
- [LLM 层文档](../../llm-layer/README.md)
