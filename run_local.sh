#!/bin/bash
# VoiceMind AI Local Run Launcher (Unix/Bash/Git Bash/WSL)
# ==========================================================
set -e

echo "Checking prerequisites..."
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm is not installed. Please install Node.js."
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "ERROR: uv is not installed. Please install uv (https://github.com/astral-sh/uv)."
    exit 1
fi

echo "Prerequisites met. Initializing dependencies..."
echo "Installing npm dependencies..."
npm install

echo "Building shared package workspaces..."
npx turbo run build

echo "Syncing backend Python packages with uv..."
cd backend
uv sync
cd ..

echo "Starting services..."

# Run backend in the background
cd backend
uv run uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Run frontend in the background
cd apps/mobile
npm run start &
FRONTEND_PID=$!
cd ../..

echo "--------------------------------------------------------"
echo "Both servers launched successfully!"
echo "Backend Process ID: $BACKEND_PID"
echo "Frontend Process ID: $FRONTEND_PID"
echo "Press Ctrl+C to terminate both servers."
echo "--------------------------------------------------------"

# Kill both background processes when this script exits/is cancelled
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true" EXIT
wait
