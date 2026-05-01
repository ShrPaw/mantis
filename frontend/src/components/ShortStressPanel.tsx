// MANTIS Operator Dashboard — SHORT_STRESS Panel (holographic theme)
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

function analyzeBlockReason(lc: Record<string, { pass: number; fail: number; not_evaluated: number }>): string {
  const order = ['L1_context_gate','L2_pressure','L3_displacement','L4_sweep','L5_trap','L6_execution_filter','L7_entry_zone','L8_exit_model','confidence_gate'];
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
  for (const key of order) {
    const c = lc[key];
    if (c && c.fail > 0 && c.pass === 0) return names[key] ?? key;
  }
  if (lc['L1_context_gate']?.not_evaluated > 0) return 'L1 blocked — market is IDLE';
  return 'No evaluations performed';
}

export const ShortStressPanel: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const spe = status?.spe;
  const lc = spe?.layer_counts ?? {};
  const raw = spe?.raw_evaluations ?? 0;
  const currentState = spe?.current_state ?? 'IDLE';
  const emitted = spe?.emitted_events ?? 0;
  const full8 = spe?.full_8_layer_passes ?? 0;
  const candidateActive = full8 > 0 && (currentState === 'CASCADE' || currentState === 'UNWIND');
  const blockReason = analyzeBlockReason(lc);
  const freq = status?.market?.trade_frequency ?? 0;
  const highVolume = freq > 3;
  const highVolatility = currentState === 'CASCADE' || currentState === 'UNWIND';

  return (
    <div style={S.panel}>
      <div style={S.title}>SPE_SHORT_STRESS CANDIDATE</div>

      <div style={{ marginBottom: 8 }}>
        <span style={{
          ...S.candidateBadge,
          background: candidateActive ? 'rgba(57,255,136,0.12)' : 'rgba(90,138,112,0.06)',
          color: candidateActive ? T.green.primary : T.text.muted,
          borderColor: candidateActive ? T.green.primary + '40' : T.border.dim,
          textShadow: candidateActive ? `0 0 10px ${T.green.glow}` : 'none',
        }}>
          {candidateActive ? '● CANDIDATE ACTIVE' : '○ NO CANDIDATE'}
        </span>
      </div>

      <div style={S.grid}>
        <Row label="Direction" value="SHORT ONLY" color={T.status.danger} />
        <Row label="Crowd Direction" value={candidateActive ? 'LONG_CROWD' : '—'} color={candidateActive ? T.status.warning : T.text.muted} />
        <Row label="Mantis State" value={currentState} color={currentState === 'IDLE' ? T.text.muted : T.status.warning} />
        <Row label="High Volume" value={highVolume ? 'YES' : 'NO'} color={highVolume ? T.green.primary : T.text.muted} />
        <Row label="High Volatility" value={highVolatility ? 'YES' : 'NO'} color={highVolatility ? T.green.primary : T.text.muted} />
        <Row label="Full 8-Layer Pass" value={full8 > 0 ? `YES (${full8})` : 'NO'} color={full8 > 0 ? T.green.primary : T.status.danger} />
        <Row label="Total Candidates" value={emitted.toString()} color={emitted > 0 ? T.green.primary : T.text.muted} />
      </div>

      <div style={S.divider} />

      <div style={S.blockBox}>
        <span style={{ color: T.text.muted, fontSize: 8, letterSpacing: 1 }}>BLOCK REASON</span>
        <span style={{ color: T.text.mid, fontSize: 10 }}>{raw > 0 ? blockReason : 'No evaluations performed'}</span>
      </div>

      {!candidateActive && raw > 0 && (
        <div style={S.silentBanner}>
          <span style={{ color: T.green.primary, marginRight: 6 }}>◆</span>
          No valid SHORT_STRESS context. System intentionally silent.
        </div>
      )}
      {raw === 0 && (
        <div style={S.silentBanner}>
          <span style={{ color: T.green.primary, marginRight: 6 }}>◆</span>
          System silent by design. No valid high-pressure context.
        </div>
      )}

      <div style={{ marginTop: 'auto', paddingTop: 6, fontSize: 7, color: T.text.faint, textAlign: 'center', fontStyle: 'italic' }}>
        ⚠ Observation-only — no execution — context detection for validation
      </div>
    </div>
  );
};

const Row: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10 }}>
    <span style={{ color: T.text.dim }}>{label}</span>
    <span style={{ color, fontWeight: 600, textShadow: `0 0 4px ${color}20` }}>{value}</span>
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
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  title: { fontSize: 9, fontWeight: 700, color: T.green.primary, letterSpacing: 2, marginBottom: 8, textShadow: `0 0 8px ${T.green.glow}` },
  candidateBadge: {
    display: 'inline-block',
    fontSize: 11,
    fontWeight: 700,
    padding: '4px 12px',
    borderRadius: 4,
    border: '1px solid',
    letterSpacing: 1,
  },
  grid: { display: 'flex', flexDirection: 'column' as const, gap: 4 },
  divider: { height: 1, background: T.border.dim, margin: '8px 0' },
  blockBox: {
    padding: '6px 8px',
    background: T.bg.card,
    borderRadius: 4,
    border: `1px solid ${T.border.dim}`,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 2,
  },
  silentBanner: {
    marginTop: 6,
    padding: '6px 10px',
    background: T.green.glow,
    border: `1px solid ${T.border.bright}`,
    borderRadius: 4,
    fontSize: 10,
    color: T.green.primary,
    textAlign: 'center' as const,
    textShadow: `0 0 6px ${T.green.glow}`,
  },
};
