# Crazytra 开发环境一键启动脚本 (Windows)

Write-Host "🚀 启动 Crazytra 开发环境" -ForegroundColor Cyan
Write-Host "============================" -ForegroundColor Cyan

# 检查 Docker
try {
    docker --version | Out-Null
    Write-Host "✅ Docker 已安装" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker 未安装或未运行" -ForegroundColor Red
    Write-Host "请先安装并启动 Docker Desktop" -ForegroundColor Yellow
    exit 1
}

# 检查 Node.js
try {
    $nodeVersion = node -v
    Write-Host "✅ Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js 未安装" -ForegroundColor Red
    Write-Host "请访问 https://nodejs.org/ 安装 Node.js 18+" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "📦 启动后端服务..." -ForegroundColor Cyan

# 启动 Docker 服务
docker-compose up -d redis timescaledb ollama

Write-Host ""
Write-Host "⏳ 等待服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 检查服务状态
Write-Host ""
Write-Host "🔍 检查服务状态..." -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "📊 配置前端环境..." -ForegroundColor Cyan

# 进入前端目录
Set-Location frontend

# 检查 .env 文件
if (-not (Test-Path .env)) {
    Write-Host "📝 创建 .env 文件..." -ForegroundColor Yellow
    Copy-Item .env.example .env
}

# 检查依赖
if (-not (Test-Path node_modules)) {
    Write-Host "📦 安装前端依赖..." -ForegroundColor Yellow
    npm install
}

Write-Host ""
Write-Host "✅ 环境准备完成！" -ForegroundColor Green
Write-Host ""
Write-Host "🎯 启动前端开发服务器..." -ForegroundColor Cyan
Write-Host "访问: http://localhost:5173" -ForegroundColor Yellow
Write-Host ""
Write-Host "按 Ctrl+C 停止服务器" -ForegroundColor Gray
Write-Host ""

# 启动前端开发服务器
npm run dev
