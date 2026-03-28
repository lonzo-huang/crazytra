# Telegram Bot 快速开始指南

## 📱 第一步：创建 Telegram Bot

### 1. 找到 BotFather

在 Telegram 中搜索 `@BotFather` 或访问：https://t.me/botfather

### 2. 创建新机器人

发送命令：
```
/newbot
```

### 3. 设置机器人信息

按提示输入：
- **机器人名称**（显示名称）：例如 `MirrorQuant Trading Bot`
- **机器人用户名**（必须以 bot 结尾）：例如 `mirrorquant_trading_bot`

### 4. 获取 Token

BotFather 会返回类似这样的消息：
```
Done! Congratulations on your new bot.
You will find it at t.me/mirrorquant_trading_bot
You can now add a description...

Use this token to access the HTTP API:
123456789:ABCdefGHIjklMNOpqrsTUVwxyz

For a description of the Bot API, see this page:
https://core.telegram.org/bots/api
```

**保存这个 Token！** 这就是你的 `TELEGRAM_BOT_TOKEN`

## 📋 第二步：获取 Chat ID

### 方法 1：使用 userinfobot

1. 在 Telegram 中搜索 `@userinfobot`
2. 点击 Start 或发送任意消息
3. Bot 会返回你的信息，包括 Chat ID

```
Id: 123456789
First name: Your Name
```

**保存这个 Id！** 这就是你的 `TELEGRAM_CHAT_ID`

### 方法 2：使用 API 获取

1. 先向你的 Bot 发送一条消息（例如 `/start`）
2. 访问以下 URL（替换 YOUR_BOT_TOKEN）：

```
https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
```

3. 在返回的 JSON 中找到 `chat.id`：

```json
{
  "message": {
    "chat": {
      "id": 123456789,
      "first_name": "Your Name"
    }
  }
}
```

## ⚙️ 第三步：配置环境变量

编辑 `.env` 文件：

```bash
# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
TELEGRAM_ENABLE=true
```

## 🚀 第四步：启动服务

### 使用 Docker Compose（推荐）

```bash
# 启动所有服务（包括 Telegram Bot）
docker-compose --profile telegram up -d

# 或者只启动 Telegram Bot
docker-compose up -d telegram-bot
```

### 本地运行

```bash
cd telegram-bot

# 安装依赖
go mod download

# 运行
export TELEGRAM_BOT_TOKEN=your_token
export TELEGRAM_CHAT_ID=your_chat_id
export REDIS_URL=localhost:6379
go run main.go
```

## ✅ 第五步：测试

### 1. 检查启动消息

启动后，你应该会收到：
```
🤖 MirrorQuant 交易机器人已启动

准备接收交易通知...
```

### 2. 测试命令

向 Bot 发送以下命令：

```
/start    - 查看欢迎消息
/status   - 查看账户状态
/positions - 查看当前持仓
/report   - 生成交易报告
/help     - 查看帮助
```

### 3. 模拟通知

如果想测试通知功能，可以手动向 Redis 发送测试数据：

```bash
# 连接到 Redis
redis-cli

# 发送测试订单事件
XADD order.event * order_id test123 symbol BTC-USDT side BUY status FILLED price 67840.50 quantity 0.1 filled_qty 0.1 timestamp_ns 1700000000000000000

# 发送测试风险告警
XADD risk.alert * alert_type DAILY_LOSS_LIMIT severity CRITICAL message "日损失超过限制" symbol BTC-USDT value -5.2 threshold -5.0 timestamp_ns 1700000000000000000
```

## 🔧 故障排查

### 问题 1: 收不到启动消息

**原因**: 
- Token 或 Chat ID 错误
- 没有先向 Bot 发送 `/start`

**解决**:
1. 在 Telegram 中找到你的 Bot
2. 点击 Start 或发送 `/start`
3. 重启 Telegram Bot 服务

### 问题 2: Bot 无响应

**检查**:
```bash
# 查看日志
docker logs mirrorquant-telegram-bot

# 检查 Redis 连接
docker exec -it mirrorquant-redis redis-cli ping
```

### 问题 3: 消息格式错误

**原因**: Redis 数据格式不正确

**解决**: 检查发送到 Redis 的数据是否符合预期格式

## 📊 通知示例

### 订单成交通知

当订单成交时，你会收到：

```
✅ 订单成交

🟢 BTC-USDT BUY
价格: $67,840.50
数量: 0.1000
成交: 0.1000
订单ID: order_abc123
```

### 风险告警

当触发风险规则时：

```
🚨 风险告警

类型: DAILY_LOSS_LIMIT
级别: CRITICAL
消息: 日损失超过限制
交易对: BTC-USDT
当前值: -5.20
阈值: -5.00
```

### 每日报告

每天早上 8:00 自动发送：

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
```

## 🔐 安全建议

1. **保护 Token**
   - 不要在公开场合分享
   - 不要提交到 Git
   - 使用环境变量

2. **限制访问**
   - 只向特定 Chat ID 发送
   - 考虑使用私有 Bot
   - 定期更换 Token

3. **监控使用**
   - 检查异常登录
   - 监控消息发送量
   - 定期审计日志

## 📱 高级配置

### 自定义通知频率

编辑 `main.go` 中的限流设置：

```go
notifyInterval := time.Minute * 5  // 改为你想要的间隔
```

### 自定义消息格式

编辑消息模板函数：
- `handleOrderEvent` - 订单通知
- `handleRiskAlert` - 风险告警
- `handlePositionUpdate` - 持仓更新

### 添加新命令

在 `handleCommands` 函数中添加：

```go
case "mycommand":
    tb.sendMessage("自定义响应")
```

## 🎯 下一步

- ✅ 配置完成后，Bot 会自动接收所有交易通知
- ✅ 每天早上 8:00 收到交易日报
- ✅ 使用命令随时查询账户状态
- ✅ 重要风险告警实时推送

享受自动化交易通知！📱✨
