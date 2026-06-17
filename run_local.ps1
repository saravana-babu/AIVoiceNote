# VoiceMind AI Local Run Launcher (Windows PowerShell)
# ==========================================================

Write-Host "Checking prerequisites..." -ForegroundColor Cyan

# Check Node/NPM
if (!(Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "npm is not installed. Please install Node.js."
    Exit 1
}

# Check uv
if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed. Please install uv (e.g. 'pip install uv' or visit https://github.com/astral-sh/uv)."
    Exit 1
}

Write-Host "Prerequisites met. Initializing dependencies..." -ForegroundColor Cyan

# Install node dependencies and build packages
Write-Host "Installing npm dependencies..." -ForegroundColor Gray
npm install

Write-Host "Building shared package workspaces..." -ForegroundColor Gray
npx turbo run build

# Install Python dependencies in backend
Write-Host "Syncing backend Python packages with uv..." -ForegroundColor Gray
cd backend
uv sync
cd ..

Write-Host "`nStarting services in separate windows..." -ForegroundColor Green

# Start backend in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; uv run uvicorn main:app --reload --port 8000" -WindowStyle Normal

# Start mobile frontend in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd apps/mobile; npm run start" -WindowStyle Normal

Write-Host "Both servers launched successfully! Check the newly opened PowerShell windows." -ForegroundColor Green
