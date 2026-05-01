// MANTIS Operator Dashboard — Decision Banner
// Top-level decision state: what matters in 5 seconds
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

type DecisionState =
  | 'NO_VALID_CONTEXT'
  | 'OBSERVE_ONLY'
  | 'SHORT_STRESS_WATCH'
  | 'SHORT_STRESS_CANDIDATE'
  | 'SYSTEM_OFFLINE'
  | 'ACCOUNTING_ERROR';

interface DecisionInfo {
  state: DecisionState;
  label: string;
  color: string;
  glowColor: string;
  reason: string;
  action: string;
}

function deriveDecision(
  connected: boolean,
  spe: any,
  market: any,
  backend: any,
): DecisionInfo {
  if (!connected || !backend) {
    return {
      state: 'SYSTEM_OFFLINE',
      label: 'SYSTEM OFFLINE',
      color: T.status.danger,
      glowColor: 'rgba(255,95,95,0.2)',
      reason: 'Backend unreachable — no data feed',
      action: 'Check backend. Start: cd backend && python main.py',
    };
  }

  if (spe?.accounting_valid === false) {
    return {
      state: 'ACCOUNTING_ERROR',
      label: 'ACCOUNTING ERROR',
      color: T.status.danger,
      glowColor: 'rgba(255,95,95,0.2)',
      reason: 'SPE accounting invariant violation detected',
      action: 'Review accounting audit. Do not trust SPE outputs.',
    };
  }

  const lc = spe?.layer_counts ?? {};
  const raw = spe?.raw_evaluations ?? 0;
  const full8 = spe?.full_8_layer_passes ?? 0;
  const currentState = spe?.current_state ?? 'IDLE';
  const emitted = spe?.emitted_events ?? 0;
  const freq = market?.trade_frequency ?? 0;

  // Check if L1 is blocking
  const l1 = lc['L1_context_gate'];
  const l1Blocking = l1 && l1.fail > 0 && l1.pass === 0;

  // Candidate: full 8-layer pass + CASCADE/UNWIND
  if (full8 > 0 && (currentState === 'CASCADE' || currentState === 'UNWIND')) {
    return {
      state: 'SHORT_STRESS_CANDIDATE',
      label: 'SHORT_STRESS CANDIDATE',
      color: T.green.primary,
      glowColor: T.green.glowStrong,
      reason: `Full 8-layer pass in ${currentState} — ${emitted} candidate(s) emitted`,
      action: 'Review manually. Observation-only — no execution.',
    };
  }

  // Watch: evaluations running but no full pass yet
  if (raw > 0 && (currentState === 'CASCADE' || currentState === 'UNWIND')) {
    return {
      state: 'SHORT_STRESS_WATCH',
      label: 'SHORT_STRESS WATCH',
      color: T.status.warning,
      glowColor: 'rgba(255,204,102,0.15)',
      reason: `${currentState} detected — ${raw} evaluations — layers blocking`,
      action: 'Observe. Waiting for full 8-layer confirmation.',
    };
  }

  // Observe only: SPE active but market is idle
  if (spe?.enabled && currentState === 'IDLE' && !l1Blocking) {
    return {
      state: 'OBSERVE_ONLY',
      label: 'OBSERVE ONLY',
      color: T.accent.cyan,
      glowColor: 'rgba(0,229,200,0.12)',
      reason: 'SPE active — no structural pressure context',
      action: 'Observe only. Wait for CASCADE or UNWIND.',
    };
  }

  // No valid context: L1 blocking or idle
  return {
    state: 'NO_VALID_CONTEXT',
    label: 'NO VALID CONTEXT',
    color: T.text.dim,
    glowColor: 'rgba(90,138,112,0.08)',
    reason: l1Blocking
      ? 'L1 blocked — no CASCADE/UNWIND state'
      : currentState === 'IDLE'
        ? 'Market state is IDLE — waiting for structural pressure'
        : 'No valid structural pressure context',
    action: 'Observe only. Do not force trades.',
  };
}

export const DecisionBanner: React.FC = () => {
  const connected = useOperatorStore(s => s.connected);
  const status = useOperatorStore(s => s.status);
  const spe = status?.spe;
  const market = status?.market;
  const backend = status?.backend;

  const decision = deriveDecision(connected, spe, market, backend);

  return (
    <div style={{
      ...S.banner,
      borderColor: decision.color + '35',
      background: `linear-gradient(135deg, ${decision.glowColor} 0%, ${T.bg.panel} 40%, ${T.bg.surface} 100%)`,
    }}>
      <div style={S.leftSection}>
        <div style={S.statusRow}>
          <span style={{
            ...S.stateBadge,
            color: decision.color,
            borderColor: decision.color + '50',
            background: decision.color + '12',
            textShadow: `0 0 12px ${decision.color}40`,
          }}>
            {decision.label}
          </span>
        </div>
        <div style={S.reasonRow}>
          <span style={S.reasonLabel}>REASON</span>
          <span style={S.reasonText}>{decision.reason}</span>
        </div>
      </div>
      <div style={S.rightSection}>
        <div style={S.actionRow}>
          <span style={S.actionLabel}>ACTION</span>
          <span style={{ ...S.actionText, color: decision.color }}>{decision.action}</span>
        </div>
      </div>
    </div>
  );
};

const S: Record<string, React.CSSProperties> = {
  banner: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 16px',
    borderRadius: 6,
    border: '1px solid',
    flexShrink: 0,
    gap: 20,
    boxShadow: `0 2px 12px rgba(0,0,0,0.3)`,
  },
  leftSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    flex: 1,
    minWidth: 0,
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  stateBadge: {
    fontSize: 14,
    fontWeight: 700,
    padding: '4px 14px',
    borderRadius: 4,
    border: '1px solid',
    letterSpacing: 2,
    fontFamily: "'JetBrains Mono', monospace",
  },
  reasonRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  reasonLabel: {
    fontSize: 8,
    color: T.text.muted,
    letterSpacing: 1,
    fontWeight: 700,
    flexShrink: 0,
  },
  reasonText: {
    fontSize: 11,
    color: T.text.mid,
    lineHeight: 1.4,
  },
  rightSection: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: 4,
    flexShrink: 0,
  },
  actionRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  actionLabel: {
    fontSize: 8,
    color: T.text.muted,
    letterSpacing: 1,
    fontWeight: 700,
    flexShrink: 0,
  },
  actionText: {
    fontSize: 11,
    fontWeight: 600,
    lineHeight: 1.4,
  },
};
