"""
MANTIS Event Manager Service — Thin wrapper for Event Engine initialization.

Provides a single function to create and configure the EventManager
with proper error handling and logging.
"""

import logging
import os

logger = logging.getLogger(__name__)

# Feature flag: set EVENT_ENGINE_ENABLED=false to disable
EVENT_ENGINE_ENABLED = os.environ.get("EVENT_ENGINE_ENABLED", "true").lower() in ("true", "1", "yes")


def create_event_manager():
    """
    Create and return an EventManager instance.
    Returns None if the event engine is disabled or fails to load.
    """
    if not EVENT_ENGINE_ENABLED:
        logger.info("Event Engine Pro: DISABLED (EVENT_ENGINE_ENABLED=false)")
        return None

    try:
        from app.event_engine import EventManager
        mgr = EventManager()
        logger.info("Event Engine Pro: ENABLED")
        return mgr
    except Exception as e:
        logger.warning(f"Event Engine Pro: FAILED TO LOAD — {e}. MANTIS continues without it.")
        return None
