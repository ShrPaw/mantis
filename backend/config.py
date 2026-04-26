"""
MANTIS configuration — edit this file or use environment variables.
Environment variables take precedence over these defaults.
"""

import os

# --- Proxy Settings ---
# Set your proxy URL here, or use HTTPS_PROXY env var.
# Examples:
#   "socks5://127.0.0.1:1080"   — Clash, V2Ray, Shadowsocks local SOCKS5
#   "http://127.0.0.1:7890"     — Clash HTTP proxy
#   ""                           — no proxy (direct connection)
PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""

# --- Binance WebSocket ---
BINANCE_WS_URL = "wss://fstream.binance.com/ws"

# --- Server ---
BACKEND_HOST = "0.0.0.0"
BACKEND_PORT = 8000

# --- Metrics ---
LARGE_TRADE_THRESHOLD = 0.5  # BTC
ROLLING_WINDOW = 300         # seconds
MAX_FOOTPRINT_CANDLES = 60
FOOTPRINT_TICK_SIZE = 0.10   # $0.10 price buckets
