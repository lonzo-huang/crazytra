#!/bin/bash
# Git 提交脚本 - Nautilus Trader 整合

set -e

echo "=========================================="
echo "Crazytra - Git 提交助手"
echo "=========================================="
echo ""

# 检查是否在 git 仓库中
if [ ! -d .git ]; then
    echo "初始化 Git 仓库..."
    git init
    echo "✓ Git 仓库已初始化"
    echo ""
fi

# 检查 .gitignore
if [ ! -f .gitignore ]; then
    echo "错误: .gitignore 文件不存在"
    exit 1
fi

# 显示当前状态
echo "当前状态:"
git status --short

echo ""
echo "=========================================="
echo "准备提交的文件:"
echo "=========================================="

# 添加所有文件
git add .

# 显示将要提交的文件
git status --short

echo ""
read -p "是否继续提交? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

# 获取提交信息
echo ""
echo "请输入提交信息（默认: feat: Nautilus Trader 整合完成）:"
read -r commit_message

if [ -z "$commit_message" ]; then
    commit_message="feat: Nautilus Trader 整合完成

- 整合 Nautilus Trader 1.204.0 作为核心交易引擎
- 实现 RedisBridgeActor 桥接 Nautilus 与 Redis
- 实现 LLMWeightActor 支持 LLM 权重注入
- 创建 CrazytraStrategy 基类支持 LLM 增强
- 添加完整的测试验证系统
- 更新所有文档（ARCHITECTURE.md, INSTALLATION.md, README.md）
- 保持 Redis Streams 作为外部系统桥接
- 前端和 API 网关零修改

详细文档:
- nautilus-core/README.md - Nautilus 整合文档
- nautilus-core/QUICKSTART.md - 5分钟快速开始
- nautilus-core/TESTING.md - 测试指南
- INSTALLATION.md - 完整安装指南"
fi

# 提交
echo ""
echo "提交中..."
git commit -m "$commit_message"

echo ""
echo "✓ 提交成功"
echo ""

# 检查远程仓库
if git remote -v | grep -q origin; then
    echo "检测到远程仓库 origin"
    echo ""
    read -p "是否推送到远程仓库? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 获取当前分支
        current_branch=$(git branch --show-current)
        
        echo "推送到 origin/$current_branch..."
        git push origin "$current_branch"
        
        echo ""
        echo "✓ 推送成功"
    fi
else
    echo "未配置远程仓库"
    echo ""
    echo "要添加远程仓库，请运行:"
    echo "  git remote add origin https://github.com/your-username/Crazytra.git"
    echo "  git push -u origin main"
fi

echo ""
echo "=========================================="
echo "完成！"
echo "=========================================="
