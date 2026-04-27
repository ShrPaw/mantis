"""
Auction Failure Research — Offline Replay Tool

Replays raw trade data through the auction failure detectors.
For analyzing collected data without running the live system.

Usage:
  python research/auction_failure/replay.py --input data/research/trades.jsonl
  python research/auction_failure/replay.py --input backend/data/events/events_raw.jsonl --format events
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from .config import AuctionFailureConfig
from .runner import AuctionFailureRunner


def replay_trades(input_path: str, output_csv: str, output_report: str):
    """Replay raw trade data (from collector.py output)."""
    print(f"Replaying raw trades from: {input_path}")

    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    runner = AuctionFailureRunner()
    trade_count = 0
    error_count = 0

    with open(input_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                trade_type = data.get("type", "")

                # Collector output format: {"timestamp", "price", "qty", "side", "delta"}
                # No "type" field — detect by presence of "side" and "delta"
                if "price" in data and "qty" in data and "delta" in data:
                    price = data.get("price", 0)
                    qty = data.get("qty", 0)
                    delta = data.get("delta", 0)
                    ts = data.get("timestamp", 0)

                    if price > 0 and qty > 0:
                        runner.on_trade(price, qty, delta, ts)
                        trade_count += 1

                elif trade_type == "large_trade":
                    price = data.get("price", 0)
                    qty = data.get("qty", 0)
                    delta = data.get("delta", 0)
                    ts = data.get("timestamp", 0)

                    if price > 0 and qty > 0:
                        runner.on_trade(price, qty, delta, ts)
                        trade_count += 1

                elif trade_type == "flow_metrics":
                    # Can extract price from flow metrics
                    price = data.get("data", {}).get("last_price", 0)
                    if price > 0:
                        # Treat as a synthetic trade with estimated volume
                        ts = data.get("timestamp", time.time())
                        runner.on_trade(price, 0.01, 0, ts)  # minimal volume
                        trade_count += 1

            except (json.JSONDecodeError, KeyError) as e:
                error_count += 1
                if error_count < 5:
                    print(f"  Warning line {line_num}: {e}")

    print(f"Processed {trade_count} trades ({error_count} errors)")
    summary = runner.get_summary()
    print(f"Summary: {json.dumps(summary, indent=2)}")

    # Export
    runner.export_csv(output_csv)

    report = runner.generate_report()
    with open(output_report, 'w') as f:
        f.write(report)
    print(f"Report written to: {output_report}")


def replay_events(input_path: str, output_csv: str, output_report: str):
    """Replay MANTIS event data (from events_raw.jsonl)."""
    print(f"Replaying MANTIS events from: {input_path}")

    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    runner = AuctionFailureRunner()
    event_count = 0

    with open(input_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                price = data.get("price", 0)
                raw = data.get("raw_metrics", {})
                total_vol = raw.get("total_volume", raw.get("volume", 0))
                total_delta = raw.get("total_delta", raw.get("delta", 0))
                timestamp = data.get("timestamp", 0)

                if price > 0 and total_vol > 0:
                    runner.on_trade(price, total_vol, total_delta, timestamp)
                    event_count += 1

            except (json.JSONDecodeError, KeyError):
                continue

    print(f"Processed {event_count} event records")
    summary = runner.get_summary()
    print(f"Summary: {json.dumps(summary, indent=2)}")

    runner.export_csv(output_csv)

    report = runner.generate_report()
    with open(output_report, 'w') as f:
        f.write(report)
    print(f"Report written to: {output_report}")


def main():
    parser = argparse.ArgumentParser(
        description="Auction Failure Research — Offline Replay"
    )
    parser.add_argument(
        "--input", type=str, required=True,
        help="Input data file path"
    )
    parser.add_argument(
        "--format", type=str, choices=["trades", "events"], default="trades",
        help="Input format: 'trades' (from collector.py) or 'events' (MANTIS JSONL)"
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

    if args.format == "trades":
        replay_trades(args.input, args.output_csv, args.output_report)
    else:
        replay_events(args.input, args.output_csv, args.output_report)


if __name__ == "__main__":
    main()
