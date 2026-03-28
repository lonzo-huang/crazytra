# LLM 层 - 新闻情感分析与权重生成

LLM 层是一个独立的 Python 进程，负责分析加密货币新闻并生成权重向量，供策略层使用。

## 功能特性

- ✅ **多 LLM 提供商路由**：Ollama (本地) / OpenAI / Anthropic
- ✅ **智能缓存**：3 分钟 TTL，避免重复分析
- ✅ **新闻聚合**：RSS + NewsAPI
- ✅ **时间衰减融合**：30 分钟半衰期
- ✅ **重大新闻检测**：自动切换到云端 LLM
- ✅ **Redis 发布**：发布到 `llm.weight` stream

## 架构

```
新闻源 (RSS + NewsAPI)
    ↓ 聚合和去重
新闻筛选 (关键词匹配)
    ↓ 重要性评分
LLM 分析 (Ollama/Claude/GPT-4o)
    ↓ 情感评分
时间衰减融合 (30min 半衰期)
    ↓ 权重向量
Redis Stream (llm.weight)
    ↓ 消费
Nautilus LLMWeightActor
    ↓ 注入
MirrorQuantStrategy
```

## 快速开始

### 1. 安装依赖

```bash
cd llm-layer
pip install -e .
```

### 2. 配置环境变量

```bash
# 必需：Redis 连接
export REDIS_URL="redis://localhost:6379"

# 可选：Ollama (本地 LLM)
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="mistral:7b-instruct-q4_K_M"

# 可选：云端 LLM (用于重大新闻)
export ANTHROPIC_API_KEY="your_api_key"
export OPENAI_API_KEY="your_api_key"

# 可选：NewsAPI (提高新闻质量)
export NEWSAPI_KEY="your_api_key"

# 可选：调整参数
export LLM_INTERVAL_S="300"        # 常规分析间隔（秒）
export BREAKING_THRESHOLD="0.85"   # 重大新闻阈值
```

### 3. 启动 Ollama (本地 LLM)

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 拉取模型
ollama pull mistral:7b-instruct-q4_K_M

# 启动服务
ollama serve
```

### 4. 运行 LLM 层

```bash
cd llm-layer
python -m llm_layer.main
```

## 工作流程

### 常规分析循环 (每 5 分钟)

1. **新闻聚合**：从 RSS 和 NewsAPI 获取最新新闻
2. **筛选和评分**：
   - 过滤 4 小时内的新闻
   - 关键词匹配（BTC, ETH 等）
   - 重要性评分（来源权重 + 高影响关键词）
3. **LLM 分析**：
   - 使用 Ollama 本地分析（成本为 0）
   - 返回情感评分 [-1.0, 1.0]
4. **时间衰减融合**：
   - 与历史权重融合（30 分钟半衰期）
   - 平滑权重变化
5. **发布到 Redis**：
   - Topic: `llm.weight`
   - 格式: JSON

### 重大新闻检测 (每 30 秒)

1. **监控新闻重要性**
2. **触发条件**：
   - 重要性 >= 0.85
   - 距离上次重大新闻 > 60 秒
3. **自动切换**：
   - 使用云端 LLM (Claude/GPT-4o)
   - 更准确的分析

## LLM 提供商路由

### 优先级策略

```python
# 常规分析
1. Ollama (本地，免费)
2. Anthropic Claude (备用)
3. OpenAI GPT-4o (备用)

# 重大新闻
1. Anthropic Claude (优先)
2. OpenAI GPT-4o (备用)
3. Ollama (最后备用)
```

### 健康检查

提供商被标记为不健康的条件：
- 连续失败 3 次且最后失败 < 60 秒
- 超出预算限制

### 成本控制

```python
# 默认预算
Anthropic: $30/月
OpenAI: $20/月

# 估算成本
Claude Sonnet: ~$0.003/1k tokens (输入) + $0.015/1k tokens (输出)
GPT-4o: ~$0.005/1k tokens (输入) + $0.015/1k tokens (输出)
Ollama: $0 (本地)
```

## 输出格式

### Redis 消息格式

```json
{
  "symbol": "BTC-USDT",
  "llm_score": 0.45,
  "confidence": 0.75,
  "horizon": "short",
  "key_drivers": ["ETF approval", "Fed rate decision"],
  "risk_events": ["SEC investigation"],
  "model_used": "anthropic/claude-sonnet-4-6",
  "ts_ns": 1704067200000000000,
  "ttl_ms": 300000
}
```

### 字段说明

| 字段 | 类型 | 范围 | 说明 |
|------|------|------|------|
| `symbol` | string | - | 标的符号 (BTC-USDT) |
| `llm_score` | float | [-1.0, 1.0] | 情感评分 |
| `confidence` | float | [0.0, 1.0] | 置信度 |
| `horizon` | string | short/medium/long | 时间范围 |
| `key_drivers` | array | - | 关键驱动因素 |
| `risk_events` | array | - | 风险事件 |
| `model_used` | string | - | 使用的模型 |
| `ts_ns` | int | - | 时间戳（纳秒） |
| `ttl_ms` | int | - | 有效期（毫秒） |

## 新闻源配置

### RSS 源

```python
RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://cryptopanic.com/news/rss/",
]
```

### 关键词映射

```python
SYMBOL_KEYWORDS = {
    "BTC-USDT": ["bitcoin", "btc", "crypto", "fed", "inflation", "etf"],
    "ETH-USDT": ["ethereum", "eth", "defi", "gas", "staking"],
}
```

### 高影响关键词

```python
HIGH_IMPACT = [
    "fed", "fomc", "rate", "sec", "ban", "hack", 
    "etf", "bankruptcy", "fraud", "acquisition", 
    "partnership", "liquidation"
]
```

## 时间衰减融合

### 公式

```python
# 衰减权重
decay = exp(-age_seconds * ln(2) / half_life_seconds)

# 融合评分
merged_score = (new_score * new_confidence + Σ(old_score * old_confidence * decay)) 
               / (new_confidence + Σ(old_confidence * decay))
```

### 参数

- **半衰期**：30 分钟（可配置）
- **历史记录**：保留最近 10 条
- **目的**：平滑权重变化，避免剧烈波动

## 市场状态调整

```python
# risk_on (风险偏好)
if score > 0:  # 看涨
    score *= 1.1  # 增强 10%
else:          # 看跌
    score *= 0.9  # 减弱 10%

# risk_off (风险厌恶)
if score > 0:  # 看涨
    score *= 0.9  # 减弱 10%
else:          # 看跌
    score *= 1.1  # 增强 10%
```

## 监控和日志

### 日志示例

```
2024-01-01T10:00:00 [info] llm_layer_starting
2024-01-01T10:00:05 [info] news_fetched count=12
2024-01-01T10:00:10 [info] llm_ok provider=ollama/mistral:7b ms=2340 tag=sentiment
2024-01-01T10:00:10 [info] weight_published symbol=BTC-USDT score=0.45 model=ollama/mistral:7b drivers=['ETF approval', 'Fed rate']
2024-01-01T10:00:10 [info] cycle_done regime=risk_on scores={'BTC-USDT': 0.45, 'ETH-USDT': 0.32}
```

### 关键指标

- `news_fetched`: 获取的新闻数量
- `llm_ok`: LLM 调用成功（延迟）
- `weight_published`: 权重发布
- `cycle_done`: 分析周期完成

## 故障排查

### 问题：Ollama 连接失败

```
provider_failed provider=ollama/mistral:7b err=Connection refused
```

**解决方案**：
1. 检查 Ollama 是否运行：`ollama list`
2. 检查端口：`curl http://localhost:11434/api/tags`
3. 调整 `OLLAMA_BASE_URL`

### 问题：所有提供商失败

```
RuntimeError: All providers failed
```

**解决方案**：
1. 检查网络连接
2. 验证 API 密钥
3. 检查预算限制

### 问题：JSON 解析失败

```
json_parse_fail raw=...
```

**解决方案**：
1. 检查 LLM 输出格式
2. 调整 `temperature` 参数
3. 使用更可靠的模型

### 问题：没有新闻

```
news_fetched count=0
```

**解决方案**：
1. 检查 RSS 源可用性
2. 调整 `max_age_h` 参数
3. 添加 NewsAPI 密钥

## 性能优化

### 缓存策略

- **TTL**: 3 分钟
- **键**: SHA256(system_prompt + user_prompt)[:16]
- **命中率**: 通常 30-50%

### 并发控制

```python
# RSS 源并发获取
tasks = [self._rss(url) for url in RSS_FEEDS]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 速率限制

```python
# 提供商配置
max_rpm: int = 60  # 每分钟最大请求数
```

## 扩展开发

### 添加新的 LLM 提供商

```python
class MyProvider(BaseProvider):
    @property
    def provider_id(self) -> str:
        return "my_provider/model_name"
    
    def estimate_cost(self, req: LLMRequest) -> float:
        return 0.001  # 每次请求成本
    
    async def complete(self, req: LLMRequest) -> LLMResponse:
        # 实现 API 调用
        pass
```

### 添加新的新闻源

```python
async def _my_news_source(self) -> list[NewsItem]:
    # 实现新闻获取
    return [NewsItem(...)]

# 在 fetch() 中添加
tasks.append(self._my_news_source())
```

### 自定义评分逻辑

```python
def _score(self, items: list[NewsItem]) -> list[NewsItem]:
    for item in items:
        # 自定义评分逻辑
        item.importance = my_scoring_function(item)
    return items
```

## 生产部署

### Docker 部署

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY llm-layer/ .
RUN pip install -e .

CMD ["python", "-m", "llm_layer.main"]
```

### 环境变量

```bash
# .env
REDIS_URL=redis://redis:6379
OLLAMA_BASE_URL=http://ollama:11434
ANTHROPIC_API_KEY=sk-ant-...
NEWSAPI_KEY=...
LLM_INTERVAL_S=300
```

### 健康检查

```bash
# 检查 Redis 连接
redis-cli -u $REDIS_URL PING

# 检查 LLM 层日志
docker logs llm-layer

# 检查权重发布
redis-cli -u $REDIS_URL XLEN llm.weight
```

## 参考资料

- [Ollama 文档](https://ollama.com/docs)
- [Anthropic API](https://docs.anthropic.com)
- [OpenAI API](https://platform.openai.com/docs)
- [NewsAPI](https://newsapi.org/docs)
- [Redis Streams](https://redis.io/docs/data-types/streams/)
