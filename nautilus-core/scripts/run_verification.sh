#!/bin/bash
# Nautilus 整合验证脚本启动器

set -e

echo "=========================================="
echo "Nautilus Trader 整合验证"
echo "=========================================="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 检查是否在虚拟环境中
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo "警告: 未检测到虚拟环境"
    echo "建议: source venv/bin/activate"
    echo ""
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 安装测试依赖
echo "检查测试依赖..."
pip install -q -r scripts/requirements-test.txt

# 运行验证脚本
echo ""
echo "开始验证..."
echo ""

python3 scripts/verify_integration.py "$@"

exit_code=$?

echo ""
if [ $exit_code -eq 0 ]; then
    echo "✓ 验证完成"
else
    echo "✗ 验证失败，请检查输出"
fi

exit $exit_code
