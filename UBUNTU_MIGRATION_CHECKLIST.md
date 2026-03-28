# Ubuntu 迁移检查清单

## ✅ 已完成（Windows 端）

- [x] 所有代码文件已提交到 Git
- [x] 所有文档已更新
- [x] MQ Tick 标准格式已定义
- [x] NT → MQ 桥接层设计已完成
- [x] Ubuntu 迁移指南已创建
- [x] 自动安装脚本已创建
- [x] 所有更改已推送到 GitHub

---

## 📋 Ubuntu 端待办事项

### 1. 系统准备（30 分钟）

- [ ] 安装 Ubuntu 22.04 LTS 或 24.04 LTS
- [ ] 更新系统：`sudo apt update && sudo apt upgrade -y`
- [ ] 配置网络和 SSH（如果需要远程访问）

### 2. 自动安装依赖（20 分钟）

```bash
# 克隆项目
git clone https://github.com/lonzo-huang/crazytra.git
cd crazytra

# 运行自动安装脚本
chmod +x ubuntu_setup.sh
./ubuntu_setup.sh
```

**脚本会自动安装：**
- [x] Python 3.14
- [x] Rust
- [x] Go 1.21+
- [x] Node.js 20.x
- [x] Redis
- [x] Docker（可选）

### 3. 项目设置（15 分钟）

```bash
# 创建 Python 虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
pip install --upgrade pip
pip install -r nautilus-core/requirements.txt

# 构建 Rust 库
cd nautilus-core/rust
cargo build --release
cd ../..

# 构建 Go API Gateway
cd api-gateway
go mod download
go build -o bin/api-gateway src/main.go
cd ..

# 安装前端依赖
cd frontend
npm install
cd ..
```

### 4. 环境变量配置（5 分钟）

```bash
# 创建 .env 文件
cat > .env << 'EOF'
REDIS_URL=redis://localhost:6379
POLYMARKET_PK=your_private_key_here
POLYMARKET_FUNDER=your_wallet_address_here
POLYMARKET_API_KEY=your_api_key_here
POLYMARKET_API_SECRET=your_api_secret_here
POLYMARKET_PASSPHRASE=your_passphrase_here
API_GATEWAY_PORT=8080
VITE_API_URL=http://localhost:8080
EOF

chmod 600 .env
```

### 5. 验证安装（10 分钟）

```bash
# 激活虚拟环境
source venv/bin/activate

# 运行测试
python architecture_demo.py
python mq_tick_types.py
python polymarket_simple_data.py

# 验证所有组件
python3 --version
rustc --version
go version
node --version
redis-cli ping
```

### 6. 启动服务（5 分钟）

```bash
# 终端 1: 启动 Redis（如果未自动启动）
sudo systemctl start redis-server

# 终端 2: 启动 API Gateway
cd api-gateway
./bin/api-gateway

# 终端 3: 启动前端（开发模式）
cd frontend
npm run dev
```

---

## 🎯 关键文件位置

### 核心文档
- `README.md` - 项目概述
- `ARCHITECTURE.md` - 架构设计
- `NT_TO_MQ_BRIDGE.md` - 桥接层设计
- `UBUNTU_MIGRATION_GUIDE.md` - 详细迁移指南
- `PROJECT_STATUS.md` - 项目状态

### 核心代码
- `mq_tick_types.py` - MQ Tick Python 类型
- `mq_tick_types.rs` - MQ Tick Rust 类型
- `mq_tick_types.ts` - MQ Tick TypeScript 类型
- `architecture_demo.py` - 架构演示
- `polymarket_simple_data.py` - Polymarket 数据获取器

### Rust 核心
- `nautilus-core/rust/src/lib.rs` - Rust 主库
- `nautilus-core/rust/src/data_polymarket.rs` - Polymarket 数据引擎
- `nautilus-core/rust/Cargo.toml` - Rust 依赖配置

### API Gateway
- `api-gateway/src/main.go` - Go API Gateway
- `api-gateway/handlers/` - API 处理器

### 前端
- `frontend/src/App.tsx` - React 主应用
- `frontend/src/components/` - React 组件

---

## 🔧 常见问题解决

### Python 版本问题
```bash
# 检查版本
python3 --version

# 重新设置默认版本
sudo update-alternatives --config python3
```

### Rust 编译问题
```bash
# 更新 Rust
rustup update

# 清理并重新构建
cd nautilus-core/rust
cargo clean
cargo build --release
```

### Redis 连接问题
```bash
# 检查状态
sudo systemctl status redis-server

# 重启 Redis
sudo systemctl restart redis-server
```

### Go 模块问题
```bash
# 设置代理（中国用户）
go env -w GOPROXY=https://goproxy.cn,direct

# 清理并重新下载
go clean -modcache
go mod download
```

---

## 📊 迁移后验证清单

### 基础环境
- [ ] Python 3.14 正常工作
- [ ] Rust 编译成功
- [ ] Go 构建成功
- [ ] Node.js 和 npm 正常
- [ ] Redis 服务运行中

### 项目功能
- [ ] `architecture_demo.py` 运行成功
- [ ] `mq_tick_types.py` 测试通过
- [ ] `polymarket_simple_data.py` 获取数据成功
- [ ] API Gateway 启动成功
- [ ] 前端开发服务器启动成功

### 核心组件
- [ ] Rust 库编译成功（`nautilus-core/rust/target/release/`）
- [ ] Go 二进制文件生成（`api-gateway/bin/api-gateway`）
- [ ] Python 虚拟环境正常
- [ ] 所有依赖安装完成

---

## 🚀 迁移后下一步

### 立即任务
1. [ ] 验证所有测试通过
2. [ ] 配置开发环境（VS Code/其他 IDE）
3. [ ] 设置 Git 配置（用户名、邮箱）
4. [ ] 创建开发分支

### 短期任务
1. [ ] 实现 Python 桥接层（连接 NT + Redis）
2. [ ] 集成真实 NautilusTrader Polymarket Connector
3. [ ] 集成真实 Redis Streams
4. [ ] 端到端测试

### 中期任务
1. [ ] 实现 Rust 桥接层（性能优化）
2. [ ] 性能测试和优化
3. [ ] 多租户功能实现
4. [ ] 完整文档更新

---

## 📝 重要提示

### Git 配置
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### SSH 密钥（可选）
```bash
ssh-keygen -t ed25519 -C "your.email@example.com"
cat ~/.ssh/id_ed25519.pub
# 将公钥添加到 GitHub
```

### 开发分支
```bash
# 创建开发分支
git checkout -b dev

# 推送到远程
git push -u origin dev
```

---

## ✨ 完成标志

当以下所有项都完成时，迁移成功：

- [x] 所有依赖安装成功
- [x] 所有测试通过
- [x] 服务正常启动
- [x] 可以正常开发

---

## 🆘 需要帮助？

查看详细文档：
- `UBUNTU_MIGRATION_GUIDE.md` - 详细迁移指南
- `README.md` - 项目说明
- `ARCHITECTURE.md` - 架构文档

---

**预计总时间：约 1.5 小时**

祝迁移顺利！🎉
