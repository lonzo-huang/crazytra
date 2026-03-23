#!/bin/bash
# Crazytra 开发环境一键启动脚本 (Linux/macOS)

set -e

echo "🚀 启动 Crazytra 开发环境"
echo "============================"

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装或未运行"
    echo "请先安装并启动 Docker"
    exit 1
fi

echo "✅ Docker 已安装"

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装"
    echo "请访问 https://nodejs.org/ 安装 Node.js 18+"
    exit 1
fi

echo "✅ Node.js $(node -v)"

echo ""
echo "📦 启动后端服务..."

# 启动 Docker 服务
docker-compose up -d redis timescaledb ollama

echo ""
echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
echo ""
echo "🔍 检查服务状态..."
docker-compose ps

echo ""
echo "📊 配置前端环境..."

# 进入前端目录
cd frontend

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "📝 创建 .env 文件..."
    cp .env.example .env
fi

# 检查依赖
if [ ! -d node_modules ]; then
    echo "📦 安装前端依赖..."
    npm install
fi

echo ""
echo "✅ 环境准备完成！"
echo ""
echo "🎯 启动前端开发服务器..."
echo "访问: http://localhost:5173"
echo ""
echo "按 Ctrl+C 停止服务器"
echo ""

# 启动前端开发服务器
npm run dev
