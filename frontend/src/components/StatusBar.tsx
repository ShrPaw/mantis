// MANTIS Dashboard — Status Bar
import { formatPrice, formatDelta, formatPct } from '../services/format';
import type { FlowMetrics } from '../types';

interface Props {
  connected: boolean;
  flow: FlowMetrics;
}

export function StatusBar({ connected, flow }: Props) {
  const deltaColor = (v: number) => v >= 0 ? '#00e676' : '#ff1744';

  return (
    <div style={styles.bar}>
      {/* Connection indicator */}
      <div style={styles.statusChip}>
        <span style={{
          ...styles.dot,
          background: connected ? '#00e676' : '#ff1744',
          boxShadow: connected ? '0 0 6px #00e676' : '0 0 6px #ff1744',
        }} />
        <span style={{ color: connected ? '#00e676' : '#ff1744', fontSize: 9, fontWeight: 600 }}>
          {connected ? 'LIVE' : 'OFFLINE'}
        </span>
      </div>

      <div style={styles.sep} />

      {/* Price */}
      <span style={styles.price}>{formatPrice(flow.last_price)}</span>

      <div style={styles.sep} />

      {/* Mini metrics */}
      <Metric label="VWAP" value={formatPrice(flow.vwap)} color="#f0b90b" />
      <Metric label="H" value={formatPrice(flow.session_high)} color="#00e676" />
      <Metric label="L" value={formatPrice(flow.session_low)} color="#ff1744" />

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
    background: 'rgba(0,230,118,0.06)',
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
  price: {
    color: '#f0b90b',
    fontWeight: 700,
    fontSize: 14,
    fontVariantNumeric: 'tabular-nums',
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
    fontVariantNumeric: 'tabular-nums',
  },
};
