@echo off
REM ============================================
REM  MANTIS — Windows Startup Script
REM ============================================
REM
REM  OPTION 1: Direct connection (no proxy)
REM    Just run this script as-is.
REM
REM  OPTION 2: Through a proxy
REM    Uncomment and set your proxy below:
REM
REM    set HTTPS_PROXY=socks5://127.0.0.1:1080
REM    set HTTPS_PROXY=http://127.0.0.1:7890
REM
REM  Common proxy ports:
REM    Clash:        SOCKS5=7891  HTTP=7890
REM    V2Ray:        SOCKS5=10808 HTTP=10809
REM    Shadowsocks:  SOCKS5=1080
REM ============================================

REM --- Uncomment ONE line below and set your proxy ---
REM set HTTPS_PROXY=socks5://127.0.0.1:1080
REM set HTTPS_PROXY=http://127.0.0.1:7890

echo.
echo  MANTIS BTCUSDT Microstructure Dashboard
echo  ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

REM Install dependencies
echo  Installing dependencies...
pip install -r requirements.txt -q 2>nul
if defined HTTPS_PROXY (
    pip install python-socks[asyncio] -q 2>nul
)

echo.
if defined HTTPS_PROXY (
    echo  Proxy: %HTTPS_PROXY%
) else (
    echo  Proxy: NONE (direct connection)
    echo  If Binance is blocked, edit this script and set HTTPS_PROXY.
)
echo.
echo  Starting backend on http://localhost:8000
echo  Press Ctrl+C to stop.
echo.

python main.py
