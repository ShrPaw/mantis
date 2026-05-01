// MANTIS Operator Dashboard — SPE Charts (Canvas-based mini charts)
import React, { useRef, useEffect, useCallback } from 'react';
import { useOperatorStore } from '../store/operatorStore';

// Simple canvas sparkline
function drawSparkline(
  ctx: CanvasRenderingContext2D,
  data: number[],
  width: number,
  height: number,
  color: string,
  fillColor?: string,
) {
  ctx.clearRect(0, 0, width, height);
  if (data.length < 2) return;

  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const step = width / (data.length - 1);

  ctx.beginPath();
  ctx.moveTo(0, height - ((data[0] - min) / range) * height);
  for (let i = 1; i < data.length; i++) {
    ctx.lineTo(i * step, height - ((data[i] - min) / range) * height);
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();

  if (fillColor) {
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();
  }
}

// Stacked bar chart for layer data
function drawStackedBar(
  ctx: CanvasRenderingContext2D,
  passData: number[],
  failData: number[],
  neData: number[],
  width: number,
  height: number,
) {
  ctx.clearRect(0, 0, width, height);
  if (passData.length < 1) return;

  const barW = Math.max(2, (width / passData.length) - 1);

  for (let i = 0; i < passData.length; i++) {
    const total = passData[i] + failData[i] + neData[i];
    if (total === 0) continue;

    const x = i * (barW + 1);
    let y = height;

    // Pass (green)
    const passH = (passData[i] / total) * height;
    ctx.fillStyle = 'rgba(38, 166, 154, 0.7)';
    ctx.fillRect(x, y - passH, barW, passH);
    y -= passH;

    // Fail (red)
    const failH = (failData[i] / total) * height;
    ctx.fillStyle = 'rgba(239, 83, 80, 0.7)';
    ctx.fillRect(x, y - failH, barW, failH);
    y -= failH;

    // Not evaluated (gray)
    const neH = (neData[i] / total) * height;
    ctx.fillStyle = 'rgba(80, 80, 80, 0.5)';
    ctx.fillRect(x, y - neH, barW, neH);
  }
}

const MiniChart: React.FC<{
  title: string;
  data: number[];
  color: string;
  fillColor?: string;
  suffix?: string;
  height?: number;
}> = ({ title, data, color, fillColor, suffix, height: h = 50 }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    drawSparkline(ctx, data, rect.width, rect.height, color, fillColor);
  }, [data, color, fillColor]);

  const latest = data.length > 0 ? data[data.length - 1] : 0;

  return (
    <div style={{ ...miniS.container, height: h + 30 }}>
      <div style={miniS.header}>
        <span style={miniS.title}>{title}</span>
        <span style={{ ...miniS.value, color }}>
          {latest.toLocaleString()}{suffix || ''}
        </span>
      </div>
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: `${h}px`, display: 'block' }}
      />
    </div>
  );
};

const miniS: Record<string, React.CSSProperties> = {
  container: {
    background: '#0a0a12',
    border: '1px solid #1a1a2e',
    borderRadius: 4,
    padding: '6px 8px',
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  title: {
    fontSize: 8,
    color: '#555',
    letterSpacing: 1,
    textTransform: 'uppercase' as const,
  },
  value: {
    fontSize: 11,
    fontWeight: 700,
    fontFamily: "'JetBrains Mono', monospace",
  },
};

export const SPECharts: React.FC = () => {
  const metricHistory = useOperatorStore(s => s.metricHistory);

  const evalsData = metricHistory.map(m => m.raw_evaluations);
  const emittedData = metricHistory.map(m => m.emitted_events);
  const full8Data = metricHistory.map(m => m.full_8_layer_passes);

  // Layer 1 pass/fail over time
  const l1PassData = metricHistory.map(m => m.layer_counts?.L1_context_gate?.pass ?? 0);
  const l1FailData = metricHistory.map(m => m.layer_counts?.L1_context_gate?.fail ?? 0);
  const l1NeData = metricHistory.map(m => m.layer_counts?.L1_context_gate?.not_evaluated ?? 0);

  // State distribution
  const stateCounts: Record<string, number> = {};
  metricHistory.forEach(m => {
    const s = m.current_state || 'IDLE';
    stateCounts[s] = (stateCounts[s] || 0) + 1;
  });

  return (
    <div style={S.panel}>
      <div style={S.title}>SPE METRICS OVER TIME</div>

      {metricHistory.length < 2 ? (
        <div style={S.empty}>
          Collecting data... ({metricHistory.length} samples)
          <br />
          <span style={{ fontSize: 9, color: '#444' }}>Charts appear after a few polling cycles</span>
        </div>
      ) : (
        <div style={S.chartGrid}>
          <MiniChart
            title="Raw Evaluations"
            data={evalsData}
            color="#2196f3"
            fillColor="rgba(33, 150, 243, 0.08)"
          />
          <MiniChart
            title="Events Emitted"
            data={emittedData}
            color="#f0b90b"
            fillColor="rgba(240, 185, 11, 0.08)"
          />
          <MiniChart
            title="Full 8-Layer Passes"
            data={full8Data}
            color="#26a69a"
            fillColor="rgba(38, 166, 154, 0.08)"
          />

          {/* State distribution */}
          <div style={S.stateCard}>
            <div style={miniS.title}>STATE DISTRIBUTION</div>
            <div style={S.stateGrid}>
              {Object.entries(stateCounts).sort((a, b) => b[1] - a[1]).map(([state, count]) => {
                const total = metricHistory.length || 1;
                const pct = (count / total * 100);
                const color = state === 'CASCADE' ? '#ef5350' : state === 'UNWIND' ? '#ff9800' : '#555';
                return (
                  <div key={state} style={S.stateRow}>
                    <span style={{ ...S.stateName, color }}>{state}</span>
                    <div style={S.stateBar}>
                      <div style={{ ...S.stateFill, width: `${pct}%`, background: color }} />
                    </div>
                    <span style={S.statePct}>{pct.toFixed(0)}%</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* L1 stacked chart */}
          <div style={{ ...miniS.container, height: 80 }}>
            <div style={miniS.header}>
              <span style={miniS.title}>L1 CONTEXT GATE</span>
              <span style={{ fontSize: 8, color: '#555' }}>
                <span style={{ color: '#26a69a' }}>■</span> pass{' '}
                <span style={{ color: '#ef5350' }}>■</span> fail{' '}
                <span style={{ color: '#555' }}>■</span> n/e
              </span>
            </div>
            <L1StackedBar passData={l1PassData} failData={l1FailData} neData={l1NeData} />
          </div>
        </div>
      )}
    </div>
  );
};

const L1StackedBar: React.FC<{ passData: number[]; failData: number[]; neData: number[] }> = ({ passData, failData, neData }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    drawStackedBar(ctx, passData, failData, neData, rect.width, rect.height);
  }, [passData, failData, neData]);

  return <canvas ref={canvasRef} style={{ width: '100%', height: '50px', display: 'block' }} />;
};

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: '#0c0c14',
    border: '1px solid #1a1a2e',
    borderRadius: 6,
    padding: '10px 12px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  title: {
    fontSize: 10,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 2,
    marginBottom: 8,
  },
  empty: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    color: '#555',
    fontSize: 11,
    fontStyle: 'italic',
  },
  chartGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: 6,
    flex: 1,
    overflow: 'auto',
  },
  stateCard: {
    background: '#0a0a12',
    border: '1px solid #1a1a2e',
    borderRadius: 4,
    padding: '6px 8px',
  },
  stateGrid: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 3,
    marginTop: 4,
  },
  stateRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  stateName: {
    fontSize: 8,
    fontWeight: 600,
    width: 60,
    fontFamily: "'JetBrains Mono', monospace",
  },
  stateBar: {
    flex: 1,
    height: 4,
    background: '#1a1a2e',
    borderRadius: 2,
    overflow: 'hidden',
  },
  stateFill: {
    height: '100%',
    borderRadius: 2,
    transition: 'width 0.3s ease',
  },
  statePct: {
    fontSize: 8,
    color: '#666',
    width: 28,
    textAlign: 'right' as const,
    fontFamily: "'JetBrains Mono', monospace",
  },
};
