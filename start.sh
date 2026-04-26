#!/usr/bin/env bash
# Start the BTC Microstructure Dashboard (backend + frontend)
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== BTCUSDT Microstructure Dashboard ==="
echo ""
echo "Starting backend on :8000 ..."
cd "$DIR/backend"
python3 main.py &
BACKEND_PID=$!

echo "Starting frontend on :3000 ..."
cd "$DIR/frontend"
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  Health:   http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
