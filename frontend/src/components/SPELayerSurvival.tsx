// MANTIS Operator Dashboard — SPE Layer Survival (holographic theme)
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

const LAYER_ORDER = [
  { key: 'L1_context_gate', name: 'L1 Context', desc: 'CASCADE/UNWIND gate' },
  { key: 'L2_pressure', name: 'L2 Pressure', desc: 'Crowd imbalance' },
  { key: 'L3_displacement', name: 'L3 Displace', desc: 'Forced move' },
  { key: 'L4_sweep', name: 'L4 Sweep', desc: 'Structural sweep' },
  { key: 'L5_trap', name: 'L5 Trap', desc: 'Trap confirm' },
  { key: 'L6_execution_filter', name: 'L6 Exec', desc: 'Quality gate' },
  { key: 'L7_entry_zone', name: 'L7 Entry', desc: 'Limit placement' },
  { key: 'L8_exit_model', name: 'L8 Exit', desc: 'TP/SL levels' },
  { key: 'confidence_gate', name: 'Confidence', desc: 'Min threshold' },
];

function getLayerStyle(counts: { pass: number; fail: number; not_evaluated: number }, raw: number) {
  if (raw === 0) return { status: 'NO DATA', color: T.text.muted, bg: T.bg.card };
  const { pass, fail } = counts;
  if (pass > 0 && fail === 0) return { status: 'PASS', color: T.green.primary, bg: 'rgba(57,255,136,0.06)' };
  if (fail > 0 && pass === 0) return { status: 'FAIL', color: T.status.danger, bg: 'rgba(255,95,95,0.06)' };
  if (pass === 0 && fail === 0) return { status: 'NOT EVAL', color: T.text.muted, bg: T.bg.card };
  return { status: 'MIXED', color: T.status.warning, bg: 'rgba(255,204,102,0.06)' };
}

export const SPELayerSurvival: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const spe = status?.spe;
  const lc = spe?.layer_counts ?? {};
  const raw = spe?.raw_evaluations ?? 0;
  const accountingValid = spe?.accounting_valid ?? true;

  return (
    <div style={S.panel}>
      <div style={S.header}>
        <span style={S.title}>SPE LAYER SURVIVAL</span>
        <span style={S.stats}>
          Evaluated: <span style={{ color: T.text.main }}>{raw.toLocaleString()}</span>
          {' · '}
          Full 8L: <span style={{ color: spe?.full_8_layer_passes ? T.green.primary : T.text.muted }}>{spe?.full_8_layer_passes ?? 0}</span>
          {' · '}
          Emitted: <span style={{ color: spe?.emitted_events ? T.green.primary : T.text.muted }}>{spe?.emitted_events ?? 0}</span>
        </span>
      </div>

      {!accountingValid && (
        <div style={S.criticalWarn}>
          ⚠ ACCOUNTING INVARIANT VIOLATION
        </div>
      )}

      <div style={S.layerGrid}>
        {LAYER_ORDER.map(layer => {
          const counts = lc[layer.key] ?? { pass: 0, fail: 0, not_evaluated: 0 };
          const { status: lStatus, color, bg } = getLayerStyle(counts, raw);
          const evaluated = counts.pass + counts.fail;
          const passRate = evaluated > 0 ? (counts.pass / evaluated * 100) : 0;
          const inv = counts.pass + counts.fail + counts.not_evaluated;

          return (
            <div key={layer.key} style={{ ...S.layerCard, background: bg, borderColor: color + '25' }}>
              <div style={S.layerTop}>
                <span style={{ color, fontWeight: 700, fontSize: 9, textShadow: `0 0 6px ${color}30` }}>{layer.name}</span>
                <span style={{ color, fontSize: 7, fontWeight: 700, letterSpacing: 1 }}>{lStatus}</span>
              </div>
              <div style={{ color: T.text.muted, fontSize: 7, marginBottom: 3 }}>{layer.desc}</div>
              <div style={S.layerStats}>
                <span style={{ color: T.green.primary }}>{counts.pass}✓</span>
                <span style={{ color: T.status.danger }}>{counts.fail}✗</span>
                <span style={{ color: T.text.muted }}>{counts.not_evaluated}⊘</span>
                <span style={{ color: T.text.dim, marginLeft: 'auto' }}>{evaluated > 0 ? `${passRate.toFixed(0)}%` : '—'}</span>
              </div>
              <div style={S.invBar}>
                <div style={{
                  height: '100%', borderRadius: 1,
                  width: raw > 0 ? `${(inv / raw * 100)}%` : '0%',
                  background: inv === raw ? T.green.muted : 'rgba(255,95,95,0.3)',
                  transition: 'width 0.3s',
                }} />
              </div>
              <div style={{ fontSize: 7, color: T.text.faint, textAlign: 'center', marginTop: 2 }}>{raw > 0 ? `${inv}/${raw}` : '—'}</div>
            </div>
          );
        })}
      </div>

      {raw === 0 && (
        <div style={S.emptyNotice}>
          <span style={{ color: T.green.primary }}>◆</span> No SPE evaluations yet. Waiting for live trade data.
        </div>
      )}
    </div>
  );
};

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: `linear-gradient(180deg, ${T.bg.panel} 0%, ${T.bg.surface} 100%)`,
    border: `1px solid ${T.border.mid}`,
    borderRadius: 6,
    padding: '8px 10px',
    width: '100%',
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  title: { fontSize: 9, fontWeight: 700, color: T.green.primary, letterSpacing: 2, textShadow: `0 0 8px ${T.green.glow}` },
  stats: { fontSize: 8, color: T.text.dim },
  criticalWarn: {
    padding: '5px 8px',
    background: 'rgba(255,95,95,0.1)',
    border: `1px solid rgba(255,95,95,0.35)`,
    borderRadius: 4,
    color: T.status.danger,
    fontSize: 9,
    fontWeight: 700,
    marginBottom: 6,
    letterSpacing: 1,
  },
  layerGrid: { display: 'grid', gridTemplateColumns: 'repeat(9, 1fr)', gap: 3 },
  layerCard: {
    border: '1px solid',
    borderRadius: 5,
    padding: '5px 6px',
    minHeight: 72,
    display: 'flex',
    flexDirection: 'column' as const,
  },
  layerTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 1 },
  layerStats: { display: 'flex', gap: 4, fontSize: 8, marginTop: 'auto' },
  invBar: { height: 2, background: T.border.dim, borderRadius: 1, marginTop: 3, overflow: 'hidden' },
  emptyNotice: { textAlign: 'center', color: T.text.dim, fontSize: 10, padding: 10, fontStyle: 'italic' },
};
