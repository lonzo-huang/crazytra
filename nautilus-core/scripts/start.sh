#!/bin/bash
# Nautilus Trader 启动脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Nautilus Trader - Crazytra Integration ===${NC}"

# 检查 Python 版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${YELLOW}Python version: ${PYTHON_VERSION}${NC}"

# 检查 .env 文件
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo -e "${YELLOW}Please copy .env.example to .env and configure it${NC}"
    exit 1
fi

# 加载环境变量
source .env

# 检查 Redis 连接
echo -e "${YELLOW}Checking Redis connection...${NC}"
if ! redis-cli -u $REDIS_URL ping > /dev/null 2>&1; then
    echo -e "${RED}Error: Cannot connect to Redis at ${REDIS_URL}${NC}"
    echo -e "${YELLOW}Please start Redis first:${NC}"
    echo -e "  docker run -d -p 6379:6379 redis:alpine"
    exit 1
fi
echo -e "${GREEN}✓ Redis connected${NC}"

# 检查依赖
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! python3 -c "import nautilus_trader" 2>/dev/null; then
    echo -e "${RED}Error: nautilus_trader not installed${NC}"
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt
fi
echo -e "${GREEN}✓ Dependencies installed${NC}"

# 解析命令行参数
MODE=${1:-paper}

if [ "$MODE" != "paper" ] && [ "$MODE" != "live" ] && [ "$MODE" != "backtest" ]; then
    echo -e "${RED}Error: Invalid mode '${MODE}'${NC}"
    echo -e "${YELLOW}Usage: $0 [paper|live|backtest]${NC}"
    exit 1
fi

# 启动
echo -e "${GREEN}Starting Nautilus Trader in ${MODE} mode...${NC}"
echo ""

python3 main.py --mode $MODE
