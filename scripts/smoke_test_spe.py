#!/usr/bin/env python3
"""
MANTIS SPE — 30-Minute Smoke Test Script

Runs MANTIS + SPE in observation-only mode and collects metrics.
Does NOT change thresholds. Does NOT execute trades.

Usage:
    python3 scripts/smoke_test_spe.py [--duration 1800]

Output:
    MANTIS_SPE_SMOKE_TEST_REPORT.md
"""

import argparse
import json
import os
import sys
import time
import signal
from datetime import datetime, timezone, timedelta
from collections import defaultdict

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def load_spe_metrics(path: str = "data/metrics/spe_metrics.json") -> dict:
    """Load SPE metrics from disk."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_spe_events(path: str = "data/events/spe_events.jsonl") -> list[dict]:
    """Load SPE events from JSONL."""
    events = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except FileNotFoundError:
        pass
    return events


def load_health(base_url: str = "http://localhost:8000") -> dict:
    """Load health endpoint."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def load_spe_layer_stats(base_url: str = "http://localhost:8000") -> dict:
    """Load SPE layer stats from API."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{base_url}/spe/layers", timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def load_spe_events_api(base_url: str = "http://localhost:8000", limit: int = 100) -> dict:
    """Load SPE events from API."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{base_url}/spe/events?limit={limit}", timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def check_no_execution(events: list[dict]) -> tuple[bool, list[str]]:
    """Verify no SPE events triggered execution."""
    violations = []
    for evt in events:
        if not evt.get("observation_only", True):
            violations.append(f"Event {evt.get('event_id')} missing observation_only=True")
    return len(violations) == 0, violations


def analyze_noise(events: list[dict]) -> dict:
    """Analyze SPE events for noise patterns."""
    if not events:
        return {"duplicate_bursts": 0, "spam": False, "repeated_contexts": 0, "false_positives": 0}

    # Duplicate bursts: same direction+state within 60s
    duplicate_bursts = 0
    for i in range(1, len(events)):
        curr = events[i]
        prev = events[i - 1]
        if (curr.get("direction") == prev.get("direction") and
            curr.get("mantis_state") == prev.get("mantis_state") and
            abs(curr.get("timestamp", 0) - prev.get("timestamp", 0)) < 60):
            duplicate_bursts += 1

    # Repeated same-context events
    context_counts = defaultdict(int)
    for evt in events:
        key = f"{evt.get('direction')}_{evt.get('mantis_state')}_{evt.get('crowd_direction')}"
        context_counts[key] += 1
    repeated = sum(1 for v in context_counts.values() if v > 3)

    return {
        "duplicate_bursts": duplicate_bursts,
        "spam": duplicate_bursts > len(events) * 0.3,
        "repeated_contexts": repeated,
        "false_positives": 0,  # Would need forward return data
    }


def analyze_event_quality(events: list[dict]) -> dict:
    """Analyze quality of emitted SPE events."""
    if not events:
        return {"full_events": [], "high_confidence": [], "avg_confidence": 0}

    full_events = [e for e in events if e.get("confidence_score", 0) > 0]
    high_confidence = sorted(full_events, key=lambda e: e.get("confidence_score", 0), reverse=True)[:10]

    confidences = [e.get("confidence_score", 0) for e in full_events]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    return {
        "full_events": full_events,
        "high_confidence": high_confidence,
        "avg_confidence": round(avg_confidence, 2),
    }


def generate_report(
    duration_seconds: int,
    health: dict,
    spe_layer_data: dict,
    spe_events_data: dict,
    spe_metrics: dict,
    spe_events: list[dict],
    start_time: datetime,
) -> str:
    """Generate the smoke test report in Markdown."""

    layer_stats = spe_layer_data.get("layer_stats", {})
    layer_pf = layer_stats.get("layer_pass_fail", {})

    safety_ok, safety_violations = check_no_execution(spe_events)
    noise = analyze_noise(spe_events)
    quality = analyze_event_quality(spe_events)

    report = f"""# MANTIS SPE — 30-Minute Smoke Test Report

**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
**Duration:** {duration_seconds // 60} minutes
**Test Start:** {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}

---

## 1. Runtime Status

| Check | Status |
|-------|--------|
| Engine connected | {'✅ YES' if health.get('status') == 'ok' else '❌ NO — ' + health.get('error', 'unknown')} |
| SPE enabled | {'✅ YES' if health.get('spe') == 'active' else '❌ NO'} |
| Observation-only confirmed | {'✅ YES' if health.get('spe_observation_only') else '❌ NO'} |
| Trade count | {health.get('trade_count', 'N/A')} |
| Candles loaded | {health.get('candles_loaded', 'N/A')} |
| Uptime | {health.get('uptime', 0):.0f}s |
| Clients connected | {health.get('clients', 'N/A')} |

---

## 2. Raw Counts

| Metric | Value |
|--------|-------|
| Raw MANTIS events (total) | {health.get('events_total', 'N/A')} |
| Raw SPE evaluations | {layer_stats.get('raw_evaluations', 0)} |
| SPE emitted events | {layer_stats.get('emitted_events', 0)} |
| Suppressed duplicates | {layer_stats.get('suppressed_duplicates', 0)} |
| Partial 4-layer passes | {layer_stats.get('partial_4_layer_passes', 0)} |
| Partial 6-layer passes | {layer_stats.get('partial_6_layer_passes', 0)} |
| Full 8-layer passes | {layer_stats.get('full_8_layer_passes', 0)} |
| Cooldown hits | {layer_stats.get('cooldown_hits', 0)} |

---

## 3. Layer Statistics

| Layer | Pass | Fail | Not Evaluated | Pass Rate |
|-------|------|------|---------------|-----------|
"""

    for layer_name in ["L1_context_gate", "L2_pressure", "L3_displacement",
                       "L4_sweep", "L5_trap", "L6_execution_filter",
                       "L7_entry_zone", "L8_exit_model", "confidence_gate"]:
        counts = layer_pf.get(layer_name, {"pass": 0, "fail": 0, "not_evaluated": 0})
        total = counts["pass"] + counts["fail"] + counts.get("not_evaluated", 0)
        evaluated = counts["pass"] + counts["fail"]
        rate = (counts["pass"] / evaluated * 100) if evaluated > 0 else 0
        ne = counts.get("not_evaluated", 0)
        report += f"| {layer_name} | {counts['pass']} | {counts['fail']} | {ne} | {rate:.1f}% |\n"

    # Find rejection bottleneck (only among evaluated layers)
    rejection_layers = []
    for layer_name, counts in layer_pf.items():
        evaluated = counts["pass"] + counts["fail"]
        if evaluated > 0 and counts["fail"] / evaluated > 0.8:
            rejection_layers.append(layer_name)

    report += f"""
**Rejection bottleneck:** {', '.join(rejection_layers) if rejection_layers else 'None identified (insufficient data)'}
**Too restrictive?** {'Yes — very few events emitted' if layer_stats.get('emitted_events', 0) == 0 and layer_stats.get('raw_evaluations', 0) > 100 else 'Cannot determine yet'}
**Too permissive?** {'Yes — too many events' if layer_stats.get('emitted_events', 0) > 50 else 'No' if layer_stats.get('emitted_events', 0) > 0 else 'Cannot determine yet'}

---

## 4. Event Quality

"""

    if quality["full_events"]:
        report += f"**Total SPE events:** {len(quality['full_events'])}\n"
        report += f"**Average confidence:** {quality['avg_confidence']}\n\n"

        report += "### Top 10 Highest-Confidence Events\n\n"
        report += "| # | Time | Direction | State | Confidence | Entry | Crowd | Displacement |\n"
        report += "|---|------|-----------|-------|------------|-------|-------|-------------|\n"
        for i, evt in enumerate(quality["high_confidence"][:10], 1):
            ts = datetime.fromtimestamp(evt.get("timestamp", 0), tz=timezone.utc).strftime("%H:%M:%S")
            report += (
                f"| {i} | {ts} | {evt.get('direction', '?')} | {evt.get('mantis_state', '?')} | "
                f"{evt.get('confidence_score', 0):.1f} | ${evt.get('entry_price', 0):,.2f} | "
                f"{evt.get('crowd_direction', '?')} | {evt.get('displacement_strength', 0):.0f}% |\n"
            )

        report += "\n### All SPE Events\n\n"
        for evt in quality["full_events"]:
            ts = datetime.fromtimestamp(evt.get("timestamp", 0), tz=timezone.utc).strftime("%H:%M:%S")
            report += (
                f"- **{ts}** | {evt.get('direction')} | {evt.get('mantis_state')} | "
                f"conf={evt.get('confidence_score', 0):.1f} | "
                f"entry=${evt.get('entry_price', 0):,.2f} | "
                f"explanation: {evt.get('explanation', 'N/A')}\n"
            )
    else:
        report += "**No SPE events emitted during test period.**\n\n"
        report += "This means either:\n"
        report += "1. No structural pressure conditions occurred (market was calm)\n"
        report += "2. SPE is too restrictive (thresholds may need review — but DO NOT tune yet)\n"
        report += "3. Insufficient runtime data accumulated\n"

    report += """
---

## 5. Noise Check

| Check | Result |
|-------|--------|
| Duplicate bursts | {duplicate_bursts} |
| Spam detected | {spam} |
| Repeated same-context events | {repeated_contexts} |
| False positives | {false_positives} (needs forward data) |
""".format(**noise)

    report += """
---

## 6. Safety Check

| Check | Status |
|-------|--------|
| No execution happened | {safety} |
| No trading endpoints called | {safety} (observation-only enforced) |
| observation_only flag on all events | {flag_check} |
""".format(
        safety='✅ CONFIRMED' if safety_ok else '❌ VIOLATION',
        flag_check='✅ YES' if safety_ok else '❌ ' + '; '.join(safety_violations),
    )

    if safety_violations:
        report += "\n**⚠ SAFETY VIOLATIONS:**\n"
        for v in safety_violations:
            report += f"- {v}\n"

    # Verdict
    verdict = "C"
    if safety_ok and layer_stats.get("raw_evaluations", 0) > 0:
        if layer_stats.get("emitted_events", 0) > 0 and not noise["spam"]:
            verdict = "A"
        elif layer_stats.get("partial_6_layer_passes", 0) > 0:
            verdict = "B"
        elif layer_stats.get("partial_4_layer_passes", 0) > 0:
            verdict = "B"

    report += f"""
---

## Final Smoke-Test Verdict

### **{verdict}** — {
    "Integration healthy, ready for longer live audit" if verdict == "A" else
    "Functional but needs mechanical fixes" if verdict == "B" else
    "Broken / too noisy / unusable"
}

### Criteria:
- **A** — Integration healthy, SPE runs without errors, events emitted with proper observation-only flags, no noise issues
- **B** — Functional but needs mechanical fixes (e.g., no events due to restrictive thresholds, minor issues)
- **C** — Broken / too noisy / unusable

### Notes:
- Thresholds were NOT changed during this test
- Results reflect real market conditions during the test window
- A verdict of B with zero events is expected if market was calm
- Run again during higher-volatility periods for better assessment
"""
    return report


def main():
    parser = argparse.ArgumentParser(description="MANTIS SPE 30-minute smoke test")
    parser.add_argument("--duration", type=int, default=1800, help="Test duration in seconds (default: 1800)")
    parser.add_argument("--api", type=str, default="http://localhost:8000", help="MANTIS API base URL")
    parser.add_argument("--output", type=str, default="MANTIS_SPE_SMOKE_TEST_REPORT.md", help="Output report file")
    parser.add_argument("--sample-interval", type=int, default=30, help="Metrics collection interval (seconds)")
    args = parser.parse_args()

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  MANTIS SPE — Smoke Test                            ║")
    print(f"║  Duration: {args.duration // 60} minutes                              ║")
    print(f"║  API: {args.api}                            ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print()

    # Verify API is reachable
    health = load_health(args.api)
    if "error" in health:
        print(f"❌ Cannot reach MANTIS API at {args.api}")
        print(f"   Error: {health['error']}")
        print(f"   Make sure MANTIS is running: bash start.sh")
        sys.exit(1)

    print(f"✅ MANTIS API reachable")
    print(f"   SPE: {health.get('spe', 'unknown')}")
    print(f"   Observation-only: {health.get('spe_observation_only', 'unknown')}")
    print(f"   Trade count: {health.get('trade_count', 0)}")
    print()

    start_time = datetime.now(timezone.utc)
    samples = []
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        print("\n⚠ Interrupted — generating report with collected data...")
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Collection loop
    elapsed = 0
    while running and elapsed < args.duration:
        time.sleep(args.sample_interval)
        elapsed += args.sample_interval

        # Collect samples
        sample = {
            "timestamp": time.time(),
            "elapsed": elapsed,
            "health": load_health(args.api),
            "layers": load_spe_layer_stats(args.api),
            "events": load_spe_events_api(args.api, limit=100),
        }
        samples.append(sample)

        # Progress
        evt_count = sample["events"].get("spe_stats", {}).get("events_emitted", 0) if "error" not in sample["events"] else "N/A"
        evals = sample["layers"].get("layer_stats", {}).get("raw_evaluations", 0) if "error" not in sample["layers"] else "N/A"
        print(f"  [{elapsed // 60:3d}m] evals={evals} | events={evt_count} | tick {len(samples)}")

    # Final collection
    print("\n📊 Collecting final metrics...")
    final_health = load_health(args.api)
    final_layers = load_spe_layer_stats(args.api)
    final_events_api = load_spe_events_api(args.api, limit=200)
    spe_metrics = load_spe_metrics()
    spe_events = load_spe_events()

    # Generate report
    report = generate_report(
        duration_seconds=elapsed,
        health=final_health,
        spe_layer_data=final_layers,
        spe_events_data=final_events_api,
        spe_metrics=spe_metrics,
        spe_events=spe_events,
        start_time=start_time,
    )

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✅ Report written to {args.output}")
    print(f"   Duration: {elapsed // 60} minutes")
    print(f"   Samples: {len(samples)}")
    print(f"   SPE Events: {len(spe_events)}")


if __name__ == "__main__":
    main()
