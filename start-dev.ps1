# Crazytra Development Environment Startup Script (Windows)

Write-Host "Starting Crazytra Development Environment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check Docker
$dockerCheck = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCheck) {
    Write-Host "Docker is not installed or not running" -ForegroundColor Red
    Write-Host "Please install and start Docker Desktop first" -ForegroundColor Yellow
    exit 1
}
Write-Host "Docker is installed" -ForegroundColor Green

# Check Node.js
$nodeCheck = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCheck) {
    Write-Host "Node.js is not installed" -ForegroundColor Red
    Write-Host "Please visit https://nodejs.org/ to install Node.js 18+" -ForegroundColor Yellow
    exit 1
}
$nodeVersion = node -v
Write-Host "Node.js $nodeVersion is installed" -ForegroundColor Green

Write-Host ""
Write-Host "Starting backend services..." -ForegroundColor Cyan

# Start Docker services
docker-compose up -d redis timescaledb ollama

Write-Host ""
Write-Host "Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check service status
Write-Host ""
Write-Host "Checking service status..." -ForegroundColor Cyan
docker-compose ps

Write-Host ""
Write-Host "Configuring frontend environment..." -ForegroundColor Cyan

# Enter frontend directory
Set-Location frontend

# Check .env file
if (-not (Test-Path .env)) {
    Write-Host "Creating .env file..." -ForegroundColor Yellow
    Copy-Item .env.example .env
}

# Check dependencies
if (-not (Test-Path node_modules)) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    npm install
}

Write-Host ""
Write-Host "Environment setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Starting frontend development server..." -ForegroundColor Cyan
Write-Host "Visit: http://localhost:5173" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Start frontend development server
npm run dev
