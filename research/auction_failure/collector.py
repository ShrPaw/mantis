"""
Auction Failure Research — Live Collector

Connects DIRECTLY to Hyperliquid WebSocket for raw trade data.
Does NOT depend on MANTIS backend for data.

Usage:
  python research/auction_failure/collector.py --duration 3600

Shadow mode only. Does NOT modify MANTIS backend.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from .config import AuctionFailureConfig
from .runner import AuctionFailureRunner


HYPERLIQUID_WS = "wss://api.hyperliquid.xyz/ws"


async def collect_direct(
    duration_seconds: int,
    output_trades: str,
    output_events: str,
    output_report: str,
):
    """Connect directly to Hyperliquid for raw trade data."""
    try:
        import websockets
    except ImportError:
        print("ERROR: websockets package not installed.")
        print("Run: pip install websockets")
        sys.exit(1)

    runner = AuctionFailureRunner()
    trades = []
    start_time = time.time()
    last_progress = 0

    print(f"Connecting to Hyperliquid: {HYPERLIQUID_WS}")
    print(f"Duration: {duration_seconds}s")
    print()

    try:
        async with websockets.connect(HYPERLIQUID_WS) as ws:
            # Subscribe to BTC trades
            subscribe_msg = json.dumps({
                "method": "subscribe",
                "subscription": {"type": "trades", "coin": "BTC"}
            })
            await ws.send(subscribe_msg)
            print("Subscribed to BTC trades. Collecting...")

            async for message in ws:
                try:
                    msg = json.loads(message)

                    # Hyperliquid trade messages: {"channel": "trades", "data": [...]}
                    if msg.get("channel") != "trades":
                        continue

                    trade_list = msg.get("data", [])
                    for trade in trade_list:
                        # Each trade: {"coin": "BTC", "side": "B"/"A", "px": "...", "sz": "...", "time": ...}
                        price = float(trade.get("px", 0))
                        qty = float(trade.get("sz", 0))
                        side_raw = trade.get("side", "")  # "B" = buyer taker (buy), "A" = ask taker (sell)
                        ts = trade.get("time", time.time() * 1000) / 1000.0  # ms to seconds

                        if price <= 0 or qty <= 0:
                            continue

                        # Delta: positive for buy aggression, negative for sell aggression
                        # "B" = buyer is taker = aggressive buy
                        # "A" = seller is taker = aggressive sell
                        delta = qty if side_raw == "B" else -qty

                        trades.append({
                            "timestamp": ts,
                            "price": price,
                            "qty": qty,
                            "side": "buy" if side_raw == "B" else "sell",
                            "delta": delta,
                        })

                        # Feed to runner
                        runner.on_trade(price, qty, delta, ts)

                    # Progress
                    elapsed = time.time() - start_time
                    if elapsed > 0 and int(elapsed) % 30 == 0 and int(elapsed) != last_progress:
                        last_progress = int(elapsed)
                        n_events = len(runner._events)
                        n_complete = sum(1 for e in runner._events if e.is_complete)
                        n_trades = len(trades)
                        tps = n_trades / elapsed if elapsed > 0 else 0
                        print(f"  {elapsed:.0f}s | {n_trades} trades ({tps:.1f}/s) | {n_events} events ({n_complete} complete)")

                    if elapsed >= duration_seconds:
                        print(f"\nDuration reached ({duration_seconds}s). Stopping.")
                        break

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    continue

    except websockets.exceptions.ConnectionClosed:
        print("\nWebSocket connection closed.")
    except ConnectionRefusedError:
        print(f"\nERROR: Cannot connect to Hyperliquid WebSocket.")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\nStopped by user.")

    # Save trades
    Path(output_trades).parent.mkdir(parents=True, exist_ok=True)
    with open(output_trades, 'w') as f:
        for trade in trades:
            f.write(json.dumps(trade) + '\n')
    print(f"\nSaved {len(trades)} trades to {output_trades}")

    # Save events and report
    summary = runner.get_summary()
    print(f"\nSummary: {json.dumps(summary, indent=2)}")

    if runner._events:
        runner.export_csv(output_events)
    else:
        print("No events detected.")

    report = runner.generate_report()
    with open(output_report, 'w') as f:
        f.write(report)
    print(f"Report written to: {output_report}")


def main():
    parser = argparse.ArgumentParser(
        description="Auction Failure Research — Live Collector (Hyperliquid direct)"
    )
    parser.add_argument(
        "--duration", type=int, default=3600,
        help="Collection duration in seconds (default: 3600 = 1 hour)"
    )
    parser.add_argument(
        "--output-trades", type=str,
        default="data/research/trades.jsonl",
        help="Output path for raw trades"
    )
    parser.add_argument(
        "--output-events", type=str,
        default="data/research/auction_events.csv",
        help="Output path for auction events"
    )
    parser.add_argument(
        "--output-report", type=str,
        default="AUCTION_FAILURE_RESEARCH_REPORT.md",
        help="Output path for report"
    )
    args = parser.parse_args()

    asyncio.run(collect_direct(
        duration_seconds=args.duration,
        output_trades=args.output_trades,
        output_events=args.output_events,
        output_report=args.output_report,
    ))


if __name__ == "__main__":
    main()
