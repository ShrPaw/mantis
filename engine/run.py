"""MANTIS Execution Engine — Main entry point.

Usage:
    python -m engine.run                     # Run with default config
    python -m engine.run --config path.yaml  # Run with custom config
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from engine.manager import MantisEngine


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    logging.basicConfig(level=getattr(logging, level.upper()), format=fmt)
    # Reduce noise from websockets
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("websockets.client").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description="MANTIS Execution Engine")
    parser.add_argument("--config", default="config/mantis_execution_config.yaml",
                        help="Path to config YAML file")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Logging level")
    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger("mantis.main")

    engine = MantisEngine(config_path=args.config)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Graceful shutdown
    def shutdown(sig, frame):
        logger.info(f"Received {sig}, shutting down...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        loop.run_until_complete(engine.run())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        loop.run_until_complete(engine.stop())
        loop.close()
        logger.info("MANTIS Engine exited.")


if __name__ == "__main__":
    main()
