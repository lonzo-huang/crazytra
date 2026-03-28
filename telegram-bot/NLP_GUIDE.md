# 自然语言命令指南

Telegram Bot 现在支持**自然语言命令**！你可以用人类语言控制交易系统，无需记忆复杂的命令格式。

## 🎯 工作原理

```
你的消息
    ↓
Telegram Bot
    ↓
Ollama LLM (本地)
    ↓
命令意图解析
    ↓
执行交易操作
    ↓
返回结果
```

## 💬 支持的自然语言命令

### 1. 查询类命令

**查询账户状态**
```
• 查看我的账户状态
• 账户怎么样了
• 我的账户情况
• 显示账户信息
```

**查询持仓**
```
• 查看持仓
• 我现在有什么仓位
• 显示所有持仓
• 当前持仓情况
```

**查询价格**
```
• BTC 现在多少钱？
• 查询 ETH-USDT 的价格
• SOL 的实时价格
• 告诉我 BTC-USDT 现在的价格
```

**查询盈亏**
```
• 查看盈亏
• 我赚了多少钱
• 今天的盈亏情况
• 显示盈亏报告
```

**查询交易历史**
```
• 查看最近的交易
• 显示交易历史
• 我最近做了哪些交易
• 最近的成交记录
```

### 2. 交易控制命令

**平仓**
```
• 平掉 BTC 的仓位
• 关闭 ETH-USDT 的持仓
• 平掉 BTC-USDT
• 清空 SOL 仓位
```

**平掉所有仓位**
```
• 平掉所有仓位
• 清空所有持仓
• 全部平仓
• 关闭所有仓位
```

**暂停交易**
```
• 暂停交易
• 停止所有交易
• 暂停自动交易
• 不要再交易了
```

**恢复交易**
```
• 恢复交易
• 继续交易
• 开始交易
• 重新开始自动交易
```

### 3. 策略控制命令

**启用策略**
```
• 启用 ma_cross 策略
• 开启均线策略
• 激活 momentum 策略
• 打开 ma_cross_llm 策略
```

**禁用策略**
```
• 禁用 ma_cross 策略
• 关闭均线策略
• 停止 momentum 策略
• 暂停 ma_cross_llm 策略
```

## 🤖 LLM 解析示例

### 示例 1: 查询价格

**你说**：
```
BTC 现在多少钱？
```

**LLM 理解为**：
```json
{
  "action": "QUERY_PRICE",
  "parameters": {
    "symbol": "BTC-USDT"
  },
  "confidence": 0.95,
  "response": "正在查询 BTC-USDT 的价格..."
}
```

**Bot 回复**：
```
💰 BTC-USDT 实时价格

价格: $67,840.50
```

### 示例 2: 平仓

**你说**：
```
帮我平掉 ETH 的仓位
```

**LLM 理解为**：
```json
{
  "action": "CLOSE_POSITION",
  "parameters": {
    "symbol": "ETH-USDT"
  },
  "confidence": 0.92,
  "response": "正在平仓 ETH-USDT..."
}
```

**Bot 回复**：
```
✅ 已发送平仓指令：ETH-USDT
```

### 示例 3: 策略控制

**你说**：
```
启用均线交叉策略
```

**LLM 理解为**：
```json
{
  "action": "ENABLE_STRATEGY",
  "parameters": {
    "strategy": "ma_cross"
  },
  "confidence": 0.88,
  "response": "正在启用策略..."
}
```

**Bot 回复**：
```
✅ 已启用策略：ma_cross
```

## 🎯 置信度机制

Bot 会评估对你意图的理解程度：

- **≥ 90%**: 非常确定，直接执行
- **60-90%**: 比较确定，执行并告知
- **< 60%**: 不确定，要求确认

**低置信度示例**：

**你说**：
```
那个东西怎么样了
```

**Bot 回复**：
```
⚠️ 我不太确定您的意思（置信度: 45%）

抱歉，我无法理解这个命令。
请尝试更具体的描述，例如：
• 查看账户状态
• 查看持仓
• BTC 现在多少钱
```

## 🔒 安全机制

### 1. 重要操作确认

对于高风险操作，Bot 会要求二次确认：

**你说**：
```
平掉所有仓位
```

**Bot 回复**：
```
⚠️ 这是一个重要操作！

您确定要平掉所有仓位吗？
这将关闭：
• BTC-USDT: 0.1 BTC
• ETH-USDT: 2.5 ETH
• SOL-USDT: 100 SOL

回复 "确认" 继续，或 "取消" 放弃
```

### 2. 操作日志

所有通过 Telegram 执行的操作都会记录：

```json
{
  "timestamp_ns": 1700000000000000000,
  "source": "telegram",
  "user_id": 123456789,
  "action": "CLOSE_POSITION",
  "parameters": {"symbol": "BTC-USDT"},
  "confidence": 0.95
}
```

### 3. 权限控制

只有配置的 `TELEGRAM_CHAT_ID` 可以控制系统。

## 🚀 使用技巧

### 1. 明确具体

❌ **模糊**：
```
那个怎么样了
```

✅ **清晰**：
```
查看 BTC-USDT 的持仓情况
```

### 2. 使用标准符号

✅ **推荐**：
```
BTC-USDT
ETH-USDT
SOL-USDT
```

⚠️ **也可以**：
```
BTC
比特币
以太坊
```

### 3. 一次一个命令

✅ **好**：
```
查看账户状态
```

❌ **不好**：
```
查看账户状态然后平掉BTC再启用策略
```

## 📊 命令执行流程

```
1. 你发送消息
   ↓
2. Bot 显示 "🤔 正在理解您的指令..."
   ↓
3. Ollama LLM 解析意图（1-3秒）
   ↓
4. 检查置信度
   ↓
5. 执行命令
   ↓
6. 返回结果
```

## 🔧 配置要求

确保以下服务正在运行：

1. **Ollama** - LLM 服务
   ```bash
   docker-compose up -d ollama
   ```

2. **Telegram Bot** - 带 NLP 支持
   ```bash
   docker-compose --profile telegram up -d
   ```

3. **Redis** - 消息总线
   ```bash
   docker-compose up -d redis
   ```

## 📝 环境变量

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# Ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M
```

## 🎨 支持的语言

目前支持：
- ✅ 中文
- ✅ 英文
- ✅ 中英混合

示例：
```
• 查看账户状态 ✓
• Show account status ✓
• 查看 BTC price ✓
```

## 🐛 故障排查

### 问题 1: Bot 无响应

**检查**：
```bash
# 查看日志
docker logs mirrorquant-telegram-bot

# 检查 Ollama
curl http://localhost:11434/api/tags
```

### 问题 2: 理解错误

**解决**：
- 使用更明确的表述
- 包含完整的交易对名称
- 避免使用代词（"它"、"那个"）

### 问题 3: 响应慢

**原因**：
- Ollama 首次加载模型需要时间
- GPU 加速未启用

**优化**：
```bash
# 预加载模型
docker exec -it mirrorquant-ollama ollama run mistral:7b-instruct-q4_K_M
```

## 🎯 最佳实践

1. **清晰表达**：使用完整的交易对名称
2. **耐心等待**：LLM 解析需要 1-3 秒
3. **检查结果**：确认 Bot 理解正确
4. **使用快捷命令**：频繁操作用 `/status` 等命令更快

## 🔮 未来功能

计划添加：
- 🔄 多轮对话（上下文记忆）
- 📊 复杂查询（"过去一周的盈亏"）
- 🎯 条件执行（"如果 BTC 跌破 60000 就平仓"）
- 🤝 多用户支持
- 🌐 更多语言支持

## 💡 示例对话

```
你: 早上好，查看一下账户
Bot: 💼 账户状态
     总资产: $105,680.50
     可用余额: $45,230.00
     今日盈亏: +$1,250.00 (+1.2%)

你: BTC 现在多少钱
Bot: 💰 BTC-USDT 实时价格
     价格: $67,840.50

你: 如果涨到 70000 提醒我
Bot: ✅ 已设置价格提醒
     BTC-USDT >= $70,000.00

你: 平掉 ETH 的仓位
Bot: ✅ 已发送平仓指令：ETH-USDT

你: 暂停所有交易
Bot: ⏸️ 已暂停所有交易
```

享受自然语言交易控制！🚀
