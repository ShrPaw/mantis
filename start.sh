#!/usr/bin/env bash
# MANTIS — BTC Microstructure Dashboard
# Starts backend (FastAPI :8000) + frontend (Vite :3000)
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "╔══════════════════════════════════════════╗"
echo "║  ◆ MANTIS — BTC Microstructure Dashboard ║"
echo "║  Source: Hyperliquid DEX (no API key)    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Backend
echo "[1/2] Starting backend on :8000 ..."
cd "$DIR/backend"
python3 main.py &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 2

# Frontend
echo "[2/2] Starting frontend on :3000 ..."
cd "$DIR/frontend"
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "  ┌─────────────────────────────────────┐"
echo "  │  Backend:  http://localhost:8000     │"
echo "  │  Frontend: http://localhost:3000     │"
echo "  │  Health:   http://localhost:8000/health│"
echo "  └─────────────────────────────────────┘"
echo ""
echo "  Press Ctrl+C to stop both services."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
