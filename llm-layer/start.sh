#!/bin/bash
# LLM 层快速启动脚本

set -e

echo "🚀 Crazytra LLM 层启动脚本"
echo "================================"

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件"
    echo "📝 正在从 .env.example 创建..."
    cp .env.example .env
    echo "✅ 已创建 .env 文件，请编辑并填写配置"
    exit 1
fi

# 检查 Redis
echo "🔍 检查 Redis 连接..."
REDIS_URL=${REDIS_URL:-redis://localhost:6379}
if ! redis-cli -u "$REDIS_URL" PING > /dev/null 2>&1; then
    echo "❌ Redis 未运行"
    echo "💡 启动 Redis: docker run -d -p 6379:6379 redis:7-alpine"
    exit 1
fi
echo "✅ Redis 连接正常"

# 检查 Ollama
echo "🔍 检查 Ollama 服务..."
OLLAMA_URL=${OLLAMA_BASE_URL:-http://localhost:11434}
if ! curl -s "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    echo "⚠️  Ollama 未运行"
    echo "💡 安装 Ollama: curl -fsSL https://ollama.com/install.sh | sh"
    echo "💡 启动 Ollama: ollama serve"
    echo "💡 拉取模型: ollama pull mistral:7b-instruct-q4_K_M"
    echo ""
    echo "❓ 是否继续（将使用云端 LLM）？ [y/N]"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ Ollama 服务正常"
    
    # 检查模型
    MODEL=${OLLAMA_MODEL:-mistral:7b-instruct-q4_K_M}
    if ! ollama list | grep -q "$MODEL"; then
        echo "⚠️  模型 $MODEL 未安装"
        echo "📥 正在拉取模型..."
        ollama pull "$MODEL"
    fi
    echo "✅ 模型 $MODEL 已就绪"
fi

# 安装依赖
echo "📦 检查 Python 依赖..."
if ! pip show aiohttp > /dev/null 2>&1; then
    echo "📥 安装依赖..."
    pip install -e .
fi
echo "✅ 依赖已安装"

# 启动 LLM 层
echo ""
echo "🎯 启动 LLM 层..."
echo "================================"
python -m llm_layer.main
