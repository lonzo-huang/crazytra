# Crazytra - 智能自动交易系统

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-1.79+-orange.svg)](https://www.rust-lang.org/)
[![Go](https://img.shields.io/badge/Go-1.22+-00ADD8.svg)](https://golang.org/)
[![Nautilus](https://img.shields.io/badge/Nautilus-1.204.0-green.svg)](https://nautilustrader.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

全栈自动交易系统，整合 **Nautilus Trader** 核心引擎，支持多市场、多策略、**LLM 情感增强**的智能交易。

## ✨ 核心特性

- 🚀 **Nautilus Trader 整合** - 专业级交易引擎，回测=实盘
- 🤖 **LLM 增强** - 实时新闻分析，权重注入策略
- 📊 **多市场支持** - Binance、Polymarket、Trading212、Tiger
- 🛡️ **智能风控** - 熔断器、仓位管理、Kelly 定仓
- 🎯 **双模式** - 纸面交易模拟 + 实盘执行
- 📈 **实时前端** - React + WebSocket 实时看板

## 🏗️ 技术架构

**Nautilus 整合后的架构：**

| 原有组件 | 整合后 | 语言 | 说明 |
|---------|--------|------|------|
| Rust 数据层 | **Nautilus DataEngine** | Rust | 高性能数据引擎 |
| Python 策略层 | **Nautilus Strategy + CrazytraStrategy** | Python | LLM 权重支持 |
| Go 风控层 | **Nautilus RiskEngine** (可选) | Go | 风控引擎 |
| Go 交易层 | **Nautilus ExecutionEngine** | Go | 执行引擎 |
| Redis Streams | **保留** | - | 桥接外部系统 |
| LLM 层 | **独立进程** | Python | 新闻分析 |
| API 网关 | **保留** | Go | REST/WebSocket |
| 前端 | **不变** | React | 实时 UI |

## 🚀 快速启动

### 5 分钟快速开始

```bash
# 1. 启动 Redis
docker run -d -p 6379:6379 --name crazytra-redis redis:alpine

# 2. 安装 Nautilus 核心
cd nautilus-core
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 设置 TRADING_MODE=paper

# 4. 启动 Nautilus 节点（纸面交易）
python main.py --mode paper

# 5. 运行验证（新终端）
python scripts/verify_integration.py
```

详细安装指南见 [INSTALLATION.md](INSTALLATION.md)

### 完整系统启动

```bash
# 终端 1: Redis
docker run -d -p 6379:6379 redis:alpine

# 终端 2: Nautilus 核心
cd nautilus-core && python main.py --mode paper

# 终端 3: LLM 层（可选）
cd llm-layer && python -m llm_layer.main

# 终端 4: API 网关（可选）
cd api-gateway && go run ./src/main.go

# 终端 5: 前端
cd frontend && npm run dev
```

## 环境变量

复制 `.env.example` 为 `.env` 并填写：

```bash
cp .env.example .env
```

## 📁 项目结构

```
Crazytra/
├── nautilus-core/           # ⭐ Nautilus Trader 核心（新增）
│   ├── actors/              # RedisBridgeActor, LLMWeightActor
│   ├── strategies/          # CrazytraStrategy 基类 + 示例策略
│   ├── scripts/             # 验证和启动脚本
│   ├── tests/               # 集成测试
│   ├── main.py              # 主入口
│   ├── config.py            # Nautilus 配置
│   ├── README.md            # 详细文档
│   ├── QUICKSTART.md        # 快速开始
│   └── TESTING.md           # 测试指南
├── data-layer/              # Rust - 数据获取（保留用于扩展）
├── llm-layer/               # Python - LLM 独立进程
├── api-gateway/             # Go - API 网关（可选）
├── frontend/                # React+Vite - 前端
├── ARCHITECTURE.md          # 架构文档（已更新 Nautilus 整合）
├── SYSTEM_SPEC.md           # 系统规范
├── QUICK_REF.md             # 快速参考
├── TASK_PROMPTS.md          # AI 工具任务模板
├── INSTALLATION.md          # 完整安装指南
└── README.md                # 本文件
```
