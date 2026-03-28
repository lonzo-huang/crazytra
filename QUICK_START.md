# MirrorQuant - 快速启动指南

**5 分钟快速启动 MirrorQuant 项目**

---

## 🚀 快速启动步骤

### 1. 启动核心服务（Docker）

```powershell
# 启动 Redis, TimescaleDB, Ollama
docker-compose -f docker-compose.simple.yml up -d

# 验证服务运行
docker ps
```

**预期输出**：
- ✅ mirrorquant-redis (6379)
- ✅ mirrorquant-timescaledb (5432)
- ✅ mirrorquant-ollama (11434)

---

### 2. 启动 Polymarket 数据适配器

```powershell
# 后台运行
python nautilus-core/adapters/polymarket_adapter.py
```

**预期输出**：
```
🚀 Polymarket adapter started (update interval: 30s)
INFO:__main__:Fetched 1000 markets
```

---

### 3. 启动前端（开发模式）

```powershell
cd frontend
npm run dev
```

**访问**: http://localhost:5173

**预期看到**：
- ✅ MirrorQuant 品牌
- ✅ Dashboard 页面
- ✅ Polymarket Predictions 面板

---

### 4. 启动 API 服务（二选一）

#### 选项 A：临时 Flask API（快速）

```powershell
python polymarket_api.py
```

#### 选项 B：Go API Gateway（推荐）

```powershell
.\start-api-gateway.ps1
```

**访问**: http://localhost:8080/health

---

## 📋 完整服务清单

| 服务 | 端口 | 状态 | 命令 |
|------|------|------|------|
| Redis | 6379 | ✅ 必需 | `docker-compose up redis` |
| TimescaleDB | 5432 | ✅ 必需 | `docker-compose up timescaledb` |
| Ollama | 11434 | ✅ 必需 | `docker-compose up ollama` |
| Polymarket 适配器 | - | ✅ 必需 | `python nautilus-core/adapters/polymarket_adapter.py` |
| API 服务 | 8080 | ✅ 必需 | `python polymarket_api.py` 或 `.\start-api-gateway.ps1` |
| 前端 | 5173 | ✅ 必需 | `cd frontend && npm run dev` |
| Nautilus Core | - | ⏸️ 可选 | 待配置 |
| LLM Layer | - | ⏸️ 可选 | 待配置 |

---

## 🔍 验证运行状态

### 检查 Docker 服务

```powershell
docker ps
```

### 检查 API 健康

```powershell
# Flask API
curl http://localhost:8080/health

# Go API
curl http://localhost:8080/health
```

### 检查 Polymarket 数据

```powershell
curl http://localhost:8080/api/v1/polymarket/markets
```

### 检查前端

浏览器访问：http://localhost:5173

---

## 🛑 停止服务

### 停止 Docker 服务

```powershell
docker-compose -f docker-compose.simple.yml down
```

### 停止 Python 服务

按 `Ctrl+C` 停止：
- Polymarket 适配器
- Flask API

### 停止前端

按 `Ctrl+C` 停止 Vite 开发服务器

---

## 🐛 常见问题

### 问题 1：Redis 连接失败

**症状**：`ConnectionError: Error connecting to Redis`

**解决**：
```powershell
# 检查 Redis 是否运行
docker ps | findstr redis

# 重启 Redis
docker restart mirrorquant-redis
```

### 问题 2：前端无法获取数据

**症状**：前端显示 "Failed to fetch Polymarket markets"

**解决**：
1. 检查 API 服务是否运行（localhost:8080）
2. 检查 Polymarket 适配器是否运行
3. 检查 Redis 是否有数据

```powershell
# 测试 API
curl http://localhost:8080/api/v1/polymarket/markets
```

### 问题 3：Polymarket 适配器无数据

**症状**：`No markets fetched`

**解决**：
1. 检查网络连接
2. 检查 Polymarket API 是否可访问
3. 运行测试脚本

```powershell
python test_polymarket_quick.py
```

### 问题 4：Docker 无法启动

**症状**：`Cannot connect to Docker daemon`

**解决**：
1. 启动 Docker Desktop
2. 等待 Docker 完全启动
3. 重试命令

---

## 📊 功能测试清单

### Polymarket 面板测试

- [ ] 能看到市场列表
- [ ] 搜索功能正常
- [ ] 排序功能正常
- [ ] 筛选功能正常
- [ ] 数据每 30 秒更新
- [ ] Yes/No 概率显示正确

### 测试步骤

1. **搜索测试**
   - 输入 "Bitcoin"
   - 应该只显示包含 Bitcoin 的市场

2. **排序测试**
   - 选择 "Highest Volume"
   - 市场应按交易量降序排列

3. **筛选测试**
   - 选择 "$1M+"
   - 只显示交易量超过 100 万的市场

4. **自动刷新测试**
   - 等待 30 秒
   - 数据应自动更新

---

## 🎯 下一步

启动成功后，你可以：

1. **浏览 Polymarket 市场**
   - 搜索感兴趣的市场
   - 查看概率变化

2. **测试其他功能**
   - 查看 Dashboard
   - 测试 WebSocket 连接

3. **开始开发**
   - 添加新功能
   - 集成其他市场
   - 实现交易功能

---

## 📚 相关文档

- [项目状态](PROJECT_STATUS.md) - 当前项目状态
- [开发路线图](ROADMAP.md) - 未来计划
- [Polymarket 集成指南](docs/POLYMARKET_INTEGRATION_GUIDE.md) - 详细集成说明
- [架构文档](ARCHITECTURE.md) - 系统架构
- [今日总结](TODAY_SUMMARY.md) - 最新进展

---

## 🆘 获取帮助

### 查看日志

```powershell
# Docker 服务日志
docker logs mirrorquant-redis
docker logs mirrorquant-timescaledb

# Python 服务日志
# 查看终端输出
```

### 重置环境

```powershell
# 停止所有服务
docker-compose -f docker-compose.simple.yml down

# 清理数据（可选）
docker volume prune

# 重新启动
docker-compose -f docker-compose.simple.yml up -d
```

---

## ✅ 启动检查清单

启动前确认：

- [ ] Docker Desktop 已启动
- [ ] Python 3.11+ 已安装
- [ ] Node.js 18+ 已安装
- [ ] 端口 6379, 5432, 8080, 5173 未被占用

启动后验证：

- [ ] Docker 服务运行正常
- [ ] Polymarket 适配器获取数据
- [ ] API 服务响应正常
- [ ] 前端页面加载成功
- [ ] Polymarket 面板显示数据

---

**祝你使用愉快！** 🚀
