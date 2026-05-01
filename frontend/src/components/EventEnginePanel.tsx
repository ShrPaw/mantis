// MANTIS Operator Dashboard — Event Engine Panel
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { useStore } from '../store';

export const EventEnginePanel: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const ee = status?.event_engine;
  const spe = status?.spe;
  const wsEvents = useStore(s => s.events);
  const wsEventStats = useStore(s => s.eventStats);

  return (
    <div style={S.panel}>
      <div style={S.title}>EVENT ENGINE</div>

      <div style={S.statusRow}>
        <span style={{
          ...S.statusBadge,
          color: ee?.enabled ? '#26a69a' : '#ef5350',
          borderColor: (ee?.enabled ? '#26a69a' : '#ef5350') + '40',
        }}>
          {ee?.status?.toUpperCase() ?? 'UNKNOWN'}
        </span>
      </div>

      <div style={S.grid}>
        <Row label="Total events" value={(ee?.total ?? wsEventStats.total ?? 0).toString()} />
        <Row label="Fired" value={(ee?.fired ?? wsEventStats.fired ?? 0).toString()} />
        <Row label="Deduped" value={(ee?.deduped ?? wsEventStats.deduped ?? 0).toString()} />
        <Row label="Pending" value={(ee?.pending_outcomes ?? wsEventStats.pending_outcomes ?? 0).toString()} />
        <Row label="Watchlisted" value={(ee?.watchlisted ?? 0).toString()} color="#ff9800" />
        <Row label="Blacklisted" value={(ee?.blacklisted ?? 0).toString()} color="#ef5350" />
      </div>

      <div style={S.divider} />

      <div style={S.speSection}>
        <div style={S.sectionLabel}>SPE MODULE</div>
        <Row label="Evaluations" value={(spe?.raw_evaluations ?? 0).toLocaleString()} />
        <Row label="Emitted" value={(spe?.emitted_events ?? 0).toString()} color="#f0b90b" />
        <Row label="Full 8L passes" value={(spe?.full_8_layer_passes ?? 0).toString()} color={spe?.full_8_layer_passes ? '#26a69a' : '#555'} />
        <Row label="State" value={spe?.current_state ?? 'IDLE'} color={spe?.current_state === 'IDLE' ? '#555' : '#ff9800'} />
      </div>

      <div style={S.divider} />

      <div style={S.recentSection}>
        <div style={S.sectionLabel}>RECENT EVENTS</div>
        <div style={S.eventList}>
          {wsEvents.length === 0 ? (
            <div style={S.noEvents}>No events detected</div>
          ) : (
            wsEvents.slice(0, 5).map((evt, i) => (
              <div key={i} style={S.eventRow}>
                <span style={{ color: '#555', fontSize: 8 }}>{evt.event_type}</span>
                <span style={{ color: evt.side === 'buy' ? '#26a69a' : '#ef5350', fontSize: 9, fontWeight: 600 }}>{evt.side?.toUpperCase()}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

const Row: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10 }}>
    <span style={{ color: '#555' }}>{label}</span>
    <span style={{ color: color || '#ccc', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{value}</span>
  </div>
);

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: '#0c0c14',
    border: '1px solid #1a1a2e',
    borderRadius: 6,
    padding: '10px 12px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  title: {
    fontSize: 10,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 2,
    marginBottom: 8,
  },
  statusRow: {
    marginBottom: 6,
  },
  statusBadge: {
    fontSize: 10,
    fontWeight: 700,
    padding: '2px 8px',
    borderRadius: 3,
    border: '1px solid',
    letterSpacing: 1,
  },
  grid: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 3,
  },
  divider: {
    height: 1,
    background: '#1a1a2e',
    margin: '8px 0',
  },
  speSection: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 3,
  },
  sectionLabel: {
    fontSize: 8,
    color: '#555',
    letterSpacing: 1,
    marginBottom: 2,
  },
  recentSection: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    overflow: 'hidden',
  },
  eventList: {
    flex: 1,
    overflow: 'auto',
  },
  noEvents: {
    color: '#444',
    fontSize: 9,
    fontStyle: 'italic',
    textAlign: 'center' as const,
    padding: 8,
  },
  eventRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '2px 0',
    borderBottom: '1px solid #111',
  },
};
