# Git 提交脚本 - Nautilus Trader 整合 (Windows PowerShell)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Crazytra - Git 提交助手" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否在 git 仓库中
if (-not (Test-Path .git)) {
    Write-Host "初始化 Git 仓库..." -ForegroundColor Yellow
    git init
    Write-Host "✓ Git 仓库已初始化" -ForegroundColor Green
    Write-Host ""
}

# 检查 .gitignore
if (-not (Test-Path .gitignore)) {
    Write-Host "错误: .gitignore 文件不存在" -ForegroundColor Red
    exit 1
}

# 显示当前状态
Write-Host "当前状态:" -ForegroundColor Yellow
git status --short

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "准备提交的文件:" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 添加所有文件
git add .

# 显示将要提交的文件
git status --short

Write-Host ""
$response = Read-Host "是否继续提交? (y/n)"
if ($response -ne "y") {
    Write-Host "已取消" -ForegroundColor Yellow
    exit 0
}

# 获取提交信息
Write-Host ""
Write-Host "请输入提交信息（留空使用默认信息）:" -ForegroundColor Yellow
$commit_message = Read-Host

if ([string]::IsNullOrWhiteSpace($commit_message)) {
    $commit_message = @"
feat: Nautilus Trader 整合完成

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
- INSTALLATION.md - 完整安装指南
"@
}

# 提交
Write-Host ""
Write-Host "提交中..." -ForegroundColor Yellow
git commit -m $commit_message

Write-Host ""
Write-Host "✓ 提交成功" -ForegroundColor Green
Write-Host ""

# 检查远程仓库
$hasRemote = git remote -v | Select-String "origin"
if ($hasRemote) {
    Write-Host "检测到远程仓库 origin" -ForegroundColor Yellow
    Write-Host ""
    $pushResponse = Read-Host "是否推送到远程仓库? (y/n)"
    
    if ($pushResponse -eq "y") {
        # 获取当前分支
        $current_branch = git branch --show-current
        
        Write-Host "推送到 origin/$current_branch..." -ForegroundColor Yellow
        git push origin $current_branch
        
        Write-Host ""
        Write-Host "✓ 推送成功" -ForegroundColor Green
    }
} else {
    Write-Host "未配置远程仓库" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "要添加远程仓库，请运行:" -ForegroundColor Cyan
    Write-Host "  git remote add origin https://github.com/your-username/Crazytra.git" -ForegroundColor White
    Write-Host "  git push -u origin main" -ForegroundColor White
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
