#!/bin/bash

# Option Chain Dashboard - Startup Script
# Starts all services: Backend + Frontend

echo "======================================================================"
echo "  Option Chain Dashboard - Startup"
echo "======================================================================"
echo ""

# Get the project directory (repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

echo "✓ Project directory: $PROJECT_DIR"
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run:"
    echo "   python -m venv venv"
    echo "   source venv/bin/activate"
    echo "   pip install -r requirements.txt"
    exit 1
fi

echo "✓ Virtual environment found"
echo ""

# Activate venv
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Check if npm dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "⚠ Frontend dependencies not installed. Installing..."
    cd frontend
    npm install
    cd ..
    echo "✓ Frontend dependencies installed"
else
    echo "✓ Frontend dependencies found"
fi

echo ""
echo "======================================================================"
echo "  STARTING SERVICES"
echo "======================================================================"
echo ""
echo "Backend (FastAPI on :8061):  venv/bin/python main.py --demo-mode"
echo "Frontend (React on :8060):    cd frontend && npm run dev"
echo ""
echo "Open in browser:             http://localhost:8060"
echo ""
echo "======================================================================"
echo ""

# Start backend
echo "🚀 Starting Backend..."
./venv/bin/python main.py --demo-mode &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
echo "🚀 Starting Frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for both processes
echo ""
echo "✓ Both services should now be running!"
echo ""
echo "Backend:  http://localhost:8061"
echo "API Docs: http://localhost:8061/docs"
echo "Frontend: http://localhost:8060"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for keyboard interrupt
trap "kill $BACKEND_PID $FRONTEND_PID; exit 0" SIGINT SIGTERM
wait
