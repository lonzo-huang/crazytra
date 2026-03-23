# Nautilus Trader 整合测试指南

本文档提供完整的测试验证步骤，确保 Nautilus Trader 整合正确工作。

## 测试前准备

### 1. 确保 Redis 运行

```bash
# 检查 Redis 是否运行
redis-cli ping
# 应返回: PONG

# 如果未运行，启动 Redis
docker run -d -p 6379:6379 --name crazytra-redis redis:alpine
```

### 2. 安装测试依赖

```bash
cd nautilus-core

# 激活虚拟环境
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\Activate.ps1  # Windows PowerShell

# 安装测试依赖
pip install -r scripts/requirements-test.txt
```

---

## 快速验证

### 方式 A: 使用验证脚本（推荐）

**Linux/macOS:**
```bash
chmod +x scripts/run_verification.sh
./scripts/run_verification.sh
```

**Windows PowerShell:**
```powershell
.\scripts\run_verification.ps1
```

**直接运行 Python 脚本:**
```bash
python scripts/verify_integration.py
```

### 方式 B: 手动验证

按以下步骤手动验证每个组件。

---

## 详细测试步骤

### 测试 1: Redis 连接

```bash
# 测试 Redis 连接
redis-cli ping

# 查看 Redis 版本
redis-cli INFO server | grep redis_version

# 预期输出:
# PONG
# redis_version:7.2.x
```

✅ **通过标准**: 返回 PONG，版本 >= 7.2

---

### 测试 2: 启动 Nautilus 节点

```bash
# 在新终端启动 Nautilus
cd nautilus-core
source venv/bin/activate
python main.py --mode paper
```

**预期输出:**
```
============================================================
Nautilus Trading Node Started
============================================================
Trader ID: CRAZYTRA-001
Trading Mode: paper
Redis URL: redis://localhost:6379
============================================================

RedisBridgeActor connected to Redis at redis://localhost:6379
LLMWeightActor connected to Redis at redis://localhost:6379
```

✅ **通过标准**: 
- 节点成功启动
- RedisBridgeActor 已连接
- LLMWeightActor 已连接
- 无错误日志

---

### 测试 3: 验证 Tick 数据流

等待 Nautilus 连接到交易所（约 10-30 秒），然后检查 Redis：

```bash
# 检查 tick stream 是否存在
redis-cli EXISTS market.tick.binance.btcusdt

# 读取最新的 tick
redis-cli XREAD COUNT 1 STREAMS market.tick.binance.btcusdt 0
```

**预期输出:**
```json
1) 1) "market.tick.binance.btcusdt"
   2) 1) 1) "1700000000000-0"
         2) 1) "data"
            2) "{\"symbol\":\"BTC-USDT\",\"exchange\":\"binance\",\"timestamp_ns\":1700000000000000000,\"received_ns\":1700000000000050000,\"bid\":\"67840.50\",\"ask\":\"67841.20\",\"last\":\"67840.80\",\"latency_us\":50}"
```

✅ **通过标准**:
- Stream 存在
- 有数据
- JSON 格式正确
- 价格字段为字符串类型

**验证价格格式（重要）:**
```bash
# 提取 bid 价格并检查类型
redis-cli XREAD COUNT 1 STREAMS market.tick.binance.btcusdt 0 | grep -o '"bid":"[^"]*"'

# 应该看到: "bid":"67840.50" （字符串，不是数字）
```

---

### 测试 4: 验证 LLM 权重注入

```bash
# 发布测试 LLM 权重
redis-cli XADD llm.weight \* data '{
  "symbol":"BTC-USDT",
  "llm_score":0.75,
  "confidence":0.85,
  "horizon":"short",
  "key_drivers":["Test integration"],
  "risk_events":[],
  "model_used":"test",
  "ts_ns":1700000000000000000,
  "ttl_ms":300000
}'
```

**检查 Nautilus 日志:**
```
LLM weight updated for BTC-USDT: score=0.750, confidence=0.850
```

**验证消费者组:**
```bash
# 检查消费者组
redis-cli XINFO GROUPS llm.weight

# 应该看到 nautilus-llm-cg 组
```

✅ **通过标准**:
- 权重消息成功发布
- LLMWeightActor 消费了消息
- Nautilus 日志显示权重更新

---

### 测试 5: 验证订单流（可选）

如果策略已经下单，检查订单事件：

```bash
# 检查订单事件 stream
redis-cli XREAD COUNT 5 STREAMS order.event 0
```

**预期输出:**
```json
1) 1) "order.event"
   2) 1) 1) "1700000000001-0"
         2) 1) "data"
            2) "{\"event_id\":\"...\",\"order_id\":\"...\",\"symbol\":\"BTC-USDT\",\"kind\":\"submitted\",\"timestamp\":1700000000000000000}"
```

✅ **通过标准**:
- 订单事件格式正确
- kind 字段为有效状态（submitted/accepted/filled/cancelled/rejected）

---

### 测试 6: 运行单元测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_integration.py -v -s

# 运行特定测试函数
pytest tests/test_integration.py::test_redis_bridge_tick_format -v -s
```

✅ **通过标准**: 所有测试通过

---

## 自动化验证脚本

验证脚本会自动检查以下项目：

| 检查项 | 说明 | 依赖组件 |
|--------|------|----------|
| ✓ Redis 连接 | 基础设施 | Redis |
| ✓ Redis Streams | 消息总线 | Redis |
| ✓ Tick 数据格式 | RedisBridgeActor | Nautilus 节点 |
| ✓ LLM 消费者组 | LLMWeightActor | Nautilus 节点 |
| ✓ LLM 权重注入 | 权重流 | Nautilus 节点 |
| ✓ 订单事件格式 | 订单流 | Nautilus 节点 + 策略下单 |

**运行验证脚本:**
```bash
python scripts/verify_integration.py
```

**预期输出:**
```
============================================================
验证报告
============================================================
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 检查项                                   ┃ 状态     ┃ 说明                         ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Redis 连接                               │ ✓ 通过   │ 基础设施                     │
│ Redis Streams                            │ ✓ 通过   │ 消息总线                     │
│ Tick 数据格式                            │ ✓ 通过   │ RedisBridgeActor             │
│ LLM 消费者组                             │ ✓ 通过   │ LLMWeightActor               │
│ LLM 权重注入                             │ ✓ 通过   │ 权重流                       │
│ 订单事件格式                             │ ✓ 通过   │ 订单流                       │
└──────────────────────────────────────────┴──────────┴──────────────────────────────┘

总计: 6/6 项通过

╭─────────────────────────────────────────────────────────────────╮
│                              成功                               │
├─────────────────────────────────────────────────────────────────┤
│ 🎉 所有检查通过！Nautilus 整合正常工作。                       │
╰─────────────────────────────────────────────────────────────────╯
```

---

## 常见问题排查

### 问题 1: Redis 连接失败

**症状:**
```
Error: Cannot connect to Redis at redis://localhost:6379
```

**解决方案:**
```bash
# 1. 检查 Redis 是否运行
docker ps | grep redis

# 2. 如果未运行，启动 Redis
docker start crazytra-redis
# 或
docker run -d -p 6379:6379 --name crazytra-redis redis:alpine

# 3. 检查端口
netstat -tuln | grep 6379  # Linux
netstat -an | findstr 6379  # Windows
```

---

### 问题 2: Tick 数据格式错误

**症状:**
```
✗ bid 不是字符串类型（应为字符串）
```

**原因:** RedisBridgeActor 未正确序列化价格

**解决方案:**
```bash
# 1. 检查 RedisBridgeActor 代码
cat nautilus-core/actors/redis_bridge.py | grep "str(tick"

# 2. 确认价格转换为字符串
# 应该看到: "bid": str(tick.bid_price)

# 3. 重启 Nautilus 节点
```

---

### 问题 3: LLM 权重未被消费

**症状:**
```
⚠ 权重未被消费（检查 LLMWeightActor 日志）
```

**解决方案:**
```bash
# 1. 检查 LLMWeightActor 是否在 main.py 中配置
grep -A 5 "LLMWeightActor" nautilus-core/main.py

# 2. 检查 Nautilus 日志
tail -f nautilus-core/logs/nautilus.log | grep LLM

# 3. 手动检查消费者组
redis-cli XINFO GROUPS llm.weight
redis-cli XINFO CONSUMERS llm.weight nautilus-llm-cg
```

---

### 问题 4: 没有订单事件

**症状:**
```
⚠ 没有订单事件（可能还未下单）
```

**原因:** 策略还未生成订单

**这是正常的**，可以：
1. 等待策略触发交易信号
2. 手动测试下单（见下方）

**手动测试下单:**
```python
# 在 Nautilus 控制台或新脚本中
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from decimal import Decimal

# 获取策略实例
strategy = node.trader.strategies()[0]

# 创建市价单
order = strategy.order_factory.market(
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    order_side=OrderSide.BUY,
    quantity=Decimal("0.001"),
)

# 提交订单
strategy.submit_order(order)
```

---

## 性能基准测试

### Tick 延迟测试

```bash
# 监控 tick 延迟
redis-cli --csv XREAD COUNT 100 STREAMS market.tick.binance.btcusdt 0 | \
  grep latency_us | \
  awk -F',' '{print $NF}' | \
  sort -n | \
  awk '{sum+=$1; count++} END {print "平均延迟:", sum/count, "μs"}'
```

**预期结果:** < 1000 μs (1ms)

### Redis 吞吐量测试

```bash
# 测试 Redis 写入性能
redis-benchmark -t set -n 100000 -q

# 预期结果: > 50,000 requests/sec
```

---

## 下一步

验证通过后，可以进行：

1. **实现 Polymarket 适配器** - 添加预测市场支持
2. **开发策略** - 创建自定义交易策略
3. **配置 LLM 层** - 实现新闻分析和权重生成
4. **回测** - 使用历史数据验证策略
5. **实盘测试** - 小资金实盘验证

---

## 持续集成

建议在 CI/CD 流程中添加验证脚本：

```yaml
# .github/workflows/test.yml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      redis:
        image: redis:7.2-alpine
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd nautilus-core
          pip install -r requirements.txt
          pip install -r scripts/requirements-test.txt
      
      - name: Run verification
        run: |
          cd nautilus-core
          python scripts/verify_integration.py
      
      - name: Run unit tests
        run: |
          cd nautilus-core
          pytest tests/ -v
```

---

**最后更新**: 2026-03-23  
**版本**: v1.0.0
