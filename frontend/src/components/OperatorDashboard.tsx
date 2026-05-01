// MANTIS Operator Dashboard — Main Layout
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
          <span>BACKEND OFFLINE — {error || 'Cannot reach localhost:8000'}</span>
          <span style={S.offlineHint}>Start MANTIS: cd backend && python main.py</span>
        </div>
      )}

      {connected && status && (
        <div style={S.grid}>
          {/* Row 1: Market State + Short Stress */}
          <div style={S.row}>
            <div style={S.cellThird}>
              <MarketStatePanel />
            </div>
            <div style={S.cellThird}>
              <ShortStressPanel />
            </div>
            <div style={S.cellThird}>
              <OperatorMetrics />
            </div>
          </div>

          {/* Row 2: Layer Survival (full width) */}
          <div style={S.row}>
            <div style={S.cellFull}>
              <SPELayerSurvival />
            </div>
          </div>

          {/* Row 3: Charts + Event Engine + Observation Logger */}
          <div style={S.row}>
            <div style={S.cellHalf}>
              <SPECharts />
            </div>
            <div style={S.cellQuarter}>
              <EventEnginePanel />
            </div>
            <div style={S.cellQuarter}>
              <ObservationLoggerPanel />
            </div>
          </div>
        </div>
      )}

      {connected && !status && (
        <div style={S.loading}>Loading operator data...</div>
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
    background: '#08080c',
    overflow: 'hidden',
    fontFamily: "'JetBrains Mono', 'SF Mono', 'Cascadia Code', monospace",
  },
  offlineBanner: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '10px 20px',
    background: 'rgba(239, 83, 80, 0.08)',
    borderBottom: '1px solid rgba(239, 83, 80, 0.3)',
    color: '#ef5350',
    fontSize: 12,
    fontFamily: "'JetBrains Mono', monospace",
  },
  offlineDot: {
    color: '#ef5350',
    fontSize: 14,
    animation: 'pulse 2s infinite',
  },
  offlineHint: {
    marginLeft: 'auto',
    color: '#666',
    fontSize: 11,
  },
  grid: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: 1,
    background: '#111',
    overflow: 'auto',
    padding: '6px',
  },
  row: {
    display: 'flex',
    gap: 1,
    minHeight: 0,
  },
  cellThird: {
    flex: 1,
    minWidth: 0,
  },
  cellHalf: {
    flex: 2,
    minWidth: 0,
  },
  cellQuarter: {
    flex: 1,
    minWidth: 0,
  },
  cellFull: {
    flex: 1,
    minWidth: 0,
  },
  loading: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#555',
    fontSize: 13,
    fontFamily: "'JetBrains Mono', monospace",
  },
};

export default OperatorDashboard;
