// MANTIS Operator Dashboard — SHORT_STRESS Checklist (redesigned)
// Large checklist rows with green checkmarks, red blocks, gray for not evaluated
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

interface CheckItem {
  label: string;
  value: string;
  status: 'pass' | 'fail' | 'neutral' | 'note';
}

function getChecklistItems(spe: any, market: any): CheckItem[] {
  const lc = spe?.layer_counts ?? {};
  const raw = spe?.raw_evaluations ?? 0;
  const currentState = spe?.current_state ?? 'IDLE';
  const full8 = spe?.full_8_layer_passes ?? 0;
  const freq = market?.trade_frequency ?? 0;
  const highVolume = freq > 3;
  const highVolatility = currentState === 'CASCADE' || currentState === 'UNWIND';
  const candidateActive = full8 > 0 && (currentState === 'CASCADE' || currentState === 'UNWIND');

  return [
    {
      label: 'Direction allowed',
      value: 'SHORT ONLY',
      status: 'note',
    },
    {
      label: 'Market state',
      value: currentState === 'IDLE' ? 'IDLE' : `${currentState} required`,
      status: currentState === 'CASCADE' || currentState === 'UNWIND' ? 'pass' : 'fail',
    },
    {
      label: 'High volume',
      value: highVolume ? 'YES' : 'NO',
      status: highVolume ? 'pass' : 'fail',
    },
    {
      label: 'High volatility',
      value: highVolatility ? 'YES' : 'NO',
      status: highVolatility ? 'pass' : 'fail',
    },
    {
      label: 'Full 8-layer pass',
      value: full8 > 0 ? `YES (${full8})` : 'NO',
      status: full8 > 0 ? 'pass' : 'fail',
    },
    {
      label: 'Observation-only',
      value: 'YES',
      status: 'note',
    },
    {
      label: 'Execution disabled',
      value: 'YES',
      status: 'note',
    },
  ];
}

function StatusIcon({ status }: { status: CheckItem['status'] }) {
  if (status === 'pass') {
    return (
      <span style={{
        color: T.green.primary,
        fontSize: 14,
        fontWeight: 700,
        textShadow: `0 0 8px ${T.green.glowStrong}`,
        lineHeight: 1,
      }}>✓</span>
    );
  }
  if (status === 'fail') {
    return (
      <span style={{
        color: T.status.danger,
        fontSize: 14,
        fontWeight: 700,
        textShadow: `0 0 6px rgba(255,95,95,0.3)`,
        lineHeight: 1,
      }}>✗</span>
    );
  }
  if (status === 'note') {
    return (
      <span style={{
        color: T.accent.gold,
        fontSize: 11,
        fontWeight: 700,
        lineHeight: 1,
      }}>◆</span>
    );
  }
  return (
    <span style={{
      color: T.text.muted,
      fontSize: 12,
      lineHeight: 1,
    }}>—</span>
  );
}

function getStatusColor(status: CheckItem['status']): string {
  if (status === 'pass') return T.green.primary;
  if (status === 'fail') return T.status.danger;
  if (status === 'note') return T.accent.gold;
  return T.text.muted;
}

export const ShortStressPanel: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const spe = status?.spe;
  const market = status?.market;
  const items = getChecklistItems(spe, market);
  const raw = spe?.raw_evaluations ?? 0;
  const full8 = spe?.full_8_layer_passes ?? 0;
  const currentState = spe?.current_state ?? 'IDLE';
  const candidateActive = full8 > 0 && (currentState === 'CASCADE' || currentState === 'UNWIND');

  return (
    <div style={S.panel}>
      <div style={S.header}>
        <span style={S.title}>SHORT_STRESS CHECKLIST</span>
        <span style={{
          ...S.candidateBadge,
          background: candidateActive ? 'rgba(57,255,136,0.12)' : 'rgba(90,138,112,0.06)',
          color: candidateActive ? T.green.primary : T.text.muted,
          borderColor: candidateActive ? T.green.primary + '40' : T.border.dim,
          textShadow: candidateActive ? `0 0 10px ${T.green.glow}` : 'none',
        }}>
          {candidateActive ? '● CANDIDATE' : '○ NO CANDIDATE'}
        </span>
      </div>

      <div style={S.checklist}>
        {items.map((item, i) => (
          <div key={i} style={{
            ...S.checkRow,
            borderLeftColor: getStatusColor(item.status) + '40',
          }}>
            <StatusIcon status={item.status} />
            <span style={S.checkLabel}>{item.label}</span>
            <span style={{
              ...S.checkValue,
              color: getStatusColor(item.status),
              textShadow: item.status === 'pass' ? `0 0 6px ${T.green.glow}` : 'none',
            }}>
              {item.value}
            </span>
          </div>
        ))}
      </div>

      {raw === 0 && (
        <div style={S.silentBanner}>
          <span style={{ color: T.green.primary, marginRight: 6 }}>◆</span>
          0 SPE events — system silent by design.
        </div>
      )}

      {!candidateActive && raw > 0 && (
        <div style={S.silentBanner}>
          <span style={{ color: T.green.primary, marginRight: 6 }}>◆</span>
          No valid SHORT_STRESS context. System intentionally silent.
        </div>
      )}

      <div style={S.footer}>
        ⚠ Observation-only — no execution — context detection for validation
      </div>
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
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  title: {
    fontSize: 9,
    fontWeight: 700,
    color: T.green.primary,
    letterSpacing: 2,
    textShadow: `0 0 8px ${T.green.glow}`,
  },
  candidateBadge: {
    fontSize: 9,
    fontWeight: 700,
    padding: '2px 8px',
    borderRadius: 3,
    border: '1px solid',
    letterSpacing: 1,
  },
  checklist: {
    display: 'flex',
    flexDirection: 'column',
    gap: 3,
    flex: 1,
  },
  checkRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '5px 8px',
    background: T.bg.card,
    borderRadius: 4,
    borderLeft: '3px solid',
  },
  checkLabel: {
    fontSize: 10,
    color: T.text.dim,
    flex: 1,
  },
  checkValue: {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: 0.5,
    textAlign: 'right',
  },
  silentBanner: {
    marginTop: 6,
    padding: '5px 10px',
    background: T.green.glow,
    border: `1px solid ${T.border.bright}`,
    borderRadius: 4,
    fontSize: 10,
    color: T.green.primary,
    textAlign: 'center',
    textShadow: `0 0 6px ${T.green.glow}`,
  },
  footer: {
    marginTop: 'auto',
    paddingTop: 6,
    fontSize: 7,
    color: T.text.faint,
    textAlign: 'center',
    fontStyle: 'italic',
    letterSpacing: 0.3,
  },
};
