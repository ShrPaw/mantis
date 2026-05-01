// MANTIS — Operator Dashboard (Visual Cockpit Redesign)
// Layout:
//   Top: Simulation Status Bar (compact)
//   Center: Main Chart (large) + Decision Sidebar (right)
//   Bottom: Event Tape | Pressure Bubbles | Pressure Heatmap | Diagnostics
import React from 'react';
import { useOperatorPolling } from '../hooks/useOperatorPolling';
import { useOperatorStore } from '../store/operatorStore';
import { SimulationStatusBar } from './SimulationStatusBar';
import { MainPriceChart } from './MainPriceChart';
import { DecisionSidebar } from './DecisionSidebar';
import { EventTape } from './EventTape';
import { PressureBubbleMap } from './PressureBubbleMap';
import { PressureHeatmap } from './PressureHeatmap';
import { CompactDiagnostics } from './CompactDiagnostics';
import { T } from '../styles/operatorTheme';

export const OperatorDashboard: React.FC = () => {
  useOperatorPolling(3000);

  const status = useOperatorStore(s => s.status);
  const connected = useOperatorStore(s => s.connected);
  const error = useOperatorStore(s => s.error);

  return (
    <div style={S.container}>
      {/* Top: Simulation status bar */}
      <SimulationStatusBar />

      {/* Offline banner */}
      {!connected && (
        <div style={S.offlineBanner}>
          <span style={S.offlineDot}>●</span>
          <span style={S.offlineText}>SYSTEM OFFLINE</span>
          <span style={S.offlineReason}>{error || 'Cannot reach localhost:8000'}</span>
          <span style={S.offlineHint}>Start MANTIS: cd backend && python main.py</span>
        </div>
      )}

      {/* Main cockpit area */}
      {connected && status && (
        <div style={S.cockpit}>
          {/* Center: Chart + Right sidebar */}
          <div style={S.mainArea}>
            <div style={S.chartArea}>
              <MainPriceChart />
            </div>
            <DecisionSidebar />
          </div>

          {/* Bottom: Flow/Event panels */}
          <div style={S.bottomRow}>
            <div style={S.bottomPanel}><EventTape /></div>
            <div style={S.bottomPanel}><PressureBubbleMap /></div>
            <div style={S.bottomPanel}><PressureHeatmap /></div>
            <div style={S.bottomPanel}><CompactDiagnostics /></div>
          </div>
        </div>
      )}

      {/* Loading state */}
      {connected && !status && (
        <div style={S.loading}>
          <span className="animate-pulse-glow" style={{ color: T.green.primary, fontSize: 18 }}>◆</span>
          <span>Initializing operator data feed...</span>
        </div>
      )}
    </div>
  );
};

const S: Record<string, React.CSSProperties> = {
  container: {
    width: '100vw',
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    background: T.bg.base,
    overflow: 'hidden',
    fontFamily: "'JetBrains Mono', 'SF Mono', 'Cascadia Code', monospace",
  },
  offlineBanner: {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '6px 14px',
    background: 'rgba(255, 95, 95, 0.06)',
    borderBottom: '1px solid rgba(255, 95, 95, 0.25)',
    fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
  },
  offlineDot: { color: '#ff5f5f', fontSize: 10, animation: 'pulse-glow 2s infinite' },
  offlineText: { color: '#ff5f5f', fontWeight: 700, letterSpacing: 1 },
  offlineReason: { color: '#8a6a6a', fontSize: 9 },
  offlineHint: { marginLeft: 'auto', color: '#5a8a70', fontSize: 9 },
  cockpit: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    minHeight: 0,
  },
  mainArea: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden',
    minHeight: 0,
  },
  chartArea: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    background: T.bg.base,
  },
  bottomRow: {
    display: 'flex',
    gap: 3,
    padding: '3px',
    height: 180,
    flexShrink: 0,
    borderTop: `1px solid ${T.border.mid}`,
    background: T.bg.surface,
  },
  bottomPanel: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
  },
  loading: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    color: T.text.dim,
    fontSize: 12,
  },
};

export default OperatorDashboard;
