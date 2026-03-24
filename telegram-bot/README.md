# Telegram Bot - 交易通知服务

Telegram Bot 服务用于实时推送交易通知、风险告警和每日报告。

## 功能特性

### 📨 实时通知

- **订单通知**
  - ✅ 订单成交通知
  - ⏳ 部分成交通知
  - ❌ 订单取消通知
  - 🚫 订单拒绝通知

- **风险告警**
  - 🚨 严重告警（CRITICAL）
  - ⚠️ 高级告警（HIGH）
  - ⚡ 中级告警（MEDIUM）
  - ℹ️ 信息告警（INFO）

- **持仓更新**
  - 📈 盈利持仓
  - 📉 亏损持仓
  - 📊 持仓变化

### 📊 每日报告

每天早上 8:00 自动发送：
- 今日交易统计
- 盈亏汇总
- 策略表现
- 风险指标

### 🤖 交互命令

- `/start` - 启动机器人
- `/status` - 查看账户状态
- `/positions` - 查看当前持仓
- `/report` - 生成交易报告
- `/help` - 帮助信息

## 快速开始

### 1. 创建 Telegram Bot

1. 在 Telegram 中找到 [@BotFather](https://t.me/botfather)
2. 发送 `/newbot` 创建新机器人
3. 按提示设置机器人名称和用户名
4. 获取 Bot Token（格式：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 2. 获取 Chat ID

1. 在 Telegram 中找到 [@userinfobot](https://t.me/userinfobot)
2. 发送任意消息
3. 获取你的 Chat ID（数字格式）

### 3. 配置环境变量

```bash
# Telegram 配置
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Redis 配置
REDIS_URL=redis:6379
```

### 4. 运行服务

**使用 Docker:**
```bash
docker build -t crazytra-telegram-bot .
docker run -d \
  --name telegram-bot \
  -e TELEGRAM_BOT_TOKEN=your_token \
  -e TELEGRAM_CHAT_ID=your_chat_id \
  -e REDIS_URL=redis:6379 \
  crazytra-telegram-bot
```

**本地运行:**
```bash
go mod download
go run main.go
```

## 消息格式

### 订单成交通知

```
✅ 订单成交

🟢 BTC-USDT BUY
价格: $67,840.50
数量: 0.1000
成交: 0.1000
订单ID: order_abc123
```

### 风险告警

```
🚨 风险告警

类型: DAILY_LOSS_LIMIT
级别: CRITICAL
消息: 日损失超过限制
交易对: BTC-USDT
当前值: -5.2%
阈值: -5.0%
```

### 持仓更新

```
📈 持仓更新

🟢 BTC-USDT LONG
数量: 0.1000
入场价: $67,500.00
当前价: $67,840.50
未实现盈亏: $34.05
已实现盈亏: $120.50
```

### 每日报告

```
📊 每日交易报告

日期: 2026-03-24

📈 今日统计
总交易次数: 25
盈利交易: 15
亏损交易: 10
胜率: 60%

💰 盈亏统计
今日盈亏: $1,250.00
累计盈亏: $5,680.00
最大回撤: -3.2%

🎯 策略表现
ma_cross_llm: 12次 胜率65%
momentum: 8次 胜率55%
mean_reversion: 5次 胜率60%
```

## 数据流

```
Redis Streams
    ↓
order.event → 订单通知
risk.alert → 风险告警
position.update → 持仓更新
account.state → 账户状态
    ↓
Telegram Bot
    ↓
Telegram API
    ↓
你的手机 📱
```

## 订阅的 Redis Streams

| Stream | 消费者组 | 用途 |
|--------|---------|------|
| `order.event` | telegram-bot-cg | 订单成交通知 |
| `risk.alert` | telegram-bot-cg | 风险告警 |
| `position.update` | telegram-bot-cg | 持仓更新 |
| `account.state` | telegram-bot-cg | 账户状态 |

## 通知频率控制

为避免消息轰炸，实现了以下限流机制：

- **持仓更新**: 每个交易对 5 分钟最多通知 1 次
- **订单事件**: 仅通知重要状态（成交、取消、拒绝）
- **风险告警**: 实时通知，无限流
- **每日报告**: 每天 8:00 发送一次

## 安全建议

1. **保护 Bot Token**
   - 不要泄露 Token
   - 使用环境变量
   - 定期更换 Token

2. **限制访问**
   - 只向特定 Chat ID 发送消息
   - 不要公开 Bot 用户名
   - 考虑使用私有 Bot

3. **监控日志**
   - 检查异常登录
   - 监控消息发送失败
   - 定期审计

## 故障排查

### 问题 1: Bot 无法发送消息

**检查**:
1. Token 是否正确
2. Chat ID 是否正确
3. 是否先向 Bot 发送过 `/start`

### 问题 2: 收不到通知

**检查**:
1. Redis 连接是否正常
2. Stream 是否有数据
3. 消费者组是否正确创建

### 问题 3: 消息格式错误

**检查**:
1. Redis 数据格式是否正确
2. JSON 解析是否成功
3. 查看日志错误信息

## 开发指南

### 添加新的通知类型

1. 定义数据结构
2. 创建订阅函数
3. 实现消息处理
4. 添加消息格式化

### 自定义消息格式

编辑 `handleOrderEvent`、`handleRiskAlert` 等函数中的消息模板。

### 添加新命令

在 `handleCommands` 函数中添加新的 case 分支。

## 依赖

- `github.com/go-telegram-bot-api/telegram-bot-api/v5` - Telegram Bot API
- `github.com/redis/go-redis/v9` - Redis 客户端
- `github.com/shopspring/decimal` - 精确数值计算
- `go.uber.org/zap` - 结构化日志

## 许可证

MIT License
