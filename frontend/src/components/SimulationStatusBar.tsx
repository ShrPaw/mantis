// MANTIS — Simulation Status Bar
// Live simulation / paper observation mode indicator
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

export const SimulationStatusBar: React.FC = () => {
  const connected = useOperatorStore(s => s.connected);
  const status = useOperatorStore(s => s.status);
  const backend = status?.backend;
  const spe = status?.spe;

  return (
    <div style={S.bar}>
      <div style={S.left}>
        <span style={S.modeChip}>◆ LIVE OBSERVATION</span>
        <Divider />
        <span style={S.modeChip}>PAPER SIMULATION</span>
        <Divider />
        <span style={{ ...S.modeChip, color: T.status.danger }}>EXECUTION DISABLED</span>
      </div>
      <div style={S.center}>
        <StatusDot ok={connected} label={connected ? 'ONLINE' : 'OFFLINE'} />
        <Divider />
        <Metric label="TRADES" value={backend?.trade_count?.toLocaleString() ?? '—'} />
        <Divider />
        <Metric label="SPE" value={spe?.enabled ? 'ACTIVE' : 'OFF'} color={spe?.enabled ? T.green.primary : T.text.muted} />
        <Divider />
        <Metric label="EVALS" value={(spe?.raw_evaluations ?? 0).toLocaleString()} />
        <Divider />
        <Metric label="STATE" value={spe?.current_state ?? 'IDLE'} color={spe?.current_state === 'IDLE' ? T.text.muted : T.status.warning} />
      </div>
      <div style={S.right}>
        <span style={S.time}>{new Date().toLocaleTimeString('en-US', { hour12: false })}</span>
      </div>
    </div>
  );
};

const StatusDot: React.FC<{ ok: boolean; label: string }> = ({ ok, label }) => (
  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
    <span style={{ color: ok ? T.green.primary : T.status.danger, fontSize: 8, textShadow: ok ? `0 0 4px ${T.green.glow}` : 'none' }}>●</span>
    <span style={{ color: ok ? T.green.primary : T.status.danger, fontWeight: 700, letterSpacing: 1, fontSize: 8 }}>{label}</span>
  </span>
);

const Metric: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color }) => (
  <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
    <span style={{ color: T.text.muted, fontSize: 7, letterSpacing: 0.5 }}>{label}</span>
    <span style={{ color: color || T.text.main, fontWeight: 600, fontSize: 8 }}>{value}</span>
  </span>
);

const Divider = () => (
  <span style={{ width: 1, height: 10, background: T.border.mid, margin: '0 1px' }} />
);

const S: Record<string, React.CSSProperties> = {
  bar: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '2px 10px',
    background: 'linear-gradient(180deg, #0a1218 0%, #070e14 100%)',
    borderBottom: `1px solid ${T.border.mid}`,
    flexShrink: 0, height: 22, zIndex: 10,
    boxShadow: `0 1px 6px rgba(0,0,0,0.3), inset 0 -1px 0 ${T.border.dim}`,
  },
  left: { display: 'flex', alignItems: 'center', gap: 4 },
  center: { display: 'flex', alignItems: 'center', gap: 4 },
  right: { display: 'flex', alignItems: 'center', gap: 6 },
  modeChip: {
    fontSize: 7, fontWeight: 700, color: T.accent.gold, letterSpacing: 1.5,
    padding: '1px 4px', borderRadius: 2,
    background: 'rgba(240, 208, 96, 0.06)',
    border: `1px solid rgba(240, 208, 96, 0.15)`,
  },
  time: { color: T.text.faint, fontSize: 7 },
};
