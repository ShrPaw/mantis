// MANTIS Operator Dashboard — Polling Hook
// Polls /operator/status every N seconds with graceful error handling
import { useEffect, useRef, useCallback } from 'react';
import { useOperatorStore } from '../store/operatorStore';

const POLL_INTERVAL = 3000; // 3 seconds
const MAX_HISTORY = 200; // max metric snapshots kept

export function useOperatorPolling(intervalMs: number = POLL_INTERVAL) {
  const timerRef = useRef<ReturnType<typeof setInterval>>();
  const {
    setOperatorStatus,
    setConnected,
    setError,
    addMetricSnapshot,
  } = useOperatorStore();

  const poll = useCallback(async () => {
    try {
      const resp = await fetch('/operator/status');
      if (!resp.ok) {
        setError(`HTTP ${resp.status}`);
        return;
      }
      const data = await resp.json();
      setOperatorStatus(data);
      setConnected(true);
      setError(null);

      // Track metric history for charts
      addMetricSnapshot({
        ts: data.timestamp,
        raw_evaluations: data.spe?.raw_evaluations ?? 0,
        emitted_events: data.spe?.emitted_events ?? 0,
        full_8_layer_passes: data.spe?.full_8_layer_passes ?? 0,
        current_state: data.spe?.current_state ?? 'IDLE',
        layer_counts: data.spe?.layer_counts ?? {},
      });
    } catch (err) {
      setConnected(false);
      setError(err instanceof Error ? err.message : 'Connection failed');
    }
  }, [setOperatorStatus, setConnected, setError, addMetricSnapshot]);

  useEffect(() => {
    poll(); // immediate first poll
    timerRef.current = setInterval(poll, intervalMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [poll, intervalMs]);

  return { poll };
}
