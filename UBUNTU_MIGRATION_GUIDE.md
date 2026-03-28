# Ubuntu 开发环境迁移指南

## 📋 迁移前准备

本指南帮助你将 MirrorQuant 开发环境从 Windows 迁移到 Ubuntu。

---

## 🎯 系统要求

### Ubuntu 版本
- **推荐**: Ubuntu 22.04 LTS 或 24.04 LTS
- **最低**: Ubuntu 20.04 LTS

### 硬件要求
- **CPU**: 4 核心以上
- **内存**: 8GB 以上（推荐 16GB）
- **硬盘**: 50GB 可用空间

---

## 📦 安装依赖

### 1. 更新系统
```bash
sudo apt update
sudo apt upgrade -y
```

### 2. 安装基础工具
```bash
sudo apt install -y \
    git \
    curl \
    wget \
    build-essential \
    pkg-config \
    libssl-dev \
    ca-certificates
```

### 3. 安装 Python 3.14
```bash
# 添加 deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# 安装 Python 3.14
sudo apt install -y \
    python3.14 \
    python3.14-dev \
    python3.14-venv \
    python3-pip

# 设置 Python 3.14 为默认
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.14 1
```

### 4. 安装 Rust
```bash
# 安装 Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# 加载 Rust 环境
source $HOME/.cargo/env

# 验证安装
rustc --version
cargo --version
```

### 5. 安装 Go 1.21+
```bash
# 下载 Go
wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz

# 解压到 /usr/local
sudo rm -rf /usr/local/go
sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz

# 添加到 PATH
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
source ~/.bashrc

# 验证安装
go version
```

### 6. 安装 Node.js 和 npm
```bash
# 安装 Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 验证安装
node --version
npm --version
```

### 7. 安装 Redis
```bash
# 安装 Redis
sudo apt install -y redis-server

# 启动 Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# 验证安装
redis-cli ping
```

### 8. 安装 Docker（可选）
```bash
# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 添加当前用户到 docker 组
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo apt install -y docker-compose

# 重新登录以应用组权限
# 然后验证安装
docker --version
docker-compose --version
```

---

## 🔄 克隆项目

### 1. 克隆仓库
```bash
# 克隆项目
git clone https://github.com/lonzo-huang/crazytra.git
cd crazytra
```

### 2. 检查分支
```bash
# 查看当前分支
git branch

# 切换到 master 分支（如果不在）
git checkout master

# 拉取最新代码
git pull origin master
```

---

## 🛠️ 项目设置

### 1. Python 环境
```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装 Python 依赖
pip install -r nautilus-core/requirements.txt
```

### 2. Rust 核心库
```bash
# 进入 Rust 目录
cd nautilus-core/rust

# 构建 Rust 库
cargo build --release

# 返回项目根目录
cd ../..
```

### 3. Go API Gateway
```bash
# 进入 API Gateway 目录
cd api-gateway

# 下载 Go 依赖
go mod download

# 构建 API Gateway
go build -o bin/api-gateway src/main.go

# 返回项目根目录
cd ..
```

### 4. 前端
```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 构建前端（可选）
npm run build

# 返回项目根目录
cd ..
```

---

## 🚀 启动服务

### 1. 启动 Redis
```bash
# 确保 Redis 正在运行
sudo systemctl status redis-server

# 如果未运行，启动它
sudo systemctl start redis-server
```

### 2. 启动 API Gateway
```bash
cd api-gateway
./bin/api-gateway
```

### 3. 启动前端（开发模式）
```bash
cd frontend
npm run dev
```

### 4. 运行测试
```bash
# 激活 Python 虚拟环境
source venv/bin/activate

# 运行架构演示
python architecture_demo.py

# 运行 MQ Tick 类型测试
python mq_tick_types.py

# 运行 Polymarket 数据测试
python polymarket_simple_data.py
```

---

## 🔧 环境变量配置

### 1. 创建 `.env` 文件
```bash
# 在项目根目录创建 .env 文件
cat > .env << 'EOF'
# Redis 配置
REDIS_URL=redis://localhost:6379

# Polymarket 配置（如果需要）
POLYMARKET_PK=your_private_key_here
POLYMARKET_FUNDER=your_wallet_address_here
POLYMARKET_API_KEY=your_api_key_here
POLYMARKET_API_SECRET=your_api_secret_here
POLYMARKET_PASSPHRASE=your_passphrase_here

# API Gateway 配置
API_GATEWAY_PORT=8080

# 前端配置
VITE_API_URL=http://localhost:8080
EOF
```

### 2. 设置权限
```bash
chmod 600 .env
```

---

## 📝 常见问题

### Python 版本问题
如果遇到 Python 版本不兼容：
```bash
# 检查 Python 版本
python3 --version

# 如果不是 3.14，重新设置默认版本
sudo update-alternatives --config python3
```

### Rust 编译问题
如果 Rust 编译失败：
```bash
# 更新 Rust
rustup update

# 清理并重新构建
cd nautilus-core/rust
cargo clean
cargo build --release
```

### Go 模块问题
如果 Go 依赖下载失败：
```bash
# 设置 Go 代理（中国用户）
go env -w GOPROXY=https://goproxy.cn,direct

# 清理并重新下载
go clean -modcache
go mod download
```

### Redis 连接问题
如果无法连接 Redis：
```bash
# 检查 Redis 状态
sudo systemctl status redis-server

# 查看 Redis 日志
sudo journalctl -u redis-server -f

# 重启 Redis
sudo systemctl restart redis-server
```

---

## 🎯 验证安装

运行以下命令验证所有组件：

```bash
# 1. Python
python3 --version

# 2. Rust
rustc --version
cargo --version

# 3. Go
go version

# 4. Node.js
node --version
npm --version

# 5. Redis
redis-cli ping

# 6. Docker（可选）
docker --version
docker-compose --version

# 7. 项目依赖
source venv/bin/activate
python -c "import nautilus_trader; print('NautilusTrader:', nautilus_trader.__version__)"
python -c "import pydantic; print('Pydantic:', pydantic.__version__)"
```

---

## 🔄 与 Windows 的差异

### 路径分隔符
- Windows: `\` 或 `\\`
- Ubuntu: `/`

### 脚本文件
- Windows: `.bat`, `.ps1`
- Ubuntu: `.sh`

### 环境变量
- Windows: `$env:VAR_NAME`
- Ubuntu: `$VAR_NAME`

### 权限
Ubuntu 需要设置可执行权限：
```bash
chmod +x script.sh
```

---

## 📚 下一步

1. ✅ 验证所有依赖安装成功
2. ✅ 运行测试确保项目正常工作
3. ✅ 配置环境变量
4. ✅ 启动所有服务
5. ✅ 开始开发

---

## 🆘 获取帮助

如果遇到问题：

1. 查看项目文档：`README.md`
2. 查看架构文档：`ARCHITECTURE.md`
3. 查看桥接层文档：`NT_TO_MQ_BRIDGE.md`
4. 查看项目状态：`PROJECT_STATUS.md`

---

## 🎉 完成

恭喜！你已经成功将 MirrorQuant 开发环境迁移到 Ubuntu。

现在你可以：
- 运行架构演示：`python architecture_demo.py`
- 测试 MQ Tick 类型：`python mq_tick_types.py`
- 测试 Polymarket 数据：`python polymarket_simple_data.py`
- 启动 API Gateway：`cd api-gateway && ./bin/api-gateway`
- 启动前端：`cd frontend && npm run dev`
