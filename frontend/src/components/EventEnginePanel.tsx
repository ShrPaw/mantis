// MANTIS Operator Dashboard — Event Engine Panel (holographic theme)
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { useStore } from '../store';
import { T } from '../styles/operatorTheme';

export const EventEnginePanel: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const ee = status?.event_engine;
  const spe = status?.spe;
  const wsEvents = useStore(s => s.events);
  const wsEventStats = useStore(s => s.eventStats);

  return (
    <div style={S.panel}>
      <div style={S.title}>EVENT ENGINE</div>
      <div style={{ marginBottom: 6 }}>
        <span style={{
          ...S.statusBadge,
          color: ee?.enabled ? T.green.primary : T.status.danger,
          borderColor: (ee?.enabled ? T.green.primary : T.status.danger) + '40',
          textShadow: ee?.enabled ? `0 0 8px ${T.green.glow}` : 'none',
        }}>
          {ee?.status?.toUpperCase() ?? 'UNKNOWN'}
        </span>
      </div>
      <div style={S.grid}>
        <Row label="Total events" value={(ee?.total ?? wsEventStats.total ?? 0).toString()} />
        <Row label="Fired" value={(ee?.fired ?? wsEventStats.fired ?? 0).toString()} />
        <Row label="Deduped" value={(ee?.deduped ?? wsEventStats.deduped ?? 0).toString()} />
        <Row label="Pending" value={(ee?.pending_outcomes ?? wsEventStats.pending_outcomes ?? 0).toString()} />
        <Row label="Watchlisted" value={(ee?.watchlisted ?? 0).toString()} color={T.status.warning} />
        <Row label="Blacklisted" value={(ee?.blacklisted ?? 0).toString()} color={T.status.danger} />
      </div>
      <div style={S.divider} />
      <div style={S.section}>
        <div style={S.sectionLabel}>SPE MODULE</div>
        <Row label="Evaluations" value={(spe?.raw_evaluations ?? 0).toLocaleString()} />
        <Row label="Emitted" value={(spe?.emitted_events ?? 0).toString()} color={T.green.primary} />
        <Row label="Full 8L passes" value={(spe?.full_8_layer_passes ?? 0).toString()} color={spe?.full_8_layer_passes ? T.green.primary : T.text.muted} />
        <Row label="State" value={spe?.current_state ?? 'IDLE'} color={spe?.current_state === 'IDLE' ? T.text.muted : T.status.warning} />
      </div>
      <div style={S.divider} />
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={S.sectionLabel}>RECENT EVENTS</div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          {wsEvents.length === 0 ? (
            <div style={{ color: T.text.faint, fontSize: 9, fontStyle: 'italic', textAlign: 'center', padding: 8 }}>No events detected</div>
          ) : wsEvents.slice(0, 5).map((evt, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', borderBottom: `1px solid ${T.border.dim}` }}>
              <span style={{ color: T.text.muted, fontSize: 8 }}>{evt.event_type}</span>
              <span style={{ color: evt.side === 'buy' ? T.green.primary : T.status.danger, fontSize: 9, fontWeight: 600 }}>{evt.side?.toUpperCase()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const Row: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10 }}>
    <span style={{ color: T.text.dim }}>{label}</span>
    <span style={{ color: color || T.text.main, fontWeight: 600 }}>{value}</span>
  </div>
);

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: `linear-gradient(180deg, ${T.bg.panel} 0%, ${T.bg.surface} 100%)`,
    border: `1px solid ${T.border.mid}`,
    borderRadius: 6,
    padding: '10px 12px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  title: { fontSize: 9, fontWeight: 700, color: T.green.primary, letterSpacing: 2, marginBottom: 8, textShadow: `0 0 8px ${T.green.glow}` },
  statusBadge: { fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 3, border: '1px solid', letterSpacing: 1 },
  grid: { display: 'flex', flexDirection: 'column' as const, gap: 3 },
  divider: { height: 1, background: T.border.dim, margin: '8px 0' },
  section: { display: 'flex', flexDirection: 'column' as const, gap: 3 },
  sectionLabel: { fontSize: 8, color: T.text.muted, letterSpacing: 1, marginBottom: 2 },
};
