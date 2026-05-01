// MANTIS Operator Dashboard — Header Bar
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';

type ViewMode = 'micro' | 'operator';

function formatUptime(s: number): string {
  if (s < 60) return `${Math.floor(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

export const OperatorHeader: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const connected = useOperatorStore(s => s.connected);
  const error = useOperatorStore(s => s.error);

  const backend = status?.backend;
  const spe = status?.spe;
  const now = new Date().toLocaleTimeString('en-US', { hour12: false });

  return (
    <header style={S.header}>
      <div style={S.left}>
        <span style={S.logo}>◆</span>
        <span style={S.title}>MANTIS</span>
        <span style={S.badge}>OPERATOR</span>
        <span style={S.source}>HYPERLIQUID</span>
      </div>

      <div style={S.center}>
        <StatusDot ok={connected} label={connected ? 'ONLINE' : 'OFFLINE'} />
        <Divider />
        <Metric label="UPTIME" value={backend ? formatUptime(backend.uptime) : '—'} />
        <Divider />
        <Metric label="TRADES" value={backend?.trade_count?.toLocaleString() ?? '—'} />
        <Divider />
        <Metric label="ENGINE" value={status?.event_engine?.status?.toUpperCase() ?? '—'} color={status?.event_engine?.enabled ? '#26a69a' : '#ef5350'} />
        <Divider />
        <Metric label="SPE" value={spe?.enabled ? 'ACTIVE' : 'OFF'} color={spe?.enabled ? '#f0b90b' : '#666'} />
        <Divider />
        <span style={S.obsBadge}>⚠ OBSERVATION-ONLY</span>
      </div>

      <div style={S.right}>
        <ViewToggle />
        <span style={S.time}>{now}</span>
        {error && <span style={S.err}>ERR: {error}</span>}
      </div>
    </header>
  );
};

const StatusDot: React.FC<{ ok: boolean; label: string }> = ({ ok, label }) => (
  <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
    <span style={{ color: ok ? '#26a69a' : '#ef5350', fontSize: 10 }}>●</span>
    <span style={{ color: ok ? '#26a69a' : '#ef5350', fontWeight: 600 }}>{label}</span>
  </span>
);

const Metric: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color }) => (
  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
    <span style={{ color: '#555', fontSize: 9, letterSpacing: 1 }}>{label}</span>
    <span style={{ color: color || '#ccc', fontWeight: 600, fontSize: 11 }}>{value}</span>
  </span>
);

const Divider = () => (
  <span style={{ width: 1, height: 16, background: '#1a1a2e', margin: '0 4px' }} />
);

const ViewToggle: React.FC = () => (
  <div style={{ display: 'flex', borderRadius: 3, overflow: 'hidden', border: '1px solid #1a1a2e' }}>
    <span style={{
      background: '#f0b90b18',
      color: '#f0b90b',
      padding: '2px 8px',
      fontSize: 8,
      fontWeight: 700,
      letterSpacing: 1,
      borderBottom: '2px solid #f0b90b',
    }}>OPERATOR</span>
    <a href="/?view=micro" style={{
      background: 'transparent',
      color: '#555',
      padding: '2px 8px',
      fontSize: 8,
      fontWeight: 700,
      letterSpacing: 1,
      textDecoration: 'none',
      borderBottom: '2px solid transparent',
    }}>MICRO</a>
  </div>
);

const S: Record<string, React.CSSProperties> = {
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '5px 16px',
    background: '#0a0a12',
    borderBottom: '1px solid #1a1a2e',
    flexShrink: 0,
    height: 34,
    zIndex: 10,
  },
  left: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  logo: { fontSize: 14, color: '#f0b90b' },
  title: { fontSize: 13, fontWeight: 700, color: '#f0b90b', letterSpacing: 2 },
  badge: {
    fontSize: 8,
    color: '#f0b90b',
    letterSpacing: 2,
    padding: '1px 5px',
    border: '1px solid #f0b90b40',
    borderRadius: 3,
    background: '#f0b90b10',
  },
  source: {
    fontSize: 8,
    color: '#333',
    letterSpacing: 2,
    padding: '1px 5px',
    border: '1px solid #1a1a2e',
    borderRadius: 3,
  },
  center: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  obsBadge: {
    fontSize: 9,
    color: '#f0b90b',
    padding: '2px 6px',
    border: '1px solid #f0b90b40',
    borderRadius: 3,
    background: '#f0b90b08',
    letterSpacing: 1,
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  time: { color: '#555', fontSize: 10 },
  err: { color: '#ef5350', fontSize: 9 },
};
