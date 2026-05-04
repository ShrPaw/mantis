// MANTIS Dashboard — Status Bar (with live price)
import { useMemo } from 'react';
import { formatPrice, formatDelta, formatPct } from '../services/format';
import type { FlowMetrics } from '../types';
import type { LivePrice } from '../store';
import { useStore } from '../store';

interface Props {
  connected: boolean;
  flow: FlowMetrics;
}

function timeSince(ms: number): string {
  if (!ms) return '—';
  const sec = Math.floor((Date.now() - ms) / 1000);
  if (sec < 2) return 'now';
  if (sec < 60) return `${sec}s ago`;
  return `${Math.floor(sec / 60)}m ago`;
}

export function StatusBar({ connected, flow }: Props) {
  const livePrice = useStore(s => s.livePrice);
  const deltaColor = (v: number) => v >= 0 ? '#26a69a' : '#ef5350';

  // Use live price if recent (within 5s), otherwise fall back to flow.last_price
  const displayPrice = useMemo(() => {
    if (livePrice.price > 0 && (Date.now() - livePrice.lastUpdate) < 5000) {
      return livePrice.price;
    }
    return flow.last_price;
  }, [livePrice.price, livePrice.lastUpdate, flow.last_price]);

  // Flash color on price update (green if updated within 200ms)
  const priceFresh = (Date.now() - livePrice.lastUpdate) < 200;

  return (
    <div style={styles.bar}>
      {/* Connection indicator */}
      <div style={styles.statusChip}>
        <span style={{
          ...styles.dot,
          background: connected ? '#26a69a' : '#ef5350',
          boxShadow: connected ? '0 0 6px #26a69a' : '0 0 6px #ef5350',
        }} />
        <span style={{ color: connected ? '#26a69a' : '#ef5350', fontSize: 9, fontWeight: 600 }}>
          {connected ? 'LIVE' : 'OFFLINE'}
        </span>
      </div>

      <div style={styles.sep} />

      {/* Exchange source */}
      <span style={styles.source}>HYPERLIQUID</span>

      <div style={styles.sep} />

      {/* Price — uses livePrice for instant updates */}
      <span style={{
        ...styles.price,
        color: priceFresh ? '#fff' : '#f0b90b',
        textShadow: priceFresh ? '0 0 8px rgba(240,185,11,0.4)' : 'none',
      }}>
        {formatPrice(displayPrice)}
      </span>

      {/* Last update indicator */}
      <span style={styles.lastUpdate}>{timeSince(livePrice.lastUpdate)}</span>

      <div style={styles.sep} />

      {/* Mini metrics */}
      <Metric label="VWAP" value={formatPrice(flow.vwap)} color="#f0b90b" />
      <Metric label="H" value={formatPrice(flow.session_high)} color="#26a69a" />
      <Metric label="L" value={formatPrice(flow.session_low)} color="#ef5350" />

      <div style={styles.sep} />

      <Metric label="Δ" value={formatDelta(flow.delta)} color={deltaColor(flow.delta)} />
      <Metric label="ΣΔ" value={formatDelta(flow.cum_delta)} color={deltaColor(flow.cum_delta)} />
      <Metric label="IMB" value={formatPct(flow.imbalance)} color={deltaColor(flow.imbalance)} />

      <div style={styles.sep} />

      <Metric label="TRADES" value={String(flow.trade_count ?? 0)} color="#888" />
      <Metric label="FREQ" value={(flow.trade_frequency ?? 0).toFixed(1) + '/s'} color="#888" />
    </div>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={styles.metric}>
      <span style={styles.metricLabel}>{label}</span>
      <span style={{ ...styles.metricValue, color }}>{value}</span>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  bar: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    fontSize: 11,
  },
  statusChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 5,
    padding: '2px 8px',
    borderRadius: 3,
    background: 'rgba(38, 166, 154, 0.06)',
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    display: 'inline-block',
  },
  sep: {
    width: 1,
    height: 14,
    background: '#1a1a2e',
  },
  source: {
    fontSize: 8,
    color: '#444',
    letterSpacing: 2,
    textTransform: 'uppercase' as const,
  },
  price: {
    color: '#f0b90b',
    fontWeight: 700,
    fontSize: 14,
    fontVariantNumeric: 'tabular-nums' as const,
    transition: 'color 0.15s, text-shadow 0.15s',
  },
  lastUpdate: {
    fontSize: 8,
    color: '#555',
    minWidth: 36,
    fontVariantNumeric: 'tabular-nums' as const,
  },
  metric: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
  },
  metricLabel: {
    color: '#555',
    fontSize: 8,
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
  },
  metricValue: {
    fontWeight: 600,
    fontSize: 10,
    fontVariantNumeric: 'tabular-nums' as const,
  },
};
