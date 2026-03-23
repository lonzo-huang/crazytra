#!/bin/bash
# 回测快速开始脚本

set -e

echo "🚀 Nautilus Trader 回测快速开始"
echo "================================"

# 检查 Python
if ! command -v python &> /dev/null; then
    echo "❌ Python 未安装"
    exit 1
fi

echo "✅ Python 已安装"

# 检查依赖
echo "📦 检查依赖..."
if ! pip show nautilus_trader &> /dev/null; then
    echo "📥 安装 Nautilus Trader..."
    pip install nautilus_trader
fi

if ! pip show ccxt &> /dev/null; then
    echo "📥 安装 ccxt（用于下载数据）..."
    pip install ccxt
fi

if ! pip show pyyaml &> /dev/null; then
    echo "📥 安装 PyYAML..."
    pip install pyyaml
fi

echo "✅ 依赖已安装"

# 下载示例数据
echo ""
echo "📊 下载示例数据..."
echo "❓ 选择数据源："
echo "  1) Binance 真实数据（需要网络）"
echo "  2) 模拟数据（快速测试）"
read -p "请选择 [1/2]: " choice

case $choice in
    1)
        echo "📥 从 Binance 下载数据..."
        python backtest/scripts/download_sample_data.py \
            --symbol BTCUSDT \
            --days 30 \
            --source binance
        ;;
    2)
        echo "🎲 生成模拟数据..."
        python backtest/scripts/download_sample_data.py \
            --symbol BTCUSDT \
            --days 30 \
            --source sample
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

echo "✅ 数据准备完成"

# 运行回测
echo ""
echo "🎯 运行回测..."
python backtest/run_backtest.py --config backtest/configs/ma_cross_example.yaml

echo ""
echo "✅ 回测完成！"
echo "📁 结果保存在: ./backtest/results/"
