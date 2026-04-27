#!/bin/bash
# Check event collection status
curl -s http://localhost:8000/health | python3 -c "
import sys, json
d = json.load(sys.stdin)
events = d.get('events_total', 0)
trades = d.get('trade_count', 0)
uptime = d.get('uptime', 0)
pending = d.get('pending_outcomes', 0)
rate = events / (uptime / 3600) if uptime > 0 else 0
hours_left = (1000 - events) / rate if rate > 0 else float('inf')
print(f'Events: {events}  Trades: {trades}  Uptime: {uptime/60:.0f}min  Rate: {rate:.0f}/hr  Pending: {pending}')
if events >= 1000:
    print('READY FOR VALIDATION')
else:
    print(f'Need {1000-events} more events (~{hours_left:.1f} hours)')
"
