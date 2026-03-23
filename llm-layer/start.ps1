# LLM 层快速启动脚本 (Windows PowerShell)

Write-Host "🚀 Crazytra LLM 层启动脚本" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# 检查 .env 文件
if (-not (Test-Path .env)) {
    Write-Host "⚠️  未找到 .env 文件" -ForegroundColor Yellow
    Write-Host "📝 正在从 .env.example 创建..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "✅ 已创建 .env 文件，请编辑并填写配置" -ForegroundColor Green
    exit 1
}

# 加载 .env 文件
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

# 检查 Redis
Write-Host "🔍 检查 Redis 连接..." -ForegroundColor Cyan
$redisUrl = if ($env:REDIS_URL) { $env:REDIS_URL } else { "redis://localhost:6379" }
try {
    $null = redis-cli -u $redisUrl PING 2>&1
    Write-Host "✅ Redis 连接正常" -ForegroundColor Green
} catch {
    Write-Host "❌ Redis 未运行" -ForegroundColor Red
    Write-Host "💡 启动 Redis: docker run -d -p 6379:6379 redis:7-alpine" -ForegroundColor Yellow
    exit 1
}

# 检查 Ollama
Write-Host "🔍 检查 Ollama 服务..." -ForegroundColor Cyan
$ollamaUrl = if ($env:OLLAMA_BASE_URL) { $env:OLLAMA_BASE_URL } else { "http://localhost:11434" }
try {
    $response = Invoke-WebRequest -Uri "$ollamaUrl/api/tags" -UseBasicParsing -ErrorAction Stop
    Write-Host "✅ Ollama 服务正常" -ForegroundColor Green
    
    # 检查模型
    $model = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { "mistral:7b-instruct-q4_K_M" }
    $models = ollama list 2>&1
    if ($models -notmatch $model) {
        Write-Host "⚠️  模型 $model 未安装" -ForegroundColor Yellow
        Write-Host "📥 正在拉取模型..." -ForegroundColor Yellow
        ollama pull $model
    }
    Write-Host "✅ 模型 $model 已就绪" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Ollama 未运行" -ForegroundColor Yellow
    Write-Host "💡 安装 Ollama: https://ollama.com/download" -ForegroundColor Yellow
    Write-Host "💡 启动 Ollama: ollama serve" -ForegroundColor Yellow
    Write-Host "💡 拉取模型: ollama pull mistral:7b-instruct-q4_K_M" -ForegroundColor Yellow
    Write-Host ""
    $response = Read-Host "❓ 是否继续（将使用云端 LLM）？ [y/N]"
    if ($response -notmatch '^[Yy]$') {
        exit 1
    }
}

# 安装依赖
Write-Host "📦 检查 Python 依赖..." -ForegroundColor Cyan
try {
    $null = pip show aiohttp 2>&1
    Write-Host "✅ 依赖已安装" -ForegroundColor Green
} catch {
    Write-Host "📥 安装依赖..." -ForegroundColor Yellow
    pip install -e .
}

# 启动 LLM 层
Write-Host ""
Write-Host "🎯 启动 LLM 层..." -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
python -m llm_layer.main
