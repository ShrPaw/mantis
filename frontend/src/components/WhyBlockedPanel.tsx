// MANTIS Operator Dashboard — "Why Blocked" Panel
// Translates SPE layer status into plain operator language
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

interface BlockReason {
  layer: string;
  layerName: string;
  message: string;
  detail: string;
}

const LAYER_LANG: Record<string, { name: string; failMsg: string; detail: string }> = {
  L1_context_gate: {
    name: 'L1 — Context Gate',
    failMsg: 'No structural pressure context',
    detail: 'Market state is IDLE — waiting for CASCADE or UNWIND',
  },
  L2_pressure: {
    name: 'L2 — Pressure',
    failMsg: 'No positioning pressure',
    detail: 'Crowd imbalance not detected',
  },
  L3_displacement: {
    name: 'L3 — Displacement',
    failMsg: 'No displacement',
    detail: 'No forced directional move confirmed',
  },
  L4_sweep: {
    name: 'L4 — Sweep',
    failMsg: 'No sweep',
    detail: 'No structural liquidity sweep detected',
  },
  L5_trap: {
    name: 'L5 — Trap',
    failMsg: 'No trap/rejection',
    detail: 'No trap confirmation at key level',
  },
  L6_execution_filter: {
    name: 'L6 — Execution',
    failMsg: 'Execution quality not acceptable',
    detail: 'Spread, slippage, or fill quality below threshold',
  },
  L7_entry_zone: {
    name: 'L7 — Entry Zone',
    failMsg: 'No valid entry zone',
    detail: 'No limit placement zone identified',
  },
  L8_exit_model: {
    name: 'L8 — Exit/RR',
    failMsg: 'Exit/RR model rejected',
    detail: 'Risk/reward ratio insufficient',
  },
  confidence_gate: {
    name: 'Confidence Gate',
    failMsg: 'Below confidence threshold',
    detail: 'Composite confidence score too low',
  },
};

const LAYER_ORDER = [
  'L1_context_gate', 'L2_pressure', 'L3_displacement', 'L4_sweep',
  'L5_trap', 'L6_execution_filter', 'L7_entry_zone', 'L8_exit_model', 'confidence_gate',
];

function getBlockReasons(lc: Record<string, { pass: number; fail: number; not_evaluated: number }>, raw: number): BlockReason[] {
  const reasons: BlockReason[] = [];

  if (raw === 0) {
    reasons.push({
      layer: 'L1_context_gate',
      layerName: 'L1 — Context Gate',
      message: 'No structural pressure context',
      detail: 'Market state is IDLE — waiting for CASCADE or UNWIND',
    });
    return reasons;
  }

  for (const key of LAYER_ORDER) {
    const c = lc[key];
    if (!c) continue;
    const lang = LAYER_LANG[key];
    if (!lang) continue;

    if (c.fail > 0 && c.pass === 0) {
      reasons.push({
        layer: key,
        layerName: lang.name,
        message: lang.failMsg,
        detail: lang.detail,
      });
    }
  }

  // If no specific failures but still blocked
  if (reasons.length === 0) {
    reasons.push({
      layer: 'unknown',
      layerName: 'System',
      message: 'Waiting for structural conditions',
      detail: 'No active pressure context detected',
    });
  }

  return reasons;
}

export const WhyBlockedPanel: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const spe = status?.spe;
  const lc = spe?.layer_counts ?? {};
  const raw = spe?.raw_evaluations ?? 0;
  const reasons = getBlockReasons(lc, raw);

  return (
    <div style={S.panel}>
      <div style={S.title}>WHY BLOCKED</div>
      <div style={S.list}>
        {reasons.map((r, i) => (
          <div key={r.layer} style={S.row}>
            <div style={S.rowLeft}>
              <span style={S.blockIcon}>✗</span>
              <span style={S.layerName}>{r.layerName}</span>
            </div>
            <div style={S.rowRight}>
              <span style={S.message}>{r.message}</span>
              <span style={S.detail}>{r.detail}</span>
            </div>
          </div>
        ))}
      </div>
      {raw > 0 && (
        <div style={S.evalSummary}>
          {raw.toLocaleString()} evaluations performed — {reasons.length} layer(s) blocking
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
    padding: '10px 12px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  title: {
    fontSize: 9,
    fontWeight: 700,
    color: T.green.primary,
    letterSpacing: 2,
    marginBottom: 8,
    textShadow: `0 0 8px ${T.green.glow}`,
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    flex: 1,
    overflow: 'auto',
  },
  row: {
    display: 'flex',
    gap: 10,
    padding: '6px 8px',
    background: 'rgba(255,95,95,0.04)',
    border: `1px solid rgba(255,95,95,0.12)`,
    borderRadius: 4,
  },
  rowLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    flexShrink: 0,
    minWidth: 120,
  },
  blockIcon: {
    color: T.status.danger,
    fontSize: 12,
    fontWeight: 700,
    textShadow: `0 0 6px rgba(255,95,95,0.3)`,
  },
  layerName: {
    fontSize: 9,
    fontWeight: 700,
    color: T.status.danger,
    letterSpacing: 0.5,
  },
  rowRight: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    minWidth: 0,
  },
  message: {
    fontSize: 10,
    color: T.text.main,
    fontWeight: 600,
  },
  detail: {
    fontSize: 9,
    color: T.text.dim,
    lineHeight: 1.3,
  },
  evalSummary: {
    marginTop: 6,
    paddingTop: 6,
    borderTop: `1px solid ${T.border.dim}`,
    fontSize: 8,
    color: T.text.muted,
    textAlign: 'center',
    letterSpacing: 0.5,
  },
};
