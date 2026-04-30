// MANTIS — SPE Panel Component (Observation-Only Mode)
// Displays Structural Pressure Execution context detection and status
// THIS IS NOT A TRADING SIGNAL. Context detection only.

import React from 'react';
import { useStore } from '../store';
import type { SPEEvent, SPEStats } from '../types';

// ============================================================
// SPE State Badge
// ============================================================
const StateBadge: React.FC<{ state: string }> = ({ state }) => {
  const color = state === 'CASCADE' ? '#ff4444' : state === 'UNWIND' ? '#ff8800' : '#666';
  return (
    <span style={{
      background: color,
      color: '#fff',
      padding: '2px 8px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 700,
      fontFamily: 'monospace',
      letterSpacing: 1,
    }}>
      {state}
    </span>
  );
};

// ============================================================
// Direction Context Badge
// ============================================================
const DirectionBadge: React.FC<{ direction: string }> = ({ direction }) => {
  const isLong = direction === 'LONG';
  return (
    <span style={{
      background: isLong ? 'rgba(0,200,83,0.15)' : 'rgba(255,23,68,0.15)',
      color: isLong ? '#00c853' : '#ff1744',
      padding: '2px 8px',
      borderRadius: 4,
      fontSize: 12,
      fontWeight: 700,
      fontFamily: 'monospace',
      border: `1px solid ${isLong ? '#00c85340' : '#ff174440'}`,
    }}>
      {direction} CONTEXT
    </span>
  );
};

// ============================================================
// Confidence Bar
// ============================================================
const ConfidenceBar: React.FC<{ score: number }> = ({ score }) => {
  const color = score >= 80 ? '#00c853' : score >= 60 ? '#ff8800' : '#ff1744';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 100, height: 6, background: '#333',
        borderRadius: 3, overflow: 'hidden',
      }}>
        <div style={{
          width: `${score}%`, height: '100%',
          background: color, borderRadius: 3,
        }} />
      </div>
      <span style={{ fontSize: 11, color, fontFamily: 'monospace' }}>
        {score.toFixed(0)}
      </span>
    </div>
  );
};

// ============================================================
// Layer Status Grid
// ============================================================
const LayerStatus: React.FC<{ event: SPEEvent }> = ({ event }) => {
  const layers = [
    { name: 'L1 Context', ok: event.mantis_state !== 'IDLE', detail: event.mantis_state },
    { name: 'L2 Pressure', ok: event.crowd_direction !== 'NONE', detail: `${event.pressure_strength.toFixed(0)}%` },
    { name: 'L3 Displace', ok: event.displacement_strength > 0, detail: `${event.displacement_strength.toFixed(0)}%` },
    { name: 'L4 Sweep', ok: event.sweep_detected, detail: event.sweep_direction || '—' },
    { name: 'L5 Trap', ok: event.trap_detected, detail: 'CONFIRMED' },
    { name: 'L6 Exec', ok: event.execution_quality >= 70, detail: `${event.execution_quality.toFixed(0)}%` },
    { name: 'L7 Entry', ok: event.entry_price > 0, detail: `$${event.entry_price.toLocaleString()}` },
    { name: 'L8 Exit', ok: event.tp_levels.length > 0, detail: `${event.tp_levels.length} TP` },
  ];

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 4,
      fontSize: 10,
      fontFamily: 'monospace',
    }}>
      {layers.map(l => (
        <div key={l.name} style={{
          background: l.ok ? 'rgba(0,200,83,0.1)' : 'rgba(255,23,68,0.1)',
          border: `1px solid ${l.ok ? '#00c85340' : '#ff174440'}`,
          borderRadius: 4,
          padding: '4px 6px',
          textAlign: 'center',
        }}>
          <div style={{ color: l.ok ? '#00c853' : '#ff1744', fontWeight: 700 }}>
            {l.name}
          </div>
          <div style={{ color: '#999', marginTop: 2 }}>{l.detail}</div>
        </div>
      ))}
    </div>
  );
};

// ============================================================
// Single SPE Event Card (Observation-Only Language)
// ============================================================
const SPEEventCard: React.FC<{ event: SPEEvent }> = ({ event }) => {
  const timeStr = new Date(event.timestamp * 1000).toLocaleTimeString();

  return (
    <div style={{
      background: '#1a1a2e',
      border: '1px solid #333',
      borderRadius: 8,
      padding: 12,
      marginBottom: 8,
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: 8,
      }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{
            background: '#f0b90b20',
            color: '#f0b90b',
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: 10,
            fontWeight: 700,
            fontFamily: 'monospace',
            border: '1px solid #f0b90b40',
          }}>
            WATCH
          </span>
          <DirectionBadge direction={event.direction} />
          <StateBadge state={event.mantis_state} />
          <span style={{ color: '#666', fontSize: 11, fontFamily: 'monospace' }}>
            {timeStr}
          </span>
        </div>
        <ConfidenceBar score={event.confidence_score} />
      </div>

      {/* Context Label */}
      <div style={{
        background: '#f0b90b10',
        border: '1px solid #f0b90b30',
        borderRadius: 4,
        padding: '4px 8px',
        marginBottom: 8,
        fontSize: 11,
        fontFamily: 'monospace',
        color: '#f0b90b',
      }}>
        SPE Context Detected — Execution Window Candidate
      </div>

      {/* Layer Status */}
      <LayerStatus event={event} />

      {/* Price Levels */}
      <div style={{
        display: 'flex', gap: 16, marginTop: 8,
        fontSize: 11, fontFamily: 'monospace',
      }}>
        <div>
          <span style={{ color: '#666' }}>Zone: </span>
          <span style={{ color: '#fff' }}>${event.entry_price.toLocaleString()}</span>
        </div>
        <div>
          <span style={{ color: '#666' }}>Invalidation: </span>
          <span style={{ color: '#ff1744' }}>${event.stop_loss.toLocaleString()}</span>
        </div>
        {event.tp_levels.map((tp, i) => (
          <div key={i}>
            <span style={{ color: '#666' }}>TP{i + 1}: </span>
            <span style={{ color: '#00c853' }}>${tp.toLocaleString()}</span>
          </div>
        ))}
      </div>

      {/* Metrics */}
      <div style={{
        display: 'flex', gap: 16, marginTop: 6,
        fontSize: 10, fontFamily: 'monospace', color: '#888',
      }}>
        <span>Imbalance: {event.imbalance_score.toFixed(0)}</span>
        <span>Exec Q: {event.execution_quality.toFixed(0)}</span>
        <span>Risk: {event.risk_score.toFixed(0)}</span>
        <span>Spread: {event.spread_bps.toFixed(1)} bps</span>
        <span>Funding Z: {event.funding_z.toFixed(2)}</span>
      </div>

      {/* Explanation */}
      <div style={{
        marginTop: 6, fontSize: 10, color: '#666',
        fontFamily: 'monospace', lineHeight: 1.4,
      }}>
        {event.explanation}
      </div>

      {/* Observation-Only Notice */}
      <div style={{
        marginTop: 6, fontSize: 9, color: '#555',
        fontFamily: 'monospace', fontStyle: 'italic',
      }}>
        ⚠ Observation-only — no execution — context detection for validation
      </div>
    </div>
  );
};

// ============================================================
// Layer Stats Summary
// ============================================================
const LayerStatsSummary: React.FC<{ stats: SPEStats }> = ({ stats }) => {
  const layerStats = stats.layer_stats;
  if (!layerStats?.layer_pass_fail) return null;

  const layers = Object.entries(layerStats.layer_pass_fail);
  if (layers.length === 0) return null;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(4, 1fr)',
      gap: 4,
      fontSize: 9,
      fontFamily: 'monospace',
      marginBottom: 12,
    }}>
      {layers.map(([name, counts]) => {
        const total = counts.pass + counts.fail;
        const rate = total > 0 ? (counts.pass / total * 100) : 0;
        return (
          <div key={name} style={{
            background: '#111',
            border: '1px solid #222',
            borderRadius: 4,
            padding: '3px 5px',
            textAlign: 'center',
          }}>
            <div style={{ color: '#888', fontSize: 8 }}>{name.replace('L', 'L')}</div>
            <div style={{ color: rate > 50 ? '#00c853' : '#ff8800', fontWeight: 700 }}>
              {rate.toFixed(0)}%
            </div>
            <div style={{ color: '#555', fontSize: 8 }}>
              {counts.pass}/{total}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ============================================================
// SPE Stats Bar
// ============================================================
const SPEStatsBar: React.FC<{ stats: SPEStats }> = ({ stats }) => {
  return (
    <div style={{
      display: 'flex', gap: 16, padding: '8px 0',
      fontSize: 11, fontFamily: 'monospace', color: '#888',
      borderBottom: '1px solid #333', marginBottom: 12,
      flexWrap: 'wrap',
    }}>
      <span>
        <span style={{ color: stats.enabled ? '#00c853' : '#ff1744' }}>●</span>
        {' '}SPE {stats.enabled ? 'ACTIVE' : 'OFF'}
      </span>
      <span>
        <span style={{ color: '#f0b90b' }}>●</span>
        {' '}Mode: OBSERVATION-ONLY
      </span>
      <span>State: <StateBadge state={stats.state} /></span>
      <span>Signals: {stats.signals_evaluated.toLocaleString()}</span>
      <span>Events: {stats.events_emitted}</span>
      {stats.layer_stats && (
        <>
          <span>4L Passes: {stats.layer_stats.partial_4_layer_passes}</span>
          <span>6L Passes: {stats.layer_stats.partial_6_layer_passes}</span>
          <span>8L Passes: {stats.layer_stats.full_8_layer_passes}</span>
        </>
      )}
    </div>
  );
};

// ============================================================
// Main SPE Panel
// ============================================================
export const SPEPanel: React.FC = () => {
  const speEvents = useStore(s => s.speEvents);
  const speStats = useStore(s => s.speStats);

  if (!speStats.enabled && speEvents.length === 0) {
    return (
      <div style={{
        background: '#0d0d1a',
        border: '1px solid #333',
        borderRadius: 8,
        padding: 16,
        color: '#666',
        fontFamily: 'monospace',
        fontSize: 12,
        textAlign: 'center',
      }}>
        SPE Module: DISABLED
      </div>
    );
  }

  return (
    <div style={{
      background: '#0d0d1a',
      border: '1px solid #333',
      borderRadius: 8,
      padding: 16,
    }}>
      {/* Title */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: 8,
      }}>
        <h3 style={{
          margin: 0, fontSize: 14, fontFamily: 'monospace',
          color: '#fff', letterSpacing: 1,
        }}>
          SPE — Structural Pressure Context
        </h3>
        <span style={{ fontSize: 10, color: '#666', fontFamily: 'monospace' }}>
          {speEvents.length} contexts detected
        </span>
      </div>

      {/* Observation-Only Banner */}
      <div style={{
        background: '#f0b90b10',
        border: '1px solid #f0b90b30',
        borderRadius: 4,
        padding: '6px 10px',
        marginBottom: 12,
        fontSize: 11,
        fontFamily: 'monospace',
        color: '#f0b90b',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <span>⚠ OBSERVATION-ONLY — No execution — Context detection for validation</span>
        <span style={{ fontSize: 9, color: '#888' }}>
          SPE_ENABLED=true | SPE_OBSERVATION_ONLY=true
        </span>
      </div>

      {/* Stats */}
      <SPEStatsBar stats={speStats} />

      {/* Layer Stats Summary */}
      <LayerStatsSummary stats={speStats} />

      {/* Events */}
      <div style={{ maxHeight: 600, overflowY: 'auto' }}>
        {speEvents.length === 0 ? (
          <div style={{
            textAlign: 'center', color: '#444',
            fontFamily: 'monospace', fontSize: 12, padding: 20,
          }}>
            No SPE contexts detected yet. Waiting for structural conditions...
          </div>
        ) : (
          speEvents.map(event => (
            <SPEEventCard key={event.event_id} event={event} />
          ))
        )}
      </div>
    </div>
  );
};

export default SPEPanel;
