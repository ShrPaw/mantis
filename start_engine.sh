#!/bin/bash
# MANTIS Execution Engine — Start Script
# Starts the engine and dashboard server

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== MANTIS Execution Engine ==="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip install -q -r engine/requirements.txt 2>/dev/null || true

# Create data directories
mkdir -p data/events data/metrics

echo ""
echo "Starting MANTIS Execution Engine..."
echo "  Config: config/mantis_execution_config.yaml"
echo "  Dashboard: http://localhost:8001"
echo "  WebSocket: ws://localhost:8001/ws"
echo ""

# Start dashboard server in background
python3 -c "from engine.dashboard_server import run_dashboard; run_dashboard(port=8001)" &
DASHBOARD_PID=$!
echo "Dashboard server started (PID: $DASHBOARD_PID)"

# Start engine (foreground)
python3 -m engine.run --config config/mantis_execution_config.yaml

# Cleanup on exit
kill $DASHBOARD_PID 2>/dev/null || true
