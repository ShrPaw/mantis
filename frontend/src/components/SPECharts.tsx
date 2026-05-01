// MANTIS Operator Dashboard — SPE Charts (redesigned)
// Answers: Are evaluations increasing? Is state always IDLE?
//          Has any event emitted? Is L1 always blocking?
import React, { useRef, useEffect } from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

function drawSparkline(ctx: CanvasRenderingContext2D, data: number[], w: number, h: number, color: string, fill: string) {
  ctx.clearRect(0, 0, w, h);
  if (data.length < 2) return;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const step = w / (data.length - 1);

  ctx.beginPath();
  ctx.moveTo(0, h - ((data[0] - min) / range) * h);
  for (let i = 1; i < data.length; i++) ctx.lineTo(i * step, h - ((data[i] - min) / range) * h);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();

  ctx.lineTo(w, h);
  ctx.lineTo(0, h);
  ctx.closePath();
  ctx.fillStyle = fill;
  ctx.fill();
}

function drawStackedBar(ctx: CanvasRenderingContext2D, pass: number[], fail: number[], ne: number[], w: number, h: number) {
  ctx.clearRect(0, 0, w, h);
  if (pass.length < 1) return;
  const barW = Math.max(2, (w / pass.length) - 1);
  for (let i = 0; i < pass.length; i++) {
    const total = pass[i] + fail[i] + ne[i];
    if (total === 0) continue;
    const x = i * (barW + 1);
    let y = h;
    const ph = (pass[i] / total) * h;
    ctx.fillStyle = 'rgba(57, 255, 136, 0.6)';
    ctx.fillRect(x, y - ph, barW, ph);
    y -= ph;
    const fh = (fail[i] / total) * h;
    ctx.fillStyle = 'rgba(255, 95, 95, 0.6)';
    ctx.fillRect(x, y - fh, barW, fh);
    y -= fh;
    const nh = (ne[i] / total) * h;
    ctx.fillStyle = 'rgba(58, 106, 82, 0.4)';
    ctx.fillRect(x, y - nh, barW, nh);
  }
}

const MiniChart: React.FC<{ title: string; data: number[]; color: string; fill: string; h?: number }> = ({ title, data, color, fill, h = 44 }) => {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const r = c.getBoundingClientRect();
    c.width = r.width * dpr;
    c.height = r.height * dpr;
    ctx.scale(dpr, dpr);
    drawSparkline(ctx, data, r.width, r.height, color, fill);
  }, [data, color, fill]);

  const latest = data.length > 0 ? data[data.length - 1] : 0;
  const max = data.length > 0 ? Math.max(...data) : 0;
  return (
    <div style={{ background: T.bg.card, border: `1px solid ${T.border.dim}`, borderRadius: 5, padding: '5px 7px', height: h + 28, display: 'flex', flexDirection: 'column' as const }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
        <span style={{ fontSize: 7, color: T.text.muted, letterSpacing: 1, textTransform: 'uppercase' as const }}>{title}</span>
        <span style={{ fontSize: 10, fontWeight: 700, color, textShadow: `0 0 6px ${color}30` }}>{latest.toLocaleString()}</span>
      </div>
      <canvas ref={ref} style={{ width: '100%', height: `${h}px`, display: 'block' }} />
    </div>
  );
};

export const SPECharts: React.FC = () => {
  const history = useOperatorStore(s => s.metricHistory);
  const status = useOperatorStore(s => s.status);
  const spe = status?.spe;
  const raw = spe?.raw_evaluations ?? 0;

  const evals = history.map(m => m.raw_evaluations);
  const emitted = history.map(m => m.emitted_events);
  const full8 = history.map(m => m.full_8_layer_passes);
  const l1p = history.map(m => m.layer_counts?.L1_context_gate?.pass ?? 0);
  const l1f = history.map(m => m.layer_counts?.L1_context_gate?.fail ?? 0);
  const l1n = history.map(m => m.layer_counts?.L1_context_gate?.not_evaluated ?? 0);

  const stateCounts: Record<string, number> = {};
  history.forEach(m => { const s = m.current_state || 'IDLE'; stateCounts[s] = (stateCounts[s] || 0) + 1; });

  const totalEmitted = emitted.length > 0 ? emitted[emitted.length - 1] : 0;
  const alwaysIdle = Object.keys(stateCounts).length === 1 && stateCounts['IDLE'] === history.length;
  const l1AlwaysBlocking = l1f.every(f => f > 0) && l1p.every(p => p === 0);

  return (
    <div style={S.panel}>
      <div style={S.header}>
        <span style={S.title}>SPE METRICS OVER TIME</span>
        {history.length >= 2 && (
          <span style={S.quickRead}>
            {alwaysIdle && <span style={{ color: T.text.muted }}>Always IDLE</span>}
            {l1AlwaysBlocking && !alwaysIdle && <span style={{ color: T.status.danger }}>L1 always blocking</span>}
            {totalEmitted > 0 && <span style={{ color: T.green.primary }}> · {totalEmitted} emitted</span>}
          </span>
        )}
      </div>

      {/* Quick answer bar */}
      {history.length >= 2 && (
        <div style={S.answerBar}>
          <AnswerChip
            label="Evaluations increasing?"
            answer={evals.length >= 2 && evals[evals.length - 1] > evals[0] ? 'YES' : 'NO'}
            color={evals.length >= 2 && evals[evals.length - 1] > evals[0] ? T.green.primary : T.text.muted}
          />
          <AnswerChip
            label="State always IDLE?"
            answer={alwaysIdle ? 'YES' : 'NO'}
            color={alwaysIdle ? T.status.warning : T.green.primary}
          />
          <AnswerChip
            label="Any event emitted?"
            answer={totalEmitted > 0 ? `YES (${totalEmitted})` : 'NO'}
            color={totalEmitted > 0 ? T.green.primary : T.text.muted}
          />
          <AnswerChip
            label="L1 always blocking?"
            answer={l1AlwaysBlocking ? 'YES' : 'NO'}
            color={l1AlwaysBlocking ? T.status.danger : T.green.primary}
          />
        </div>
      )}

      {history.length < 2 ? (
        <div style={S.empty}>
          <span className="animate-pulse-glow" style={{ color: T.green.primary, fontSize: 14 }}>◆</span>
          <span style={{ color: T.text.dim }}>Collecting data... ({history.length} sample{history.length !== 1 ? 's' : ''})</span>
          <span style={{ fontSize: 8, color: T.text.faint }}>Charts appear after a few polling cycles</span>
          {raw === 0 && (
            <div style={S.zeroNotice}>
              0 SPE events — system silent by design.
            </div>
          )}
        </div>
      ) : (
        <div style={S.chartGrid}>
          <MiniChart title="Raw Evaluations" data={evals} color="#39ff88" fill="rgba(57,255,136,0.06)" />
          <MiniChart title="Events Emitted" data={emitted} color="#00ffa6" fill="rgba(0,255,166,0.06)" />
          <MiniChart title="Full 8-Layer Passes" data={full8} color="#00e5c8" fill="rgba(0,229,200,0.06)" />

          <div style={{ background: T.bg.card, border: `1px solid ${T.border.dim}`, borderRadius: 5, padding: '5px 7px' }}>
            <div style={{ fontSize: 7, color: T.text.muted, letterSpacing: 1, marginBottom: 4 }}>STATE DISTRIBUTION</div>
            <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 3 }}>
              {Object.entries(stateCounts).sort((a, b) => b[1] - a[1]).map(([state, count]) => {
                const pct = (count / (history.length || 1)) * 100;
                const color = state === 'CASCADE' ? T.status.danger : state === 'UNWIND' ? T.status.warning : T.text.muted;
                return (
                  <div key={state} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ color, fontSize: 8, fontWeight: 600, width: 55 }}>{state}</span>
                    <div style={{ flex: 1, height: 4, background: T.border.dim, borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 2, transition: 'width 0.3s' }} />
                    </div>
                    <span style={{ fontSize: 7, color: T.text.dim, width: 26, textAlign: 'right' }}>{pct.toFixed(0)}%</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div style={{ background: T.bg.card, border: `1px solid ${T.border.dim}`, borderRadius: 5, padding: '5px 7px', display: 'flex', flexDirection: 'column' as const }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span style={{ fontSize: 7, color: T.text.muted, letterSpacing: 1 }}>L1 CONTEXT GATE</span>
              <span style={{ fontSize: 7, color: T.text.muted }}>
                <span style={{ color: T.green.primary }}>■</span> pass <span style={{ color: T.status.danger }}>■</span> fail <span style={{ color: T.text.muted }}>■</span> n/e
              </span>
            </div>
            <L1Bar passData={l1p} failData={l1f} neData={l1n} />
          </div>
        </div>
      )}
    </div>
  );
};

const AnswerChip: React.FC<{ label: string; answer: string; color: string }> = ({ label, answer, color }) => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '3px 8px',
    background: T.bg.card,
    borderRadius: 4,
    border: `1px solid ${T.border.dim}`,
  }}>
    <span style={{ fontSize: 8, color: T.text.muted }}>{label}</span>
    <span style={{ fontSize: 9, fontWeight: 700, color, textShadow: `0 0 4px ${color}20` }}>{answer}</span>
  </div>
);

const L1Bar: React.FC<{ passData: number[]; failData: number[]; neData: number[] }> = ({ passData, failData, neData }) => {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const r = c.getBoundingClientRect();
    c.width = r.width * dpr;
    c.height = r.height * dpr;
    ctx.scale(dpr, dpr);
    drawStackedBar(ctx, passData, failData, neData, r.width, r.height);
  }, [passData, failData, neData]);
  return <canvas ref={ref} style={{ width: '100%', height: '40px', display: 'block' }} />;
};

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: `linear-gradient(180deg, ${T.bg.panel} 0%, ${T.bg.surface} 100%)`,
    border: `1px solid ${T.border.mid}`,
    borderRadius: 6,
    padding: '8px 10px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  title: { fontSize: 9, fontWeight: 700, color: T.green.primary, letterSpacing: 2, textShadow: `0 0 8px ${T.green.glow}` },
  quickRead: { fontSize: 8, display: 'flex', gap: 4 },
  answerBar: {
    display: 'flex',
    gap: 4,
    marginBottom: 6,
    flexWrap: 'wrap',
  },
  empty: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    color: T.text.dim,
    fontSize: 11,
  },
  zeroNotice: {
    marginTop: 8,
    padding: '6px 12px',
    background: T.green.glow,
    border: `1px solid ${T.border.bright}`,
    borderRadius: 4,
    fontSize: 10,
    color: T.green.primary,
    textShadow: `0 0 6px ${T.green.glow}`,
  },
  chartGrid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4, flex: 1, overflow: 'auto' },
};
