# 前端环境配置脚本 (Windows PowerShell)

Write-Host "🚀 Crazytra 前端环境配置" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan

# 检查 Node.js
try {
    $nodeVersion = node -v
    $versionNumber = [int]($nodeVersion -replace 'v(\d+)\..*', '$1')
    
    if ($versionNumber -lt 18) {
        Write-Host "❌ Node.js 版本过低 (需要 18+)" -ForegroundColor Red
        Write-Host "当前版本: $nodeVersion" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "✅ Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Node.js 未安装" -ForegroundColor Red
    Write-Host "请访问 https://nodejs.org/ 安装 Node.js 18+" -ForegroundColor Yellow
    exit 1
}

# 检查 npm
try {
    $npmVersion = npm -v
    Write-Host "✅ npm $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ npm 未安装" -ForegroundColor Red
    exit 1
}

# 创建 .env 文件
if (-not (Test-Path .env)) {
    Write-Host ""
    Write-Host "📝 创建 .env 配置文件..." -ForegroundColor Cyan
    Copy-Item .env.example .env
    Write-Host "✅ .env 文件已创建" -ForegroundColor Green
    Write-Host ""
    Write-Host "请编辑 .env 文件配置 API 地址：" -ForegroundColor Yellow
    Write-Host "  VITE_API_URL=http://localhost:8080"
    Write-Host "  VITE_WS_URL=ws://localhost:8080/ws"
} else {
    Write-Host "✅ .env 文件已存在" -ForegroundColor Green
}

# 安装依赖
Write-Host ""
Write-Host "📦 安装依赖..." -ForegroundColor Cyan
npm install

Write-Host ""
Write-Host "✅ 环境配置完成！" -ForegroundColor Green
Write-Host ""
Write-Host "🎯 下一步：" -ForegroundColor Cyan
Write-Host "  1. 编辑 .env 文件（如果需要）"
Write-Host "  2. 运行 'npm run dev' 启动开发服务器"
Write-Host "  3. 访问 http://localhost:5173"
Write-Host ""
