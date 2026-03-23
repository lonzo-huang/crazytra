# Start Frontend Only (Windows)

Write-Host "Starting Crazytra Frontend" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan

# Check Node.js
$nodeCheck = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCheck) {
    Write-Host "Node.js is not installed" -ForegroundColor Red
    Write-Host "Please visit https://nodejs.org/ to install Node.js 18+" -ForegroundColor Yellow
    exit 1
}

$nodeVersion = node -v
Write-Host "Node.js $nodeVersion" -ForegroundColor Green

# Enter frontend directory
Set-Location frontend

# Check .env file
if (-not (Test-Path .env)) {
    Write-Host "Creating .env file..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "Created .env file" -ForegroundColor Green
}

# Check dependencies
if (-not (Test-Path node_modules)) {
    Write-Host ""
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    npm install
}

Write-Host ""
Write-Host "Starting development server..." -ForegroundColor Cyan
Write-Host "Visit: http://localhost:5173" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Start development server
npm run dev
