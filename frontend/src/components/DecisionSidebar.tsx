// MANTIS — Decision Sidebar
// Right-side operator column: Decision + Interpretation + Checklist + Why Blocked
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { DecisionBanner } from './DecisionBanner';
import { InterpretationPanel } from './InterpretationPanel';
import { WhyBlockedPanel } from './WhyBlockedPanel';
import { ShortStressPanel } from './ShortStressPanel';
import { L3DiagnosticPanel } from './L3DiagnosticPanel';
import { T } from '../styles/operatorTheme';

export const DecisionSidebar: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const connected = useOperatorStore(s => s.connected);

  return (
    <div style={S.sidebar}>
      <DecisionBanner />
      <InterpretationPanel />
      <L3DiagnosticPanel />
      <ShortStressPanel />
      <WhyBlockedPanel />

      {/* Simulation mode footer */}
      <div style={S.simFooter}>
        <div style={S.simRow}>
          <span style={S.simDot}>●</span>
          <span style={S.simLabel}>LIVE OBSERVATION</span>
        </div>
        <div style={S.simRow}>
          <span style={S.simDot}>●</span>
          <span style={S.simLabel}>EXECUTION DISABLED</span>
        </div>
        <div style={S.simRow}>
          <span style={S.simDot}>●</span>
          <span style={S.simLabel}>PAPER SIMULATION</span>
        </div>
      </div>
    </div>
  );
};

const S: Record<string, React.CSSProperties> = {
  sidebar: {
    width: 320,
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: 3,
    overflow: 'auto',
    background: T.bg.surface,
    borderLeft: `1px solid ${T.border.mid}`,
    padding: '3px',
  },
  simFooter: {
    marginTop: 'auto',
    padding: '6px 8px',
    background: 'rgba(240, 208, 96, 0.04)',
    border: `1px solid rgba(240, 208, 96, 0.15)`,
    borderRadius: 4,
    display: 'flex',
    flexDirection: 'column',
    gap: 3,
  },
  simRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  simDot: {
    color: T.accent.gold,
    fontSize: 6,
    textShadow: `0 0 4px rgba(240, 208, 96, 0.3)`,
  },
  simLabel: {
    fontSize: 7,
    color: T.accent.gold,
    letterSpacing: 1.5,
    fontWeight: 700,
  },
};
