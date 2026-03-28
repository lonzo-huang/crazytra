# 启动 API Gateway 脚本
Write-Host "🚀 启动 MirrorQuant API Gateway..." -ForegroundColor Green

# 检查 Go 是否安装
try {
    $goVersion = go version 2>$null
    Write-Host "✅ Go 版本: $goVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Go 未安装" -ForegroundColor Red
    Write-Host "📦 请从 https://golang.org/dl/ 下载安装 Go" -ForegroundColor Yellow
    exit 1
}

# 进入 API Gateway 目录
Set-Location api-gateway

Write-Host "🔨 构建 API Gateway..." -ForegroundColor Blue
go mod tidy

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 依赖安装失败" -ForegroundColor Red
    exit 1
}

Write-Host "🌐 启动 API Gateway..." -ForegroundColor Blue
Write-Host "📍 服务地址: http://localhost:8080" -ForegroundColor Cyan
Write-Host "📊 API 文档: http://localhost:8080/docs" -ForegroundColor Cyan
Write-Host "🔍 健康检查: http://localhost:8080/health" -ForegroundColor Cyan

# 启动服务
go run src/main.go
