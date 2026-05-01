#!/usr/bin/env python3
"""
MANTIS SPE — Short-Stress Long-Run Observation Logger

Passive observer that polls MANTIS backend endpoints and logs SPE metrics
over days/weeks for walk-forward validation of SPE_SHORT_STRESS.

This is NOT a trading bot. This is NOT execution. This is NOT strategy logic.
It is only a passive observer/logger.

Usage:
    python scripts/run_short_stress_observation.py [--interval 30] [--api http://localhost:8000]

Output:
    data/observation/short_stress_health.jsonl
    data/observation/short_stress_metrics.jsonl
    data/observation/short_stress_events.jsonl
    data/observation/SHORT_STRESS_OBSERVATION_SESSION_SUMMARY.md
"""

import argparse
import json
import os
import sys
import time
import signal
import hashlib
from datetime import datetime, timezone, timedelta
from collections import defaultdict


# ── Constants ──
ENCODING = "utf-8"
OBSERVATION_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "observation"
)
HEALTH_FILE = os.path.join(OBSERVATION_DIR, "short_stress_health.jsonl")
METRICS_FILE = os.path.join(OBSERVATION_DIR, "short_stress_metrics.jsonl")
EVENTS_FILE = os.path.join(OBSERVATION_DIR, "short_stress_events.jsonl")
SUMMARY_FILE = os.path.join(OBSERVATION_DIR, "SHORT_STRESS_OBSERVATION_SESSION_SUMMARY.md")


def ensure_dirs():
    """Create output directories if they don't exist."""
    os.makedirs(OBSERVATION_DIR, exist_ok=True)


def http_get_json(url: str, timeout: int = 10) -> dict | None:
    """
    Fetch JSON from a URL. Returns None on any error.
    Windows-safe: uses urllib (no external deps).
    """
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw)
    except Exception:
        return None


def write_jsonl_line(path: str, record: dict):
    """Append a single JSON line to a file. UTF-8, Windows-safe."""
    try:
        with open(path, "a", encoding=ENCODING, errors="replace") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"  [WARN] Failed to write {path}: {e}", file=sys.stderr)


def event_dedup_key(evt: dict) -> str:
    """
    Build a dedup key from event fields.
    Matches the spec: timestamp/event_type/direction_context/confidence_score.
    """
    parts = [
        str(evt.get("timestamp", "")),
        str(evt.get("event_type", "")),
        str(evt.get("direction", "")),
        str(evt.get("mantis_state", "")),
        str(evt.get("crowd_direction", "")),
        str(evt.get("confidence_score", "")),
    ]
    return "|".join(parts)


def is_short_stress_candidate(evt: dict) -> bool:
    """
    Check if an event is a SHORT_STRESS candidate.
    SHORT direction + LONG_CROWD + CASCADE/UNWIND state.
    """
    return (
        evt.get("direction") == "SHORT"
        and evt.get("crowd_direction") == "LONG_CROWD"
        and evt.get("mantis_state") in ("CASCADE", "UNWIND")
    )


class ObservationSession:
    """Manages a single long-run observation session."""

    def __init__(self, api_base: str, interval: int):
        self.api_base = api_base.rstrip("/")
        self.interval = interval
        self.running = True
        self.start_time = datetime.now(timezone.utc)
        self.start_ts = time.time()

        # Counters
        self.health_samples = 0
        self.metric_samples = 0
        self.event_api_samples = 0
        self.unique_events_seen = 0
        self.total_events_from_api = 0

        # Dedup tracking
        self._seen_event_keys: set[str] = set()

        # State distribution
        self.state_counts: dict[str, int] = defaultdict(int)

        # Accounting
        self.accounting_valid_failures = 0
        self.observation_only_violations = 0

        # Max emitted
        self.max_emitted_events = 0

        # Error tracking
        self.health_errors = 0
        self.metrics_errors = 0
        self.events_errors = 0

        # Layer pass tracking (latest snapshot)
        self.last_layer_counts: dict = {}

        # Full 8-layer pass tracking
        self.full_8_layer_passes_max = 0

    def handle_signal(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        print("\n[INFO] Ctrl+C received. Generating summary and exiting...")
        self.running = False

    def poll_health(self):
        """Poll /health and log."""
        data = http_get_json(f"{self.api_base}/health")
        if data is None:
            self.health_errors += 1
            return

        record = {
            "poll_ts": time.time(),
            "poll_utc": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        write_jsonl_line(HEALTH_FILE, record)
        self.health_samples += 1

    def poll_metrics(self):
        """Poll /spe/metrics and log."""
        data = http_get_json(f"{self.api_base}/spe/metrics")
        if data is None:
            self.metrics_errors += 1
            return

        record = {
            "poll_ts": time.time(),
            "poll_utc": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        write_jsonl_line(METRICS_FILE, record)
        self.metric_samples += 1

        # Extract state distribution
        state = data.get("current_state", "UNKNOWN")
        self.state_counts[state] += 1

        # Track accounting
        if not data.get("accounting_valid", True):
            self.accounting_valid_failures += 1

        # Track emitted events
        emitted = data.get("emitted_events", 0)
        if emitted > self.max_emitted_events:
            self.max_emitted_events = emitted

        # Track full 8-layer passes
        full_passes = data.get("full_8_layer_passes", 0)
        if full_passes > self.full_8_layer_passes_max:
            self.full_8_layer_passes_max = full_passes

        # Store layer counts
        self.last_layer_counts = data.get("layer_counts", {})

    def poll_events(self):
        """Poll /spe/events?limit=20, deduplicate, and log."""
        data = http_get_json(f"{self.api_base}/spe/events?limit=20")
        if data is None:
            self.events_errors += 1
            return

        self.event_api_samples += 1

        # The response may have spe_events key or be a list
        events = data.get("spe_events", data if isinstance(data, list) else [])
        self.total_events_from_api += len(events)

        new_count = 0
        for evt in events:
            # Dedup
            key = event_dedup_key(evt)
            if key in self._seen_event_keys:
                continue
            self._seen_event_keys.add(key)
            self.unique_events_seen += 1
            new_count += 1

            # Check observation_only
            if not evt.get("observation_only", True):
                self.observation_only_violations += 1

            # Mark if SHORT_STRESS candidate
            evt["_short_stress_candidate"] = is_short_stress_candidate(evt)

            # Write
            record = {
                "log_ts": time.time(),
                "log_utc": datetime.now(timezone.utc).isoformat(),
                "event": evt,
            }
            write_jsonl_line(EVENTS_FILE, record)

        if new_count > 0:
            print(f"  [EVENT] {new_count} new unique event(s) logged")

    def poll_cycle(self):
        """Run one poll cycle."""
        self.poll_health()
        self.poll_metrics()
        self.poll_events()

    def generate_summary(self):
        """Generate the session summary markdown file."""
        end_time = datetime.now(timezone.utc)
        end_ts = time.time()
        duration_s = end_ts - self.start_ts
        duration_h = duration_s / 3600

        # Count short_stress candidates from events file
        short_stress_count = 0
        short_stress_events = []
        try:
            with open(EVENTS_FILE, "r", encoding=ENCODING) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    evt = record.get("event", {})
                    if evt.get("_short_stress_candidate"):
                        short_stress_count += 1
                        short_stress_events.append(evt)
        except FileNotFoundError:
            pass

        # State distribution percentages
        total_state_samples = sum(self.state_counts.values()) or 1
        state_dist_lines = []
        for state in sorted(self.state_counts.keys()):
            count = self.state_counts[state]
            pct = count / total_state_samples * 100
            state_dist_lines.append(f"| {state} | {count} | {pct:.1f}% |")

        # Layer stats from last snapshot
        layer_lines = []
        for layer_name in [
            "L1_context_gate", "L2_pressure", "L3_displacement",
            "L4_sweep", "L5_trap", "L6_execution_filter",
            "L7_entry_zone", "L8_exit_model", "confidence_gate"
        ]:
            counts = self.last_layer_counts.get(layer_name, {})
            p = counts.get("pass", 0)
            f_ = counts.get("fail", 0)
            ne = counts.get("not_evaluated", 0)
            layer_lines.append(f"| {layer_name} | {p} | {f_} | {ne} |")

        # Short-stress candidate details
        ss_lines = []
        for evt in short_stress_events[:20]:
            ts = evt.get("timestamp", 0)
            ts_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ts > 0 else "N/A"
            ss_lines.append(
                f"- **{ts_str}** | conf={evt.get('confidence_score', 0):.1f} | "
                f"state={evt.get('mantis_state', '?')} | "
                f"entry=${evt.get('entry_price', 0):,.2f} | "
                f"displacement={evt.get('displacement_strength', 0):.0f}"
            )

        summary = f"""# SPE_SHORT_STRESS — Observation Session Summary

**Generated:** {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Script:** `scripts/run_short_stress_observation.py`
**API:** `{self.api_base}`
**Poll interval:** {self.interval}s

---

## Session Timing

| Metric | Value |
|--------|-------|
| Start time (UTC) | {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| End time (UTC) | {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')} |
| Duration | {duration_s:.0f}s ({duration_h:.1f} hours) |

---

## Sample Counts

| Metric | Count |
|--------|-------|
| Health samples | {self.health_samples} |
| Metric samples | {self.metric_samples} |
| Event API samples | {self.event_api_samples} |
| Total events from API | {self.total_events_from_api} |
| Unique events logged | {self.unique_events_seen} |
| SHORT_STRESS candidates | {short_stress_count} |

---

## Error Tracking

| Error Type | Count |
|------------|-------|
| Health poll failures | {self.health_errors} |
| Metrics poll failures | {self.metrics_errors} |
| Events poll failures | {self.events_errors} |

---

## State Distribution

| State | Count | Percentage |
|-------|-------|------------|
{chr(10).join(state_dist_lines) if state_dist_lines else "| (no data) | 0 | 0% |"}

---

## SPE Accounting

| Check | Status |
|-------|--------|
| Accounting valid failures | {self.accounting_valid_failures} |
| observation_only violations | {self.observation_only_violations} |
| Max emitted_events | {self.max_emitted_events} |
| Max full_8_layer_passes | {self.full_8_layer_passes_max} |

---

## Layer Statistics (Last Snapshot)

| Layer | Pass | Fail | Not Evaluated |
|-------|------|------|---------------|
{chr(10).join(layer_lines) if layer_lines else "| (no data) | - | - | - |"}

---

## SHORT_STRESS Candidates

Events matching: `direction=SHORT` AND `crowd_direction=LONG_CROWD` AND `mantis_state IN (CASCADE, UNWIND)`

**Total found:** {short_stress_count}

{chr(10).join(ss_lines) if ss_lines else "_No SHORT_STRESS candidates observed during this session._"}

---

## Verdict

{"**No SHORT_STRESS events observed.** Market did not enter CASCADE/UNWIND states with LONG_CROWD pressure during this observation window." if short_stress_count == 0 else f"**{short_stress_count} SHORT_STRESS candidate(s) observed.** Review events file for full details."}

---

## Files Produced

| File | Description |
|------|-------------|
| `short_stress_health.jsonl` | Raw health poll snapshots |
| `short_stress_metrics.jsonl` | Raw SPE metrics poll snapshots |
| `short_stress_events.jsonl` | Deduplicated SPE events |
| `SHORT_STRESS_OBSERVATION_SESSION_SUMMARY.md` | This summary |

---

## Notes

- All data collected in observation-only mode
- No thresholds were modified
- No execution was attempted
- No trading endpoints were called
- Events are deduplicated by: timestamp + event_type + direction + mantis_state + crowd_direction + confidence_score
- This script does NOT claim edge. It only collects evidence.

---

*Observation session completed at {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}*
"""
        try:
            with open(SUMMARY_FILE, "w", encoding=ENCODING) as f:
                f.write(summary)
            print(f"[INFO] Summary written to {SUMMARY_FILE}")
        except Exception as e:
            print(f"[ERROR] Failed to write summary: {e}", file=sys.stderr)

    def print_status(self):
        """Print a status line to console."""
        elapsed = time.time() - self.start_ts
        hours = elapsed / 3600
        state_str = ", ".join(f"{k}:{v}" for k, v in sorted(self.state_counts.items()))
        print(
            f"  [{hours:6.1f}h] "
            f"health={self.health_samples} "
            f"metrics={self.metric_samples} "
            f"events={self.unique_events_seen} "
            f"ss_candidates={sum(1 for _ in [])} "  # placeholder
            f"acct_failures={self.accounting_valid_failures} "
            f"states=[{state_str}]"
        )

    def run(self):
        """Main observation loop."""
        print("=" * 60)
        print("  MANTIS SPE — Short-Stress Observation Logger")
        print(f"  API:       {self.api_base}")
        print(f"  Interval:  {self.interval}s")
        print(f"  Output:    {OBSERVATION_DIR}")
        print(f"  Start:     {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 60)
        print()

        # Verify API is reachable
        health = http_get_json(f"{self.api_base}/health", timeout=5)
        if health is None:
            print("[ERROR] Cannot reach MANTIS API. Is it running?")
            print(f"        Expected at: {self.api_base}")
            print("        Start with: cd backend && python main.py")
            sys.exit(1)

        print(f"[OK] MANTIS API reachable")
        print(f"     SPE: {health.get('spe', 'unknown')}")
        print(f"     Observation-only: {health.get('spe_observation_only', 'unknown')}")
        print(f"     Trade count: {health.get('trade_count', 0)}")
        print()
        print("[RUNNING] Polling... (Ctrl+C to stop)")
        print()

        cycle = 0
        while self.running:
            try:
                self.poll_cycle()
                cycle += 1

                # Print status every 10 cycles
                if cycle % 10 == 0:
                    self.print_status()

                # Sleep in small increments so Ctrl+C is responsive
                for _ in range(self.interval * 2):
                    if not self.running:
                        break
                    time.sleep(0.5)

            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                print(f"  [ERROR] Unexpected error in poll cycle: {e}", file=sys.stderr)
                # Don't crash — log and continue
                time.sleep(self.interval)

        # Generate summary
        print()
        print("[DONE] Generating session summary...")
        self.generate_summary()

        # Final stats
        end_ts = time.time()
        duration = end_ts - self.start_ts
        print()
        print(f"Session duration: {duration:.0f}s ({duration/3600:.1f} hours)")
        print(f"Health samples:   {self.health_samples}")
        print(f"Metric samples:   {self.metric_samples}")
        print(f"Unique events:    {self.unique_events_seen}")
        print(f"Acct failures:    {self.accounting_valid_failures}")
        print(f"OO violations:    {self.observation_only_violations}")
        print()
        print("Observation complete.")


def main():
    parser = argparse.ArgumentParser(
        description="MANTIS SPE Short-Stress Long-Run Observation Logger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This is a passive observer. It does NOT:
  - Change thresholds
  - Modify SPE logic
  - Enable execution
  - Call trading endpoints
  - Claim edge
  - Produce alerts

It only polls MANTIS endpoints and logs what it sees.

Example:
  Terminal 1: cd backend && python main.py
  Terminal 2: python scripts/run_short_stress_observation.py --interval 30
"""
    )
    parser.add_argument(
        "--interval", type=int, default=30,
        help="Poll interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--api", type=str, default="http://localhost:8000",
        help="MANTIS API base URL (default: http://localhost:8000)"
    )
    args = parser.parse_args()

    ensure_dirs()

    session = ObservationSession(
        api_base=args.api,
        interval=args.interval,
    )

    # Register signal handlers for clean Ctrl+C
    signal.signal(signal.SIGINT, session.handle_signal)
    signal.signal(signal.SIGTERM, session.handle_signal)

    session.run()


if __name__ == "__main__":
    main()
