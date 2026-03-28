# MirrorQuant 项目上下文（用于 Windsurf 记忆）

## 🎯 项目概述

**MirrorQuant** 是一个专业级量化交易平台，采用三层事件驱动架构。

---

## 🏗️ 核心架构

### 三层架构
```
第一层: MirrorQuant 平台层
  - StrategyEngine (策略引擎)
  - RiskEngine (风控引擎)
  - ExecutionEngine (执行引擎)
  - LLMWeightActor (LLM 权重生成)

第二层: Redis Streams 事件总线
  - market.tick.{exchange}.{symbol}
  - order.request.{accountId}
  - order.event.{accountId}
  - position.update.{accountId}
  - llm.weight.{strategyId}

第三层: NautilusTrader Runner (执行后端)
  - 订阅订单请求
  - 执行交易
  - 发布订单事件
```

---

## 🔑 关键技术决策

### 1. NT → MQ 数据流
- ❌ **不能**直接使用 NT 的内部数据结构
- ✅ **必须**通过桥接层转换为 MQ Tick JSON
- ✅ **必须**通过 Redis Streams 发布
- ✅ MQ StrategyEngine 只订阅 Redis，不依赖 NT

### 2. MQ Tick 标准格式
- 跨语言（Python/Rust/Go/JS/LLM）
- 可扩展（新字段不破坏现有系统）
- 多租户（Redis 命名空间隔离）
- 低延迟（~13ms 端到端）

### 3. 桥接层设计
```
Polymarket WS → NT Connector → 桥接层 → MQ Tick JSON → Redis → MQ
```

---

## 📁 核心文件位置

### 架构文档
- `ARCHITECTURE.md` - 三层架构设计
- `NT_TO_MQ_BRIDGE.md` - 桥接层设计
- `BRIDGE_LAYER_SOLUTION.md` - 完整解决方案

### MQ Tick 类型定义
- `mq_tick_schema.json` - JSON Schema
- `mq_tick_types.py` - Python Pydantic
- `mq_tick_types.rs` - Rust Serde
- `mq_tick_types.ts` - TypeScript

### 核心实现
- `architecture_demo.py` - 架构演示
- `polymarket_simple_data.py` - Polymarket 数据获取器
- `nautilus-core/rust/` - Rust 核心库

---

## 🛠️ 技术栈

- **Python**: 3.14
- **Rust**: 最新稳定版 (Cargo + PyO3)
- **Go**: 1.21+ (API Gateway)
- **Node.js**: 20.x (前端)
- **Redis**: 事件总线
- **NautilusTrader**: 1.224.0
- **React + TypeScript**: 前端

---

## 🚀 当前状态

### 已完成
- ✅ 三层架构设计
- ✅ MQ Tick 标准格式定义（4 种语言）
- ✅ NT → MQ 桥接层设计
- ✅ Polymarket 数据获取器
- ✅ 架构演示（已测试通过）
- ✅ Ubuntu 迁移准备

### 进行中
- ⏳ 实现 Python 桥接层
- ⏳ 集成真实 NautilusTrader
- ⏳ 集成真实 Redis Streams

### 待办
- ⏳ 实现 Rust 桥接层
- ⏳ 端到端测试
- ⏳ 性能优化

---

## 💡 重要提醒

1. **NT 和 MQ 必须通过桥接层解耦**
2. **MQ Tick 是标准化的 JSON 格式**
3. **不能直接使用 NT 的数据结构**
4. **Redis Streams 是唯一的通信层**
5. **多租户通过 Redis 命名空间隔离**

---

## 📞 快速参考

### Git 仓库
```
https://github.com/lonzo-huang/crazytra.git
```

### 关键命令
```bash
# Python 环境
python3 -m venv venv
source venv/bin/activate
pip install -r nautilus-core/requirements.txt

# Rust 构建
cd nautilus-core/rust
cargo build --release

# 运行测试
python architecture_demo.py
python mq_tick_types.py
```

---

**此文档用于在新环境中快速恢复项目上下文。**
