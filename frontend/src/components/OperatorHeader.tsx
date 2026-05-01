// MANTIS Operator Dashboard — Header (compact system status)
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

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
        <Metric label="ENGINE" value={status?.event_engine?.status?.toUpperCase() ?? '—'} color={status?.event_engine?.enabled ? T.green.primary : T.status.danger} />
        <Divider />
        <Metric label="SPE" value={spe?.enabled ? 'ACTIVE' : 'OFF'} color={spe?.enabled ? T.green.primary : T.text.muted} />
        <Divider />
        <Metric label="EVALS" value={(spe?.raw_evaluations ?? 0).toLocaleString()} color={spe?.raw_evaluations ? T.green.primary : T.text.muted} />
        <Divider />
        <span style={S.obsBadge}>⚠ OBSERVATION-ONLY</span>
      </div>

      <div style={S.right}>
        <ViewToggle />
        <span style={S.time}>{now}</span>
        {error && <span style={S.err}>{error}</span>}
      </div>
    </header>
  );
};

const StatusDot: React.FC<{ ok: boolean; label: string }> = ({ ok, label }) => (
  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
    <span style={{
      color: ok ? T.green.primary : T.status.danger,
      fontSize: 10,
      textShadow: ok ? `0 0 6px ${T.green.glowStrong}` : 'none',
    }}>●</span>
    <span style={{ color: ok ? T.green.primary : T.status.danger, fontWeight: 700, letterSpacing: 1, fontSize: 9 }}>{label}</span>
  </span>
);

const Metric: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color }) => (
  <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
    <span style={{ color: T.text.muted, fontSize: 7, letterSpacing: 1 }}>{label}</span>
    <span style={{ color: color || T.text.main, fontWeight: 600, fontSize: 9 }}>{value}</span>
  </span>
);

const Divider = () => (
  <span style={{ width: 1, height: 12, background: T.border.mid, margin: '0 1px' }} />
);

const ViewToggle: React.FC = () => (
  <div style={{ display: 'flex', borderRadius: 3, overflow: 'hidden', border: `1px solid ${T.border.mid}` }}>
    <span style={{
      background: T.green.glow,
      color: T.green.primary,
      padding: '2px 8px',
      fontSize: 8,
      fontWeight: 700,
      letterSpacing: 1,
      borderBottom: `2px solid ${T.green.primary}`,
      textShadow: `0 0 8px ${T.green.glow}`,
    }}>OPERATOR</span>
    <a href="/?view=micro" style={{
      background: 'transparent',
      color: T.text.muted,
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
    padding: '3px 12px',
    background: 'linear-gradient(180deg, #0a1218 0%, #070e14 100%)',
    borderBottom: `1px solid ${T.border.mid}`,
    flexShrink: 0,
    height: 28,
    zIndex: 10,
    boxShadow: `0 1px 8px rgba(0,0,0,0.3), inset 0 -1px 0 ${T.border.dim}`,
  },
  left: { display: 'flex', alignItems: 'center', gap: 6 },
  logo: {
    fontSize: 12,
    color: T.green.primary,
    textShadow: `0 0 10px ${T.green.glowStrong}`,
  },
  title: {
    fontSize: 11,
    fontWeight: 700,
    color: T.green.primary,
    letterSpacing: 3,
    textShadow: `0 0 12px ${T.green.glow}`,
  },
  badge: {
    fontSize: 7,
    color: T.green.primary,
    letterSpacing: 2,
    padding: '1px 4px',
    border: `1px solid ${T.border.bright}`,
    borderRadius: 3,
    background: T.green.glow,
    textShadow: `0 0 6px ${T.green.glow}`,
  },
  source: {
    fontSize: 7,
    color: T.text.muted,
    letterSpacing: 2,
    padding: '1px 4px',
    border: `1px solid ${T.border.dim}`,
    borderRadius: 3,
  },
  center: { display: 'flex', alignItems: 'center', gap: 4 },
  obsBadge: {
    fontSize: 7,
    color: T.accent.gold,
    padding: '1px 5px',
    border: `1px solid rgba(240, 208, 96, 0.25)`,
    borderRadius: 3,
    background: 'rgba(240, 208, 96, 0.06)',
    letterSpacing: 1,
  },
  right: { display: 'flex', alignItems: 'center', gap: 6 },
  time: { color: T.text.muted, fontSize: 8 },
  err: { color: T.status.danger, fontSize: 8 },
};
