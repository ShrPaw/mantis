// MANTIS — Event Tape
// Scrolling event stream: timestamp, type, confidence, color-coded severity
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { useStore } from '../store';
import { T } from '../styles/operatorTheme';

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function getEventColor(type: string): string {
  switch (type) {
    case 'absorption': return '#00e5c8';
    case 'exhaustion': return '#ffcc66';
    case 'liquidity_sweep': return '#ff5f5f';
    case 'delta_divergence': return '#66d9ff';
    case 'imbalance': return '#9c27b0';
    case 'large_trade_cluster': return '#ff9800';
    case 'range_break': return '#f0b90b';
    case 'vwap_reaction': return '#39ff88';
    case 'structural_pressure_execution': return T.green.primary;
    default: return T.text.muted;
  }
}

function getEventIcon(type: string): string {
  switch (type) {
    case 'absorption': return '◈';
    case 'exhaustion': return '⊘';
    case 'liquidity_sweep': return '⚡';
    case 'delta_divergence': return '⇄';
    case 'imbalance': return '◐';
    case 'large_trade_cluster': return '◉';
    case 'range_break': return '⊞';
    case 'vwap_reaction': return '◇';
    case 'structural_pressure_execution': return '◆';
    default: return '•';
  }
}

export const EventTape: React.FC = () => {
  const events = useStore(s => s.events);
  const speEvents = useStore(s => s.speEvents);
  const opStatus = useOperatorStore(s => s.status);
  const spe = opStatus?.spe;

  // Merge and sort events by timestamp
  const allEvents = [
    ...events.slice(0, 20).map(e => ({
      ts: e.timestamp,
      type: e.event_type,
      side: e.side,
      confidence: e.scores?.confidence_score,
      strength: e.scores?.strength_score,
      explanation: e.explanation,
      source: 'ENGINE' as const,
    })),
    ...speEvents.slice(0, 10).map(e => ({
      ts: e.timestamp,
      type: 'SPE',
      side: e.direction === 'SHORT' ? 'sell' : 'buy',
      confidence: e.confidence_score,
      strength: e.pressure_strength,
      explanation: `${e.mantis_state} ${e.direction} — confidence ${(e.confidence_score * 100).toFixed(0)}%`,
      source: 'SPE' as const,
    })),
  ].sort((a, b) => b.ts - a.ts).slice(0, 25);

  // SPE state summary
  const currentState = spe?.current_state ?? 'IDLE';
  const raw = spe?.raw_evaluations ?? 0;
  const emitted = spe?.emitted_events ?? 0;

  return (
    <div style={S.panel}>
      <div style={S.header}>
        <span style={S.title}>EVENT TAPE</span>
        <span style={S.stats}>
          {allEvents.length} events · {raw} evals · {emitted} emitted
        </span>
      </div>

      {/* SPE state strip */}
      <div style={S.stateStrip}>
        <span style={{
          ...S.stateBadge,
          color: currentState === 'IDLE' ? T.text.muted :
                 currentState === 'CASCADE' ? T.status.danger : T.status.warning,
          borderColor: (currentState === 'IDLE' ? T.text.muted :
                 currentState === 'CASCADE' ? T.status.danger : T.status.warning) + '30',
        }}>
          {currentState}
        </span>
        {emitted > 0 && (
          <span style={S.candBadge}>● {emitted} CANDIDATE</span>
        )}
        {raw === 0 && (
          <span style={S.silentText}>0 SPE events — system silent by design</span>
        )}
      </div>

      {/* Event list */}
      <div style={S.list}>
        {allEvents.length === 0 ? (
          <div style={S.empty}>
            <span style={{ color: T.green.primary }}>◆</span>
            <span>No events observed. Waiting for market activity.</span>
          </div>
        ) : allEvents.map((evt, i) => {
          const color = getEventColor(evt.type);
          const icon = getEventIcon(evt.type);
          return (
            <div key={i} style={S.row}>
              <span style={S.time}>{formatTime(evt.ts)}</span>
              <span style={{ ...S.icon, color }}>{icon}</span>
              <span style={{ ...S.type, color }}>{evt.type.toUpperCase()}</span>
              <span style={{ ...S.side, color: evt.side === 'buy' ? T.green.primary : T.status.danger }}>
                {evt.side?.toUpperCase() ?? '—'}
              </span>
              <span style={S.conf}>
                {evt.confidence != null ? `${(evt.confidence * 100).toFixed(0)}%` : '—'}
              </span>
              <span style={S.source}>{evt.source}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: `linear-gradient(180deg, ${T.bg.panel} 0%, ${T.bg.surface} 100%)`,
    border: `1px solid ${T.border.mid}`,
    borderRadius: 6,
    padding: '6px 8px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4,
  },
  title: {
    fontSize: 8, fontWeight: 700, color: T.green.primary, letterSpacing: 2,
    textShadow: `0 0 8px ${T.green.glow}`,
  },
  stats: { fontSize: 7, color: T.text.muted },
  stateStrip: {
    display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4,
    padding: '3px 6px', background: T.bg.card, borderRadius: 3,
  },
  stateBadge: {
    fontSize: 8, fontWeight: 700, letterSpacing: 1, padding: '1px 5px',
    borderRadius: 2, border: '1px solid',
  },
  candBadge: {
    fontSize: 7, fontWeight: 700, color: T.green.primary, letterSpacing: 0.5,
  },
  silentText: { fontSize: 7, color: T.text.faint, fontStyle: 'italic' },
  list: { flex: 1, overflow: 'auto' },
  row: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '2px 0', borderBottom: `1px solid ${T.border.dim}`,
  },
  time: { fontSize: 7, color: T.text.faint, width: 58, flexShrink: 0, fontFamily: "'JetBrains Mono', monospace" },
  icon: { fontSize: 10, width: 12, textAlign: 'center', flexShrink: 0 },
  type: { fontSize: 8, fontWeight: 700, letterSpacing: 0.5, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  side: { fontSize: 8, fontWeight: 600, width: 32, textAlign: 'center', flexShrink: 0 },
  conf: { fontSize: 8, color: T.text.dim, width: 30, textAlign: 'right', flexShrink: 0 },
  source: { fontSize: 6, color: T.text.faint, letterSpacing: 1, width: 28, textAlign: 'right', flexShrink: 0 },
  empty: {
    flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', gap: 4, color: T.text.dim, fontSize: 10,
  },
};
