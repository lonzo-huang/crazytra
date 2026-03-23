# 回测快速开始脚本 (Windows PowerShell)

Write-Host "🚀 Nautilus Trader 回测快速开始" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# 检查 Python
try {
    $null = python --version 2>&1
    Write-Host "✅ Python 已安装" -ForegroundColor Green
} catch {
    Write-Host "❌ Python 未安装" -ForegroundColor Red
    exit 1
}

# 检查依赖
Write-Host "📦 检查依赖..." -ForegroundColor Cyan

$packages = @("nautilus_trader", "ccxt", "pyyaml")
foreach ($package in $packages) {
    try {
        $null = pip show $package 2>&1
    } catch {
        Write-Host "📥 安装 $package..." -ForegroundColor Yellow
        pip install $package
    }
}

Write-Host "✅ 依赖已安装" -ForegroundColor Green

# 下载示例数据
Write-Host ""
Write-Host "📊 下载示例数据..." -ForegroundColor Cyan
Write-Host "❓ 选择数据源：" -ForegroundColor Yellow
Write-Host "  1) Binance 真实数据（需要网络）"
Write-Host "  2) 模拟数据（快速测试）"
$choice = Read-Host "请选择 [1/2]"

switch ($choice) {
    "1" {
        Write-Host "📥 从 Binance 下载数据..." -ForegroundColor Yellow
        python backtest/scripts/download_sample_data.py `
            --symbol BTCUSDT `
            --days 30 `
            --source binance
    }
    "2" {
        Write-Host "🎲 生成模拟数据..." -ForegroundColor Yellow
        python backtest/scripts/download_sample_data.py `
            --symbol BTCUSDT `
            --days 30 `
            --source sample
    }
    default {
        Write-Host "❌ 无效选择" -ForegroundColor Red
        exit 1
    }
}

Write-Host "✅ 数据准备完成" -ForegroundColor Green

# 运行回测
Write-Host ""
Write-Host "🎯 运行回测..." -ForegroundColor Cyan
python backtest/run_backtest.py --config backtest/configs/ma_cross_example.yaml

Write-Host ""
Write-Host "✅ 回测完成！" -ForegroundColor Green
Write-Host "📁 结果保存在: ./backtest/results/" -ForegroundColor Cyan
