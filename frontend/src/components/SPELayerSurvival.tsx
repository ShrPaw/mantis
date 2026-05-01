// MANTIS Operator Dashboard — SPE Layer Survival Panel
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';

const LAYER_ORDER = [
  { key: 'L1_context_gate', name: 'L1 Context Gate', desc: 'CASCADE/UNWIND state gate' },
  { key: 'L2_pressure', name: 'L2 Pressure', desc: 'Crowd positioning imbalance' },
  { key: 'L3_displacement', name: 'L3 Displacement', desc: 'Forced move detection' },
  { key: 'L4_sweep', name: 'L4 Sweep', desc: 'Structural sweep / CRT' },
  { key: 'L5_trap', name: 'L5 Trap', desc: 'Trap confirmation' },
  { key: 'L6_execution_filter', name: 'L6 Exec Filter', desc: 'Spread/depth quality gate' },
  { key: 'L7_entry_zone', name: 'L7 Entry Zone', desc: 'Passive limit placement' },
  { key: 'L8_exit_model', name: 'L8 Exit Model', desc: 'TP/SL levels' },
  { key: 'confidence_gate', name: 'Confidence', desc: 'Min confidence threshold' },
];

function getLayerStatus(counts: { pass: number; fail: number; not_evaluated: number }, raw: number): {
  status: string;
  color: string;
  bgColor: string;
} {
  if (raw === 0) return { status: 'NO DATA', color: '#444', bgColor: '#111' };
  const { pass, fail, not_evaluated } = counts;
  if (pass > 0 && fail === 0) return { status: 'PASS', color: '#26a69a', bgColor: 'rgba(38,166,154,0.1)' };
  if (fail > 0 && pass === 0) return { status: 'FAIL', color: '#ef5350', bgColor: 'rgba(239,83,80,0.1)' };
  if (not_evaluated > 0 && pass === 0 && fail === 0) return { status: 'NOT EVALUATED', color: '#555', bgColor: '#111' };
  if (pass > 0 && fail > 0) return { status: 'MIXED', color: '#ff9800', bgColor: 'rgba(255,152,0,0.1)' };
  return { status: '—', color: '#444', bgColor: '#111' };
}

export const SPELayerSurvival: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const spe = status?.spe;
  const layerCounts = spe?.layer_counts ?? {};
  const raw = spe?.raw_evaluations ?? 0;
  const accountingValid = spe?.accounting_valid ?? true;
  const accountingErrors = spe?.accounting_errors ?? [];

  return (
    <div style={S.panel}>
      <div style={S.header}>
        <span style={S.title}>SPE LAYER SURVIVAL</span>
        <span style={S.subtitle}>
          Raw evaluations: <span style={{ color: '#ccc' }}>{raw.toLocaleString()}</span>
          {' · '}
          Full 8-layer passes: <span style={{ color: spe?.full_8_layer_passes ? '#26a69a' : '#555' }}>{spe?.full_8_layer_passes ?? 0}</span>
          {' · '}
          Emitted: <span style={{ color: spe?.emitted_events ? '#f0b90b' : '#555' }}>{spe?.emitted_events ?? 0}</span>
        </span>
      </div>

      {!accountingValid && (
        <div style={S.criticalWarn}>
          ⚠ ACCOUNTING INVARIANT VIOLATION: {accountingErrors.join('; ')}
        </div>
      )}

      <div style={S.layerGrid}>
        {LAYER_ORDER.map(layer => {
          const counts = layerCounts[layer.key] ?? { pass: 0, fail: 0, not_evaluated: 0 };
          const { status: layerStatus, color, bgColor } = getLayerStatus(counts, raw);
          const evaluated = counts.pass + counts.fail;
          const passRate = evaluated > 0 ? (counts.pass / evaluated * 100) : 0;
          const invariant = counts.pass + counts.fail + counts.not_evaluated;

          return (
            <div key={layer.key} style={{ ...S.layerCard, background: bgColor, borderColor: color + '30' }}>
              <div style={S.layerTop}>
                <span style={{ ...S.layerName, color }}>{layer.name}</span>
                <span style={{ ...S.layerStatus, color }}>{layerStatus}</span>
              </div>
              <div style={S.layerDesc}>{layer.desc}</div>
              <div style={S.layerStats}>
                <span style={{ color: '#26a69a' }}>{counts.pass}✓</span>
                <span style={{ color: '#ef5350' }}>{counts.fail}✗</span>
                <span style={{ color: '#555' }}>{counts.not_evaluated}⊘</span>
                <span style={{ color: '#888', marginLeft: 'auto' }}>
                  {evaluated > 0 ? `${passRate.toFixed(0)}%` : '—'}
                </span>
              </div>
              <div style={S.invariantBar}>
                <div style={{
                  ...S.invariantFill,
                  width: raw > 0 ? `${(invariant / raw * 100)}%` : '0%',
                  background: invariant === raw ? '#26a69a30' : '#ef535040',
                }} />
              </div>
              <div style={S.invariantLabel}>
                {raw > 0 ? `${invariant}/${raw}` : '—'}
              </div>
            </div>
          );
        })}
      </div>

      {raw === 0 && (
        <div style={S.emptyNotice}>
          No SPE evaluations yet. Waiting for live trade data.
        </div>
      )}
    </div>
  );
};

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: '#0c0c14',
    border: '1px solid #1a1a2e',
    borderRadius: 6,
    padding: '10px 12px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  title: {
    fontSize: 10,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 2,
  },
  subtitle: {
    fontSize: 9,
    color: '#666',
    fontFamily: "'JetBrains Mono', monospace",
  },
  criticalWarn: {
    padding: '6px 10px',
    background: 'rgba(239, 83, 80, 0.12)',
    border: '1px solid rgba(239, 83, 80, 0.4)',
    borderRadius: 4,
    color: '#ef5350',
    fontSize: 10,
    fontWeight: 700,
    marginBottom: 8,
    letterSpacing: 1,
  },
  layerGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(9, 1fr)',
    gap: 4,
  },
  layerCard: {
    border: '1px solid',
    borderRadius: 5,
    padding: '6px 7px',
    minHeight: 80,
    display: 'flex',
    flexDirection: 'column' as const,
  },
  layerTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 2,
  },
  layerName: {
    fontSize: 9,
    fontWeight: 700,
    letterSpacing: 0.5,
  },
  layerStatus: {
    fontSize: 7,
    fontWeight: 700,
    letterSpacing: 1,
  },
  layerDesc: {
    fontSize: 7,
    color: '#555',
    marginBottom: 4,
    lineHeight: 1.3,
  },
  layerStats: {
    display: 'flex',
    gap: 5,
    fontSize: 9,
    fontFamily: "'JetBrains Mono', monospace",
    marginTop: 'auto',
  },
  invariantBar: {
    height: 2,
    background: '#1a1a2e',
    borderRadius: 1,
    marginTop: 4,
    overflow: 'hidden',
  },
  invariantFill: {
    height: '100%',
    borderRadius: 1,
    transition: 'width 0.3s ease',
  },
  invariantLabel: {
    fontSize: 7,
    color: '#444',
    textAlign: 'center' as const,
    marginTop: 2,
  },
  emptyNotice: {
    textAlign: 'center' as const,
    color: '#444',
    fontSize: 11,
    padding: 12,
    fontStyle: 'italic',
  },
};
