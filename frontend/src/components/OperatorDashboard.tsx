// MANTIS Operator Dashboard — Main Layout (holographic theme)
import React from 'react';
import { useOperatorPolling } from '../hooks/useOperatorPolling';
import { useOperatorStore } from '../store/operatorStore';
import { OperatorHeader } from './OperatorHeader';
import { MarketStatePanel } from './MarketStatePanel';
import { SPELayerSurvival } from './SPELayerSurvival';
import { ShortStressPanel } from './ShortStressPanel';
import { OperatorMetrics } from './OperatorMetrics';
import { ObservationLoggerPanel } from './ObservationLoggerPanel';
import { SPECharts } from './SPECharts';
import { EventEnginePanel } from './EventEnginePanel';

export const OperatorDashboard: React.FC = () => {
  useOperatorPolling(3000);

  const status = useOperatorStore(s => s.status);
  const connected = useOperatorStore(s => s.connected);
  const error = useOperatorStore(s => s.error);

  return (
    <div style={S.container}>
      <OperatorHeader />

      {!connected && (
        <div style={S.offlineBanner}>
          <span style={S.offlineDot}>●</span>
          <span style={S.offlineText}>BACKEND OFFLINE</span>
          <span style={S.offlineReason}>{error || 'Cannot reach localhost:8000'}</span>
          <span style={S.offlineHint}>Start MANTIS: cd backend && python main.py</span>
        </div>
      )}

      {connected && status && (
        <div style={S.grid}>
          <div style={S.row}>
            <div style={S.cellThird}><MarketStatePanel /></div>
            <div style={S.cellThird}><ShortStressPanel /></div>
            <div style={S.cellThird}><OperatorMetrics /></div>
          </div>
          <div style={S.row}>
            <div style={S.cellFull}><SPELayerSurvival /></div>
          </div>
          <div style={S.row}>
            <div style={S.cellHalf}><SPECharts /></div>
            <div style={S.cellQuarter}><EventEnginePanel /></div>
            <div style={S.cellQuarter}><ObservationLoggerPanel /></div>
          </div>
        </div>
      )}

      {connected && !status && (
        <div style={S.loading}>
          <span className="animate-pulse-glow" style={{ color: '#39ff88', fontSize: 18 }}>◆</span>
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
    background: '#05070b',
    overflow: 'hidden',
    fontFamily: "'JetBrains Mono', 'SF Mono', 'Cascadia Code', monospace",
  },
  offlineBanner: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 16px',
    background: 'rgba(255, 95, 95, 0.06)',
    borderBottom: '1px solid rgba(255, 95, 95, 0.25)',
    fontSize: 11,
    fontFamily: "'JetBrains Mono', monospace",
  },
  offlineDot: { color: '#ff5f5f', fontSize: 12, animation: 'pulse-glow 2s infinite' },
  offlineText: { color: '#ff5f5f', fontWeight: 700, letterSpacing: 1 },
  offlineReason: { color: '#8a6a6a', fontSize: 10 },
  offlineHint: { marginLeft: 'auto', color: '#5a8a70', fontSize: 10 },
  grid: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    padding: '4px',
    overflow: 'auto',
    minHeight: 0,
  },
  row: { display: 'flex', gap: 2, minHeight: 0 },
  cellThird: { flex: 1, minWidth: 0, display: 'flex' },
  cellHalf: { flex: 2, minWidth: 0, display: 'flex' },
  cellQuarter: { flex: 1, minWidth: 0, display: 'flex' },
  cellFull: { flex: 1, minWidth: 0, display: 'flex' },
  loading: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
    color: '#5a8a70',
    fontSize: 12,
  },
};

export default OperatorDashboard;
