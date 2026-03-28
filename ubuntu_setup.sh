#!/bin/bash
# MirrorQuant Ubuntu 开发环境自动安装脚本
# 使用方法: chmod +x ubuntu_setup.sh && ./ubuntu_setup.sh

set -e  # 遇到错误立即退出

echo "🚀 MirrorQuant Ubuntu 开发环境安装脚本"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为 root 用户
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}❌ 请不要使用 root 用户运行此脚本${NC}"
    exit 1
fi

# 1. 更新系统
echo -e "\n${YELLOW}📦 步骤 1/8: 更新系统...${NC}"
sudo apt update
sudo apt upgrade -y

# 2. 安装基础工具
echo -e "\n${YELLOW}🔧 步骤 2/8: 安装基础工具...${NC}"
sudo apt install -y \
    git \
    curl \
    wget \
    build-essential \
    pkg-config \
    libssl-dev \
    ca-certificates \
    software-properties-common

# 3. 安装 Python 3.14
echo -e "\n${YELLOW}🐍 步骤 3/8: 安装 Python 3.14...${NC}"
if ! command -v python3.14 &> /dev/null; then
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt update
    sudo apt install -y \
        python3.14 \
        python3.14-dev \
        python3.14-venv \
        python3-pip
    
    # 设置 Python 3.14 为默认
    sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.14 1
    echo -e "${GREEN}✅ Python 3.14 安装完成${NC}"
else
    echo -e "${GREEN}✅ Python 3.14 已安装${NC}"
fi

# 4. 安装 Rust
echo -e "\n${YELLOW}🦀 步骤 4/8: 安装 Rust...${NC}"
if ! command -v rustc &> /dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
    echo -e "${GREEN}✅ Rust 安装完成${NC}"
else
    echo -e "${GREEN}✅ Rust 已安装${NC}"
fi

# 5. 安装 Go 1.21+
echo -e "\n${YELLOW}🔵 步骤 5/8: 安装 Go 1.21...${NC}"
if ! command -v go &> /dev/null || [[ $(go version | grep -oP 'go\K[0-9]+\.[0-9]+' | head -1) < "1.21" ]]; then
    wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
    sudo rm -rf /usr/local/go
    sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
    rm go1.21.0.linux-amd64.tar.gz
    
    # 添加到 PATH
    if ! grep -q "/usr/local/go/bin" ~/.bashrc; then
        echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
    fi
    export PATH=$PATH:/usr/local/go/bin
    echo -e "${GREEN}✅ Go 1.21 安装完成${NC}"
else
    echo -e "${GREEN}✅ Go 已安装${NC}"
fi

# 6. 安装 Node.js 20.x
echo -e "\n${YELLOW}🟢 步骤 6/8: 安装 Node.js 20.x...${NC}"
if ! command -v node &> /dev/null || [[ $(node -v | grep -oP 'v\K[0-9]+' | head -1) < "20" ]]; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
    echo -e "${GREEN}✅ Node.js 20.x 安装完成${NC}"
else
    echo -e "${GREEN}✅ Node.js 已安装${NC}"
fi

# 7. 安装 Redis
echo -e "\n${YELLOW}🔴 步骤 7/8: 安装 Redis...${NC}"
if ! command -v redis-server &> /dev/null; then
    sudo apt install -y redis-server
    sudo systemctl start redis-server
    sudo systemctl enable redis-server
    echo -e "${GREEN}✅ Redis 安装完成${NC}"
else
    echo -e "${GREEN}✅ Redis 已安装${NC}"
fi

# 8. 安装 Docker（可选）
echo -e "\n${YELLOW}🐳 步骤 8/8: 安装 Docker（可选）...${NC}"
read -p "是否安装 Docker? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        rm get-docker.sh
        sudo usermod -aG docker $USER
        sudo apt install -y docker-compose
        echo -e "${GREEN}✅ Docker 安装完成${NC}"
        echo -e "${YELLOW}⚠️  请重新登录以应用 Docker 组权限${NC}"
    else
        echo -e "${GREEN}✅ Docker 已安装${NC}"
    fi
else
    echo -e "${YELLOW}⏭️  跳过 Docker 安装${NC}"
fi

# 验证安装
echo -e "\n${YELLOW}🧪 验证安装...${NC}"
echo "Python: $(python3 --version)"
echo "Rust: $(rustc --version)"
echo "Go: $(go version)"
echo "Node.js: $(node --version)"
echo "npm: $(npm --version)"
echo "Redis: $(redis-cli --version)"
if command -v docker &> /dev/null; then
    echo "Docker: $(docker --version)"
fi

# 完成
echo -e "\n${GREEN}🎉 所有依赖安装完成！${NC}"
echo -e "\n${YELLOW}📋 下一步：${NC}"
echo "1. 克隆项目: git clone https://github.com/lonzo-huang/crazytra.git"
echo "2. 进入目录: cd crazytra"
echo "3. 创建 Python 虚拟环境: python3 -m venv venv"
echo "4. 激活虚拟环境: source venv/bin/activate"
echo "5. 安装 Python 依赖: pip install -r nautilus-core/requirements.txt"
echo "6. 构建 Rust 库: cd nautilus-core/rust && cargo build --release"
echo "7. 查看完整指南: cat UBUNTU_MIGRATION_GUIDE.md"

echo -e "\n${GREEN}✨ 准备开始开发！${NC}"
