"""
MANTIS — Unified Configuration Settings.

Centralizes all application configuration.
Environment variables override defaults.
"""

import os

# Server
HOST = os.environ.get("MANTIS_HOST", "0.0.0.0")
PORT = int(os.environ.get("MANTIS_PORT", "8000"))

# Event Engine
EVENT_ENGINE_ENABLED = os.environ.get("EVENT_ENGINE_ENABLED", "true").lower() in ("true", "1", "yes")

# SPE Module
SPE_ENABLED = os.environ.get("SPE_ENABLED", "true").lower() in ("true", "1", "yes")
SPE_OBSERVATION_ONLY = os.environ.get("SPE_OBSERVATION_ONLY", "true").lower() in ("true", "1", "yes")

# Historical candles
HISTORICAL_CANDLE_LIMIT = int(os.environ.get("MANTIS_CANDLE_LIMIT", "1000"))

# CORS
CORS_ORIGINS = os.environ.get("MANTIS_CORS_ORIGINS", "*").split(",")
