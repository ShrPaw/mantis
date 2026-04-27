"""
Auction Failure Research — Runner

Main entry point. Connects to MANTIS data feed,
runs detectors, tracks outcomes, exports CSV.

Usage:
  # Standalone (replay from JSONL):
  python -m research.auction_failure.runner --replay backend/data/events/events_raw.jsonl

  # Live (attach to running MANTIS):
  python -m research.auction_failure.runner --live

Shadow mode only. No production integration.
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

# Add parent to path for MANTIS imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from .config import AuctionFailureConfig
from .models import AuctionEvent, CSV_FIELDS
from .data_adapter import LiveDataFeed
from .detectors import AuctionDetectors
from .outcomes import OutcomeTracker
from .analytics import (
    compute_all_stats,
    compute_time_split_stats,
    compute_10min_blocks,
    compute_directional_returns,
)


class AuctionFailureRunner:
    """
    Orchestrates the research pipeline:
    1. Receive trade data
    2. Run detectors
    3. Track outcomes
    4. Export CSV
    5. Generate report
    """

    def __init__(self, config: AuctionFailureConfig = None):
        self.config = config or AuctionFailureConfig()
        self.feed = LiveDataFeed(self.config.detection.buffer_depth_seconds)
        self.detectors = AuctionDetectors(self.config)
        self.outcomes = OutcomeTracker(self.config.outcome)

        self._events: list[AuctionEvent] = []
        self._last_fire: dict[str, float] = {}
        self._detection_count: int = 0
        self._tick_count: int = 0

    def on_trade(self, price: float, qty: float, delta: float, timestamp: float):
        """Process a single trade tick."""
        # Feed data
        self.feed.on_trade(price, qty, delta, timestamp)
        self._tick_count += 1

        # Update outcomes for existing events
        self.outcomes.update(price, timestamp)

        # Run detectors
        if self.feed.window.count < 20:
            return

        events = self.detectors.detect_all(self.feed.window, timestamp)

        for event in events:
            # Cooldown check
            key = f"{event.event_class}:{event.side}"
            last = self._last_fire.get(key, 0)
            if timestamp - last < self.config.detection.cooldown_seconds:
                continue

            # Register for outcome tracking
            self.outcomes.register(event, price)
            self._events.append(event)
            self._last_fire[key] = timestamp
            self._detection_count += 1

    def export_csv(self, path: str):
        """Export all events to CSV."""
        if not self._events:
            print(f"No events to export.")
            return

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for event in self._events:
                writer.writerow(event.to_csv_row())

        print(f"Exported {len(self._events)} events to {path}")

    def get_summary(self) -> dict:
        """Get runner summary."""
        by_class = {}
        for e in self._events:
            by_class[e.event_class] = by_class.get(e.event_class, 0) + 1

        complete = sum(1 for e in self._events if e.is_complete)

        return {
            "total_ticks": self._tick_count,
            "total_events": len(self._events),
            "complete_events": complete,
            "pending_outcomes": self.outcomes.pending_count,
            "by_class": by_class,
            "detection_count": self._detection_count,
        }

    def generate_report(self) -> str:
        """Generate the full research report."""
        from .report import generate_report
        return generate_report(self._events, self.config)


def run_replay(jsonl_path: str, output_csv: str, output_report: str):
    """Replay events from a JSONL file through the research detectors."""
    print(f"Replaying from: {jsonl_path}")

    if not os.path.exists(jsonl_path):
        print(f"ERROR: File not found: {jsonl_path}")
        sys.exit(1)

    runner = AuctionFailureRunner()

    # Load and replay trades
    with open(jsonl_path, 'r') as f:
        lines = f.readlines()

    print(f"Loaded {len(lines)} lines from JSONL")

    # Parse events from MANTIS format
    # The JSONL contains MicrostructureEvent objects, not raw trades
    # We need to extract price/delta information
    trade_count = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            # Extract trade data from the event
            price = data.get("price", 0)
            raw = data.get("raw_metrics", {})
            total_vol = raw.get("total_volume", raw.get("volume", 0))
            total_delta = raw.get("total_delta", raw.get("delta", 0))
            timestamp = data.get("timestamp", 0)

            if price > 0 and total_vol > 0:
                # Simulate as a single trade
                runner.on_trade(price, total_vol, total_delta, timestamp)
                trade_count += 1
        except (json.JSONDecodeError, KeyError) as e:
            continue

    print(f"Processed {trade_count} trade records")
    summary = runner.get_summary()
    print(f"Summary: {json.dumps(summary, indent=2)}")

    # Export
    runner.export_csv(output_csv)

    # Generate report
    report = runner.generate_report()
    with open(output_report, 'w') as f:
        f.write(report)
    print(f"Report written to: {output_report}")


def run_live():
    """Attach to live MANTIS engine and collect data."""
    print("Live mode: attempting to connect to MANTIS backend...")

    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
        from event_engine.context import EngineContext
        from event_engine.manager import EventManager
        print("MANTIS modules found.")
    except ImportError:
        print("ERROR: Cannot import MANTIS backend modules.")
        print("Run from the mantis/ root directory.")
        sys.exit(1)

    runner = AuctionFailureRunner()

    print("Starting live collection. Press Ctrl+C to stop.")
    print("Events will be saved to data/research/auction_events.csv")

    try:
        # This would need to be connected to the actual MANTIS data feed
        # For now, we'll create a simple polling loop
        print("NOTE: Live collection requires MANTIS backend to be running.")
        print("Use --replay mode with collected data for analysis.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        summary = runner.get_summary()
        print(f"Final summary: {json.dumps(summary, indent=2)}")
        runner.export_csv("data/research/auction_events.csv")
        report = runner.generate_report()
        with open("AUCTION_FAILURE_RESEARCH_REPORT.md", 'w') as f:
            f.write(report)
        print("Report written.")


def main():
    parser = argparse.ArgumentParser(
        description="Auction Failure Research — MANTIS"
    )
    parser.add_argument(
        "--replay", type=str, default=None,
        help="Path to JSONL file for replay analysis"
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Attach to live MANTIS engine"
    )
    parser.add_argument(
        "--output-csv", type=str,
        default="data/research/auction_events.csv",
        help="Output CSV path"
    )
    parser.add_argument(
        "--output-report", type=str,
        default="AUCTION_FAILURE_RESEARCH_REPORT.md",
        help="Output report path"
    )
    args = parser.parse_args()

    if args.replay:
        run_replay(args.replay, args.output_csv, args.output_report)
    elif args.live:
        run_live()
    else:
        print("Specify --replay <path> or --live")
        parser.print_help()


if __name__ == "__main__":
    main()
