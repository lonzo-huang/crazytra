#!/bin/bash
# 前端环境配置脚本 (Linux/macOS)

set -e

echo "🚀 Crazytra 前端环境配置"
echo "=========================="

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装"
    echo "请访问 https://nodejs.org/ 安装 Node.js 18+"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js 版本过低 (需要 18+)"
    echo "当前版本: $(node -v)"
    exit 1
fi

echo "✅ Node.js $(node -v)"

# 检查 npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm 未安装"
    exit 1
fi

echo "✅ npm $(npm -v)"

# 创建 .env 文件
if [ ! -f .env ]; then
    echo ""
    echo "📝 创建 .env 配置文件..."
    cp .env.example .env
    echo "✅ .env 文件已创建"
    echo ""
    echo "请编辑 .env 文件配置 API 地址："
    echo "  VITE_API_URL=http://localhost:8080"
    echo "  VITE_WS_URL=ws://localhost:8080/ws"
else
    echo "✅ .env 文件已存在"
fi

# 安装依赖
echo ""
echo "📦 安装依赖..."
npm install

echo ""
echo "✅ 环境配置完成！"
echo ""
echo "🎯 下一步："
echo "  1. 编辑 .env 文件（如果需要）"
echo "  2. 运行 'npm run dev' 启动开发服务器"
echo "  3. 访问 http://localhost:5173"
echo ""
