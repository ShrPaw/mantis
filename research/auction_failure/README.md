# Auction Failure Research Module

**Shadow mode only. No production integration.**

## Purpose

Answer one question: *"Do failed auctions or accepted breakouts produce repeatable net-positive behavior after costs?"*

Built on auction mechanics, not pattern matching. All thresholds are relative (bps, percentile, ratio). No fixed USD amounts. No ML. No optimization.

## Event Classes

| Class | Mechanism | Favorable Direction |
|-------|-----------|-------------------|
| `failed_aggressive_sell` | Strong sell aggression, price fails to move lower | Price RISES |
| `failed_aggressive_buy` | Strong buy aggression, price fails to move higher | Price FALLS |
| `breakout_acceptance` | Price breaks range, holds outside, flow confirms | Continuation |
| `breakout_rejection` | Price breaks range, returns inside, flow fails | Reversal |

## Architecture

```
research/auction_failure/
├── __init__.py          # Package init
├── __main__.py          # Module entry point
├── config.py            # All relative thresholds (no USD)
├── models.py            # AuctionEvent data structure
├── data_adapter.py      # Rolling window + live data feed
├── detectors.py         # Four primitive detectors
├── outcomes.py          # Forward outcome tracker (no lookahead)
├── analytics.py         # Statistics computation
├── report.py            # Report generator
├── runner.py            # Main orchestrator
├── collector.py         # Live WebSocket collector
└── replay.py            # Offline replay tool
```

## Usage

### Collect live data (attach to running MANTIS):
```bash
# Collect for 1 hour
python research/auction_failure/collector.py --duration 3600

# Collect trades only (no detection)
python research/auction_failure/collector.py --duration 3600 --no-detectors
```

### Replay collected data:
```bash
# Replay raw trades
python research/auction_failure/replay.py --input data/research/trades.jsonl --format trades

# Replay MANTIS events
python research/auction_failure/replay.py --input backend/data/events/events_raw.jsonl --format events
```

### Run as module:
```bash
python -m research.auction_failure --replay data/research/trades.jsonl
python -m research.auction_failure --live
```

## Output

- `data/research/auction_events.csv` — All detected events with outcomes
- `AUCTION_FAILURE_RESEARCH_REPORT.md` — Full analysis report

## Detection Parameters (Structural Starting Assumptions)

**These are NOT proven constants.** They are structural starting assumptions based on market mechanics. They define what "strong aggression" and "failure to continue" mean in relative terms. They will NOT be tuned after results are observed.

| Parameter | Value | What It Means |
|-----------|-------|---------------|
| Delta ratio | 0.40 | |delta|/volume ≥ 40% = strong aggression |
| Delta percentile | 0.85 | Current |delta| exceeds 85% of recent windows |
| Volume percentile | 0.70 | Current volume exceeds 70% of recent windows |
| Max move (no response) | 3.0 bps | Price moved < 3bps despite aggression |
| Reclaim window | 30s | Price must return within this time |
| Reclaim threshold | 2.0 bps | Price must return within this distance |
| Break distance | 10% of range | Price exceeds range by this fraction |
| Min range height | 5.0 bps | Minimum range to qualify |
| Flow confirmation | 0.25 | Delta ratio must support break direction |
| Hold window | 15s | Price must stay outside for acceptance |
| Detection window | 15s | Primary lookback for aggression |
| Cooldown | 10s | Minimum time between same-type events |

## Promotion Criteria

An event class is NOT valid unless ALL are true:

1. ≥100 occurrences
2. Positive gross return at intended horizon
3. Net ≥ 0 at 4bps
4. Stable across chronological halves
5. Controlled MAE (< 5bps average)
6. Time-to-positive < 30s average
7. No severe decay over time blocks

## Design Principles

- **No connection to existing detector system** — clean separation
- **All thresholds are relative** — adapts to any volatility regime
- **No scoring engine** — binary detection only
- **No ML** — pure microstructure mechanics
- **No tuning after seeing results** — thresholds are structural
- **Shadow mode only** — never affects production
- **No lookahead bias** — outcomes filled only after horizons pass
