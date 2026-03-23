# Nautilus 整合验证脚本启动器 (Windows PowerShell)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Nautilus Trader 整合验证" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "错误: 未找到 python" -ForegroundColor Red
    exit 1
}

# 检查虚拟环境
if (-not $env:VIRTUAL_ENV) {
    Write-Host "警告: 未检测到虚拟环境" -ForegroundColor Yellow
    Write-Host "建议: .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host ""
    $response = Read-Host "是否继续? (y/n)"
    if ($response -ne "y") {
        exit 1
    }
}

# 安装测试依赖
Write-Host "检查测试依赖..." -ForegroundColor Yellow
pip install -q -r scripts/requirements-test.txt

# 运行验证脚本
Write-Host ""
Write-Host "开始验证..." -ForegroundColor Green
Write-Host ""

python scripts/verify_integration.py $args

$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "✓ 验证完成" -ForegroundColor Green
} else {
    Write-Host "✗ 验证失败，请检查输出" -ForegroundColor Red
}

exit $exitCode
