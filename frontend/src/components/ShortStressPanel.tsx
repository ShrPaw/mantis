// MANTIS Operator Dashboard — SHORT_STRESS Candidate Panel
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';

function analyzeBlockReason(layerCounts: Record<string, { pass: number; fail: number; not_evaluated: number }>): string {
  const order = ['L1_context_gate', 'L2_pressure', 'L3_displacement', 'L4_sweep', 'L5_trap', 'L6_execution_filter', 'L7_entry_zone', 'L8_exit_model', 'confidence_gate'];
  for (const key of order) {
    const c = layerCounts[key];
    if (c && c.fail > 0 && c.pass === 0) {
      const names: Record<string, string> = {
        L1_context_gate: 'L1 — No CASCADE/UNWIND state',
        L2_pressure: 'L2 — No crowd pressure detected',
        L3_displacement: 'L3 — No displacement confirmed',
        L4_sweep: 'L4 — No structural sweep',
        L5_trap: 'L5 — No trap confirmation',
        L6_execution_filter: 'L6 — Execution quality too low',
        L7_entry_zone: 'L7 — No valid entry zone',
        L8_exit_model: 'L8 — R:R insufficient',
        confidence_gate: 'Confidence — Below threshold',
      };
      return names[key] ?? key;
    }
  }
  if (layerCounts['L1_context_gate']?.not_evaluated > 0) return 'L1 blocked — market is IDLE';
  return 'No evaluations performed';
}

export const ShortStressPanel: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const spe = status?.spe;
  const layerCounts = spe?.layer_counts ?? {};
  const raw = spe?.raw_evaluations ?? 0;
  const currentState = spe?.current_state ?? 'IDLE';
  const emitted = spe?.emitted_events ?? 0;
  const full8 = spe?.full_8_layer_passes ?? 0;

  // Determine if a SHORT_STRESS candidate is active
  // A candidate exists when full_8_layer_passes > 0 and current state is CASCADE/UNWIND
  const candidateActive = full8 > 0 && (currentState === 'CASCADE' || currentState === 'UNWIND');
  const blockReason = analyzeBlockReason(layerCounts);

  // High volume/volatility heuristics
  const freq = status?.market?.trade_frequency ?? 0;
  const highVolume = freq > 3;
  const highVolatility = currentState === 'CASCADE' || currentState === 'UNWIND';

  return (
    <div style={S.panel}>
      <div style={S.title}>SPE_SHORT_STRESS CANDIDATE</div>

      <div style={S.candidateRow}>
        <span style={{
          ...S.candidateBadge,
          background: candidateActive ? 'rgba(239, 83, 80, 0.15)' : 'rgba(100, 100, 100, 0.08)',
          color: candidateActive ? '#ef5350' : '#555',
          borderColor: candidateActive ? '#ef535040' : '#333',
        }}>
          {candidateActive ? '● CANDIDATE ACTIVE' : '○ NO CANDIDATE'}
        </span>
      </div>

      <div style={S.grid}>
        <Row label="Direction" value="SHORT ONLY" color="#ef5350" />
        <Row label="Crowd Direction" value={candidateActive ? 'LONG_CROWD' : '—'} color={candidateActive ? '#ff9800' : '#555'} />
        <Row label="Mantis State" value={currentState} color={currentState === 'IDLE' ? '#555' : '#ff9800'} />
        <Row label="High Volume" value={highVolume ? 'YES' : 'NO'} color={highVolume ? '#26a69a' : '#555'} />
        <Row label="High Volatility" value={highVolatility ? 'YES' : 'NO'} color={highVolatility ? '#26a69a' : '#555'} />
        <Row label="Full 8-Layer Pass" value={full8 > 0 ? `YES (${full8})` : 'NO'} color={full8 > 0 ? '#26a69a' : '#ef5350'} />
        <Row label="Total Candidates" value={emitted.toString()} color={emitted > 0 ? '#f0b90b' : '#555'} />
      </div>

      <div style={S.divider} />

      <div style={S.blockSection}>
        <span style={S.blockLabel}>Current block reason:</span>
        <span style={S.blockValue}>{raw > 0 ? blockReason : 'No evaluations performed'}</span>
      </div>

      {!candidateActive && raw > 0 && (
        <div style={S.silentNotice}>
          No valid SHORT_STRESS context. System intentionally silent.
        </div>
      )}

      {raw === 0 && (
        <div style={S.silentNotice}>
          System silent by design. No valid high-pressure context.
        </div>
      )}

      <div style={S.obsNotice}>
        ⚠ Observation-only — no execution — context detection for validation
      </div>
    </div>
  );
};

const Row: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10 }}>
    <span style={{ color: '#666' }}>{label}</span>
    <span style={{ color, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{value}</span>
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
  },
  title: {
    fontSize: 10,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 2,
    marginBottom: 8,
  },
  candidateRow: {
    marginBottom: 8,
  },
  candidateBadge: {
    display: 'inline-block',
    fontSize: 12,
    fontWeight: 700,
    padding: '4px 12px',
    borderRadius: 4,
    border: '1px solid',
    letterSpacing: 1,
  },
  grid: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 4,
  },
  divider: {
    height: 1,
    background: '#1a1a2e',
    margin: '8px 0',
  },
  blockSection: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 3,
    padding: '6px 8px',
    background: '#111',
    borderRadius: 4,
    border: '1px solid #1a1a2e',
  },
  blockLabel: {
    fontSize: 8,
    color: '#555',
    letterSpacing: 1,
    textTransform: 'uppercase' as const,
  },
  blockValue: {
    fontSize: 10,
    color: '#888',
    fontFamily: "'JetBrains Mono', monospace",
  },
  silentNotice: {
    marginTop: 6,
    padding: '6px 8px',
    background: '#f0b90b08',
    border: '1px solid #f0b90b20',
    borderRadius: 4,
    fontSize: 10,
    color: '#f0b90b',
    textAlign: 'center' as const,
    fontStyle: 'italic',
  },
  obsNotice: {
    marginTop: 'auto',
    paddingTop: 6,
    fontSize: 8,
    color: '#444',
    textAlign: 'center' as const,
    fontStyle: 'italic',
  },
};
