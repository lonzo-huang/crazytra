# MirrorQuant 自动交易系统 - 完整安装指导

本文档提供 MirrorQuant 系统的完整安装和配置指南，包括 Nautilus Trader 整合后的所有组件。

## 目录

- [系统要求](#系统要求)
- [基础设施安装](#基础设施安装)
- [Nautilus 核心安装](#nautilus-核心安装)
- [LLM 层安装](#llm-层安装)
- [API 网关安装（可选）](#api-网关安装可选)
- [前端安装](#前端安装)
- [验证安装](#验证安装)
- [故障排查](#故障排查)

---

## 系统要求

### 硬件要求

- **CPU**: 4 核心以上（推荐 8 核心）
- **内存**: 8GB 以上（推荐 16GB）
- **存储**: 50GB 可用空间（SSD 推荐）
- **网络**: 稳定的互联网连接（低延迟）

### 软件要求

| 组件 | 版本要求 | 用途 |
|------|---------|------|
| Python | 3.11+ | Nautilus 策略层、LLM 层 |
| Rust | 1.79+ | 数据层（已被 Nautilus 替代，但保留用于扩展） |
| Go | 1.22+ | API 网关（可选） |
| Node.js | 18+ | 前端 |
| Redis | 7.2+ | 消息总线 |
| Docker | 20.10+ | 容器化部署（可选） |

---

## 基础设施安装

### 1. 安装 Redis

#### 方式 A: Docker（推荐）

```bash
# 启动 Redis 容器
docker run -d \
  --name mirrorquant-redis \
  -p 6379:6379 \
  -v mirrorquant-redis-data:/data \
  redis:7.2-alpine \
  redis-server --appendonly yes

# 验证 Redis 运行
docker logs mirrorquant-redis
redis-cli ping  # 应返回 PONG
```

#### 方式 B: 本地安装

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Windows:**
```powershell
# 使用 WSL2 + Docker 或下载 Redis for Windows
# https://github.com/microsoftarchive/redis/releases
```

### 2. 验证 Redis

```bash
redis-cli ping
# 输出: PONG

redis-cli INFO server
# 检查版本 >= 7.2
```

---

## Nautilus 核心安装

Nautilus 核心是系统的交易引擎，整合了数据层、策略层、风控层和交易层。

### 1. 克隆项目（如果还没有）

```bash
git clone https://github.com/your-org/MirrorQuant.git
cd MirrorQuant
```

### 2. 安装 Python 依赖

```bash
cd nautilus-core

# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\activate  # Windows

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

**requirements.txt 内容：**
```
nautilus_trader==1.204.0
redis[asyncio]==5.0.1
pandas==2.1.4
pyarrow==14.0.1
pydantic==2.5.3
python-dotenv==1.0.0
structlog==23.2.0
aioredis==2.0.1
```

### 3. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件
nano .env  # 或使用你喜欢的编辑器
```

**最小配置（纸面交易）：**
```bash
# Redis
REDIS_URL=redis://localhost:6379
REDIS_DB=0

# 交易模式
TRADING_MODE=paper

# 纸面交易初始资金
PAPER_INITIAL_CASH=100000

# 日志
LOG_LEVEL=INFO
LOG_DIRECTORY=./logs
```

**完整配置（实盘交易）：**
```bash
# Redis
REDIS_URL=redis://localhost:6379
REDIS_DB=0

# 交易模式
TRADING_MODE=live

# Binance 配置
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_SECRET=your_binance_secret_here
BINANCE_TESTNET=false

# Polymarket 配置
POLYMARKET_API_KEY=your_polymarket_api_key_here
POLYMARKET_WALLET_ADDRESS=0x_your_wallet_address_here

# 风控参数
MAX_POSITION_SIZE=0.20
MAX_DAILY_LOSS=0.05
MAX_DRAWDOWN=0.15

# LLM 配置
LLM_HALF_LIFE_S=1800

# 回测配置
BACKTEST_DATA_PATH=./data
BACKTEST_START=2024-01-01
BACKTEST_END=2024-12-31

# 日志
LOG_LEVEL=INFO
LOG_DIRECTORY=./logs
```

### 4. 验证安装

```bash
# 测试导入
python -c "import nautilus_trader; print(nautilus_trader.__version__)"
# 输出: 1.204.0

# 运行集成测试
pytest tests/test_integration.py -v

# 使用自动化验证脚本（推荐）
# 安装测试依赖
pip install -r scripts/requirements-test.txt

# 运行完整验证
python scripts/verify_integration.py
```

**验证脚本会检查：**
- ✓ Redis 连接和版本
- ✓ Redis Streams 配置
- ✓ Tick 数据格式（价格必须为字符串）
- ✓ LLM 权重消费者组
- ✓ LLM 权重注入流程
- ✓ 订单事件格式

详细测试指南见 [`nautilus-core/TESTING.md`](nautilus-core/TESTING.md)

### 5. 启动 Nautilus 节点

```bash
# 纸面交易模式
python main.py --mode paper

# 应该看到：
# ============================================================
# Nautilus Trading Node Started
# ============================================================
# Trader ID: MIRRORQUANT-001
# Trading Mode: paper
# Redis URL: redis://localhost:6379
# ============================================================
```

---

## LLM 层安装

LLM 层是独立的 Python 进程，负责分析新闻并生成权重向量。

### 1. 安装依赖

```bash
cd ../llm-layer

# 使用相同的虚拟环境或创建新的
pip install -r requirements.txt
```

**requirements.txt 内容：**
```
openai==1.3.0
anthropic==0.7.0
redis[asyncio]==5.0.1
structlog==23.2.0
python-dotenv==1.0.0
httpx==0.25.0
```

### 2. 配置 LLM API Keys

```bash
cp .env.example .env
nano .env
```

**配置示例：**
```bash
# Redis
REDIS_URL=redis://localhost:6379

# OpenAI
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_MODEL=gpt-4o

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-your-claude-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Ollama（本地）
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M

# LLM 路由规则
LLM_DEFAULT_PROVIDER=ollama
LLM_IMPORTANCE_THRESHOLD=0.85  # 超过此阈值使用云端 LLM

# 预算控制
LLM_DAILY_BUDGET_USD=10.0
```

### 3. 安装 Ollama（本地 LLM，可选）

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# 启动 Ollama
ollama serve &

# 下载模型
ollama pull mistral:7b-instruct-q4_K_M
```

### 4. 启动 LLM 层

```bash
python -m llm_layer.main

# 应该看到：
# LLM Layer started
# Default provider: ollama
# Listening on Redis: llm.weight
```

---

## API 网关安装（可选）

如果保留自建 API 网关，按以下步骤安装。如果完全使用 Nautilus，可跳过此部分。

### 1. 安装 Go

```bash
# Ubuntu/Debian
sudo apt install golang-go

# macOS
brew install go

# 验证
go version  # 应 >= 1.22
```

### 2. 安装依赖

```bash
cd ../api-gateway

# 初始化 Go 模块（如果还没有）
go mod init github.com/your-org/mirrorquant/api-gateway

# 下载依赖
go mod download
```

### 3. 配置环境变量

```bash
cp .env.example .env
nano .env
```

**配置示例：**
```bash
REDIS_URL=redis://localhost:6379
API_PORT=8080
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
JWT_SECRET=your-secret-key-here
```

### 4. 启动 API 网关

```bash
go run ./src/main.go

# 应该看到：
# API Gateway started on :8080
# Connected to Redis at redis://localhost:6379
```

---

## 前端安装

### 1. 安装 Node.js 和 npm

```bash
# Ubuntu/Debian
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# macOS
brew install node

# 验证
node --version  # 应 >= 18
npm --version
```

### 2. 安装前端依赖

```bash
cd ../frontend

# 安装依赖
npm install

# 或使用 pnpm（更快）
npm install -g pnpm
pnpm install
```

### 3. 配置环境变量

```bash
cp .env.example .env
nano .env
```

**配置示例：**
```bash
VITE_API_URL=http://localhost:8080
VITE_WS_URL=ws://localhost:8080/ws
```

### 4. 启动开发服务器

```bash
npm run dev

# 应该看到：
# VITE v5.0.0  ready in 500 ms
# ➜  Local:   http://localhost:5173/
# ➜  Network: use --host to expose
```

---

## 验证安装

### 1. 检查所有服务状态

```bash
# Redis
redis-cli ping
# 输出: PONG

# Nautilus 节点
curl http://localhost:8080/health || echo "Nautilus running in terminal"

# LLM 层
redis-cli XINFO GROUPS llm.weight
# 应该看到消费者组

# 前端
curl http://localhost:5173
# 应该返回 HTML
```

### 2. 端到端测试

```bash
cd nautilus-core

# 运行集成测试
pytest tests/test_integration.py -v -s

# 测试 LLM 权重注入
redis-cli XADD llm.weight \* data '{
  "symbol":"BTC-USDT",
  "llm_score":0.6,
  "confidence":0.8,
  "horizon":"short",
  "key_drivers":["Test"],
  "risk_events":[],
  "model_used":"test",
  "ts_ns":1700000000000000000,
  "ttl_ms":300000
}'

# 检查 Nautilus 日志，应该看到：
# LLM weight updated for BTC-USDT: score=0.600
```

### 3. 检查 Redis 数据流

```bash
# 检查 tick 数据
redis-cli XREAD COUNT 1 STREAMS market.tick.binance.btcusdt 0

# 检查订单事件
redis-cli XREAD COUNT 1 STREAMS order.event 0

# 检查 LLM 权重
redis-cli XREAD COUNT 1 STREAMS llm.weight 0
```

---

## 完整启动顺序

### 方式 A: 手动启动（开发模式）

```bash
# 终端 1: Redis
docker run -d -p 6379:6379 redis:alpine

# 终端 2: Nautilus 节点
cd nautilus-core
source venv/bin/activate
python main.py --mode paper

# 终端 3: LLM 层
cd llm-layer
source venv/bin/activate
python -m llm_layer.main

# 终端 4: API 网关（可选）
cd api-gateway
go run ./src/main.go

# 终端 5: 前端
cd frontend
npm run dev
```

### 方式 B: 使用启动脚本

```bash
# 给脚本添加执行权限
chmod +x nautilus-core/scripts/start.sh

# 启动所有服务
./nautilus-core/scripts/start.sh paper
```

### 方式 C: Docker Compose（生产模式）

```bash
# 创建 docker-compose.yml（待实现）
docker-compose up -d
```

---

## 故障排查

### 问题 1: Redis 连接失败

**错误信息：**
```
Error: Cannot connect to Redis at redis://localhost:6379
```

**解决方案：**
```bash
# 检查 Redis 是否运行
redis-cli ping

# 如果没有运行，启动 Redis
docker start mirrorquant-redis
# 或
sudo systemctl start redis-server

# 检查端口是否被占用
netstat -tuln | grep 6379
```

### 问题 2: Nautilus 导入失败

**错误信息：**
```
ModuleNotFoundError: No module named 'nautilus_trader'
```

**解决方案：**
```bash
# 确认虚拟环境已激活
source venv/bin/activate

# 重新安装 Nautilus
pip install --upgrade nautilus_trader==1.204.0

# 检查安装
pip show nautilus_trader
```

### 问题 3: LLM 权重没有注入

**检查清单：**
```bash
# 1. 检查 LLM 层是否运行
ps aux | grep llm_layer

# 2. 检查 Redis stream
redis-cli XREAD COUNT 10 STREAMS llm.weight 0

# 3. 检查消费者组
redis-cli XINFO GROUPS llm.weight

# 4. 检查 Nautilus 日志
tail -f nautilus-core/logs/nautilus.log
```

### 问题 4: 前端无法连接

**检查清单：**
```bash
# 1. 检查 API 网关是否运行
curl http://localhost:8080/health

# 2. 检查 CORS 配置
# 确保 .env 中 CORS_ORIGINS 包含前端地址

# 3. 检查浏览器控制台
# F12 → Console → 查看错误信息
```

### 问题 5: 订单没有执行

**检查清单：**
```bash
# 1. 查看 Nautilus 日志中的 OrderRejected 事件
grep "OrderRejected" nautilus-core/logs/nautilus.log

# 2. 检查风控配置
cat nautilus-core/.env | grep MAX_

# 3. 检查账户余额（纸面交易）
redis-cli GET account:paper:balance

# 4. 检查仓位限制
redis-cli HGETALL position:BTC-USDT
```

---

## 生产环境部署建议

### 1. 使用 systemd 服务（Linux）

创建 `/etc/systemd/system/mirrorquant-nautilus.service`：

```ini
[Unit]
Description=MirrorQuant Nautilus Trading Node
After=network.target redis.service

[Service]
Type=simple
User=mirrorquant
WorkingDirectory=/opt/mirrorquant/nautilus-core
Environment="PATH=/opt/mirrorquant/venv/bin"
ExecStart=/opt/mirrorquant/venv/bin/python main.py --mode live
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable mirrorquant-nautilus
sudo systemctl start mirrorquant-nautilus
sudo systemctl status mirrorquant-nautilus
```

### 2. 使用 Docker（推荐）

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY nautilus-core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY nautilus-core/ .

CMD ["python", "main.py", "--mode", "live"]
```

构建和运行：
```bash
docker build -t mirrorquant-nautilus .
docker run -d \
  --name mirrorquant-nautilus \
  --env-file nautilus-core/.env \
  --network host \
  mirrorquant-nautilus
```

### 3. 监控和日志

```bash
# 使用 Prometheus + Grafana 监控
# 使用 ELK Stack 或 Loki 收集日志
# 配置告警（PagerDuty / Slack）
```

---

## 下一步

- 阅读 [QUICKSTART.md](nautilus-core/QUICKSTART.md) 快速开始
- 查看 [ARCHITECTURE.md](ARCHITECTURE.md) 了解系统架构
- 参考 [SYSTEM_SPEC.md](SYSTEM_SPEC.md) 了解开发规范
- 学习 [nautilus-core/README.md](nautilus-core/README.md) 开发策略

---

## 获取帮助

- **文档**: [完整文档目录](README.md)
- **示例**: [examples/](examples/)
- **问题**: [GitHub Issues](https://github.com/your-org/MirrorQuant/issues)
- **社区**: [Discord / Telegram]

---

**最后更新**: 2026-03-23  
**版本**: v1.0.0 (Nautilus 整合版)
