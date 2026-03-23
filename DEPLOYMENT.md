# Crazytra 部署指南

本文档介绍如何部署 Crazytra 量化交易系统。

## 系统要求

### 硬件要求

**最低配置**：
- CPU: 4 核
- 内存: 8 GB
- 硬盘: 50 GB SSD
- 网络: 稳定的互联网连接

**推荐配置**：
- CPU: 8 核
- 内存: 16 GB
- 硬盘: 100 GB SSD
- GPU: NVIDIA GPU（用于 LLM 加速，可选）
- 网络: 低延迟互联网连接

### 软件要求

- Docker 20.10+
- Docker Compose 2.0+
- Git

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/lonzo-huang/crazytra.git
cd crazytra
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写必要的配置：

```bash
# 数据库密码
POSTGRES_PASSWORD=your_secure_password

# 交易模式（paper=纸面交易，live=实盘交易）
TRADING_MODE=paper

# Binance API（如果使用 Binance）
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# LLM API（可选）
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key
NEWSAPI_KEY=your_newsapi_key

# Ollama 模型
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M

# 日志级别
LOG_LEVEL=INFO

# JWT 密钥
JWT_SECRET=your_random_secret_here
```

### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 查看特定服务的日志
docker-compose logs -f nautilus-core
```

### 4. 初始化 Ollama 模型

```bash
# 进入 Ollama 容器
docker exec -it crazytra-ollama bash

# 拉取模型
ollama pull mistral:7b-instruct-q4_K_M

# 退出容器
exit
```

### 5. 访问服务

- **前端**: http://localhost:3000
- **API**: http://localhost:8080
- **Grafana**: http://localhost:3001 (admin/admin)

## 服务说明

### Redis

**端口**: 6379  
**用途**: 消息总线和缓存  
**数据持久化**: `redis_data` volume

**健康检查**:
```bash
docker exec crazytra-redis redis-cli ping
```

### TimescaleDB

**端口**: 5432  
**用途**: 时序数据存储  
**数据持久化**: `timescaledb_data` volume

**连接**:
```bash
docker exec -it crazytra-timescaledb psql -U crazytra -d crazytra
```

### Ollama

**端口**: 11434  
**用途**: 本地 LLM 服务  
**数据持久化**: `ollama_data` volume

**管理模型**:
```bash
# 列出已安装的模型
docker exec crazytra-ollama ollama list

# 拉取新模型
docker exec crazytra-ollama ollama pull llama3:8b

# 删除模型
docker exec crazytra-ollama ollama rm mistral:7b
```

### LLM 层

**依赖**: Redis, Ollama  
**用途**: 新闻分析和权重生成

**查看日志**:
```bash
docker-compose logs -f llm-layer
```

### Nautilus 核心

**依赖**: Redis, TimescaleDB  
**用途**: 策略引擎和交易执行

**查看日志**:
```bash
docker-compose logs -f nautilus-core
```

### API 网关

**端口**: 8080  
**依赖**: Redis, TimescaleDB  
**用途**: REST API 和 WebSocket

**健康检查**:
```bash
curl http://localhost:8080/health
```

### 前端

**端口**: 3000  
**依赖**: API 网关  
**用途**: Web UI

**访问**: http://localhost:3000

### Grafana

**端口**: 3001  
**依赖**: TimescaleDB  
**用途**: 监控和可视化

**默认账号**: admin/admin

## 配置详解

### 环境变量

#### 数据库配置

```bash
POSTGRES_PASSWORD=your_password  # PostgreSQL 密码
```

#### 交易配置

```bash
TRADING_MODE=paper              # paper 或 live
BINANCE_API_KEY=your_key        # Binance API Key
BINANCE_API_SECRET=your_secret  # Binance API Secret
```

#### LLM 配置

```bash
# Ollama
OLLAMA_MODEL=mistral:7b-instruct-q4_K_M
LLM_INTERVAL_S=300              # 分析间隔（秒）
BREAKING_THRESHOLD=0.85         # 重大新闻阈值

# 云端 LLM（可选）
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
NEWSAPI_KEY=your_key
```

#### 日志配置

```bash
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR
```

#### 安全配置

```bash
JWT_SECRET=your_random_secret   # JWT 签名密钥
```

## 数据持久化

### Volume 说明

| Volume | 用途 | 大小建议 |
|--------|------|----------|
| `redis_data` | Redis 数据 | 5 GB |
| `timescaledb_data` | 时序数据 | 50 GB |
| `ollama_data` | LLM 模型 | 20 GB |
| `nautilus_data` | 策略数据 | 10 GB |
| `grafana_data` | Grafana 配置 | 1 GB |

### 备份

```bash
# 备份 Redis
docker exec crazytra-redis redis-cli SAVE
docker cp crazytra-redis:/data/dump.rdb ./backup/

# 备份 PostgreSQL
docker exec crazytra-timescaledb pg_dump -U crazytra crazytra > ./backup/db_backup.sql

# 备份所有 volumes
docker run --rm -v crazytra_timescaledb_data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/timescaledb_backup.tar.gz /data
```

### 恢复

```bash
# 恢复 Redis
docker cp ./backup/dump.rdb crazytra-redis:/data/
docker restart crazytra-redis

# 恢复 PostgreSQL
docker exec -i crazytra-timescaledb psql -U crazytra crazytra < ./backup/db_backup.sql
```

## 监控

### 日志查看

```bash
# 所有服务
docker-compose logs -f

# 特定服务
docker-compose logs -f nautilus-core

# 最近 100 行
docker-compose logs --tail=100 llm-layer
```

### 资源使用

```bash
# 查看容器资源使用
docker stats

# 查看特定容器
docker stats crazytra-nautilus-core
```

### Grafana 仪表板

访问 http://localhost:3001，使用以下仪表板：

- **系统概览**: 整体性能指标
- **策略性能**: 策略收益和风险
- **订单监控**: 订单执行情况
- **LLM 分析**: LLM 权重和新闻

## 扩展和优化

### 水平扩展

```yaml
# docker-compose.yml
nautilus-core:
  deploy:
    replicas: 3  # 运行 3 个实例
```

### 资源限制

```yaml
nautilus-core:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 2G
```

### GPU 加速

如果有 NVIDIA GPU：

```bash
# 安装 NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

Ollama 服务会自动使用 GPU。

## 故障排查

### 问题：服务无法启动

**检查**:
```bash
# 查看服务状态
docker-compose ps

# 查看错误日志
docker-compose logs service-name
```

### 问题：Redis 连接失败

**检查**:
```bash
# 测试 Redis 连接
docker exec crazytra-redis redis-cli ping

# 检查网络
docker network inspect crazytra_crazytra-network
```

### 问题：数据库连接失败

**检查**:
```bash
# 测试数据库连接
docker exec crazytra-timescaledb pg_isready -U crazytra

# 查看数据库日志
docker-compose logs timescaledb
```

### 问题：Ollama 模型未加载

**解决**:
```bash
# 进入容器
docker exec -it crazytra-ollama bash

# 拉取模型
ollama pull mistral:7b-instruct-q4_K_M

# 验证模型
ollama list
```

### 问题：前端无法连接 API

**检查**:
```bash
# 测试 API 健康
curl http://localhost:8080/health

# 检查 CORS 配置
# 查看 api-gateway 日志
docker-compose logs api-gateway
```

## 生产部署

### 安全加固

1. **更改默认密码**:
   ```bash
   POSTGRES_PASSWORD=strong_random_password
   GRAFANA_PASSWORD=strong_random_password
   JWT_SECRET=long_random_string
   ```

2. **启用 HTTPS**:
   使用 Nginx 或 Traefik 作为反向代理。

3. **防火墙配置**:
   ```bash
   # 只开放必要端口
   ufw allow 80/tcp    # HTTP
   ufw allow 443/tcp   # HTTPS
   ufw enable
   ```

4. **限制网络访问**:
   ```yaml
   # docker-compose.yml
   services:
     redis:
       ports: []  # 不暴露到主机
   ```

### 高可用部署

1. **Redis 集群**:
   使用 Redis Sentinel 或 Redis Cluster。

2. **数据库主从**:
   配置 PostgreSQL 主从复制。

3. **负载均衡**:
   使用 Nginx 或 HAProxy 进行负载均衡。

### 监控告警

1. **配置 Prometheus**:
   ```yaml
   prometheus:
     image: prom/prometheus
     volumes:
       - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
   ```

2. **配置 AlertManager**:
   设置告警规则和通知渠道。

## 更新和维护

### 更新服务

```bash
# 拉取最新代码
git pull origin master

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d
```

### 滚动更新

```bash
# 逐个重启服务，避免停机
docker-compose up -d --no-deps --build nautilus-core
```

### 清理

```bash
# 停止所有服务
docker-compose down

# 删除所有数据（谨慎！）
docker-compose down -v

# 清理未使用的镜像
docker image prune -a
```

## 性能调优

### Redis 优化

```bash
# 增加最大内存
# docker-compose.yml
command: redis-server --maxmemory 4gb
```

### PostgreSQL 优化

```sql
-- 调整配置
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '64MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- 重启数据库
SELECT pg_reload_conf();
```

### 网络优化

```yaml
# docker-compose.yml
networks:
  crazytra-network:
    driver: bridge
    driver_opts:
      com.docker.network.driver.mtu: 1500
```

## 参考资料

- [Docker 文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [Redis 文档](https://redis.io/documentation)
- [PostgreSQL 文档](https://www.postgresql.org/docs/)
- [Ollama 文档](https://ollama.com/docs)
- [Grafana 文档](https://grafana.com/docs/)
