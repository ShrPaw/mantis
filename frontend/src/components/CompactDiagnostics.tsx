// MANTIS — Compact Diagnostics
// Compressed SPE layer survival + metric charts for secondary position
// Does not dominate the interface — secondary information
import React, { useRef, useEffect } from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

const LAYER_ORDER = [
  { key: 'L1_context_gate', name: 'L1', desc: 'Context' },
  { key: 'L2_pressure', name: 'L2', desc: 'Pressure' },
  { key: 'L3_displacement', name: 'L3', desc: 'Displace' },
  { key: 'L4_sweep', name: 'L4', desc: 'Sweep' },
  { key: 'L5_trap', name: 'L5', desc: 'Trap' },
  { key: 'L6_execution_filter', name: 'L6', desc: 'Exec' },
  { key: 'L7_entry_zone', name: 'L7', desc: 'Entry' },
  { key: 'L8_exit_model', name: 'L8', desc: 'Exit' },
  { key: 'confidence_gate', name: 'CG', desc: 'Conf' },
];

function getLayerColor(counts: { pass: number; fail: number; not_evaluated: number }, raw: number): string {
  if (raw === 0) return T.text.faint;
  const { pass, fail } = counts;
  if (pass > 0 && fail === 0) return T.green.primary;
  if (fail > 0 && pass === 0) return T.status.danger;
  if (pass === 0 && fail === 0) return T.text.faint;
  return T.status.warning;
}

function drawMiniSparkline(ctx: CanvasRenderingContext2D, data: number[], w: number, h: number, color: string) {
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
  ctx.lineWidth = 1;
  ctx.stroke();
}

export const CompactDiagnostics: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const history = useOperatorStore(s => s.metricHistory);
  const spe = status?.spe;
  const lc = spe?.layer_counts ?? {};
  const raw = spe?.raw_evaluations ?? 0;
  const accountingValid = spe?.accounting_valid ?? true;

  const evalsCanvasRef = useRef<HTMLCanvasElement>(null);
  const emittedCanvasRef = useRef<HTMLCanvasElement>(null);

  const evals = history.map(m => m.raw_evaluations);
  const emitted = history.map(m => m.emitted_events);

  // Draw sparklines
  useEffect(() => {
    const drawLine = (ref: React.RefObject<HTMLCanvasElement>, data: number[], color: string) => {
      const c = ref.current;
      if (!c || data.length < 2) return;
      const ctx = c.getContext('2d');
      if (!ctx) return;
      const dpr = window.devicePixelRatio || 1;
      const r = c.getBoundingClientRect();
      c.width = r.width * dpr;
      c.height = r.height * dpr;
      ctx.scale(dpr, dpr);
      drawMiniSparkline(ctx, data, r.width, r.height, color);
    };
    drawLine(evalsCanvasRef, evals, T.green.primary);
    drawLine(emittedCanvasRef, emitted, T.green.holo);
  }, [evals, emitted]);

  return (
    <div style={S.panel}>
      <div style={S.header}>
        <span style={S.title}>SPE DIAGNOSTICS</span>
        <span style={S.stats}>
          {raw.toLocaleString()} evals · {spe?.full_8_layer_passes ?? 0} full8 · {spe?.emitted_events ?? 0} emitted
        </span>
      </div>

      {!accountingValid && (
        <div style={S.criticalWarn}>⚠ ACCOUNTING INVALID</div>
      )}

      {/* Layer strip */}
      <div style={S.layerStrip}>
        {LAYER_ORDER.map(layer => {
          const counts = lc[layer.key] ?? { pass: 0, fail: 0, not_evaluated: 0 };
          const color = getLayerColor(counts, raw);
          const evaluated = counts.pass + counts.fail;
          const passRate = evaluated > 0 ? (counts.pass / evaluated * 100) : 0;
          return (
            <div key={layer.key} style={{ ...S.layerCell, borderColor: color + '30' }}>
              <span style={{ ...S.layerName, color }}>{layer.name}</span>
              <span style={S.layerDesc}>{layer.desc}</span>
              <div style={S.layerBar}>
                <div style={{
                  height: '100%', borderRadius: 1,
                  width: raw > 0 ? `${(evaluated / raw * 100)}%` : '0%',
                  background: color + '40',
                  transition: 'width 0.3s',
                }} />
              </div>
              <span style={{ ...S.layerStat, color }}>
                {raw > 0 ? `${counts.pass}✓ ${counts.fail}✗` : '—'}
              </span>
            </div>
          );
        })}
      </div>

      {/* Mini sparklines */}
      <div style={S.sparkRow}>
        <div style={S.sparkCell}>
          <span style={S.sparkLabel}>EVALS</span>
          <canvas ref={evalsCanvasRef} style={{ width: '100%', height: 20, display: 'block' }} />
          <span style={S.sparkVal}>{evals.length > 0 ? evals[evals.length - 1].toLocaleString() : '0'}</span>
        </div>
        <div style={S.sparkCell}>
          <span style={S.sparkLabel}>EMITTED</span>
          <canvas ref={emittedCanvasRef} style={{ width: '100%', height: 20, display: 'block' }} />
          <span style={S.sparkVal}>{emitted.length > 0 ? emitted[emitted.length - 1].toString() : '0'}</span>
        </div>
      </div>

      {raw === 0 && (
        <div style={S.silentNote}>0 SPE events — system silent by design</div>
      )}
    </div>
  );
};

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: `linear-gradient(180deg, ${T.bg.panel} 0%, ${T.bg.surface} 100%)`,
    border: `1px solid ${T.border.mid}`,
    borderRadius: 6,
    padding: '6px 8px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  header: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4,
  },
  title: {
    fontSize: 8, fontWeight: 700, color: T.green.primary, letterSpacing: 2,
    textShadow: `0 0 8px ${T.green.glow}`,
  },
  stats: { fontSize: 7, color: T.text.muted },
  criticalWarn: {
    padding: '3px 6px', background: 'rgba(255,95,95,0.1)',
    border: `1px solid rgba(255,95,95,0.3)`, borderRadius: 3,
    color: T.status.danger, fontSize: 8, fontWeight: 700, marginBottom: 4, letterSpacing: 1,
  },
  layerStrip: {
    display: 'flex', gap: 2, marginBottom: 4,
  },
  layerCell: {
    flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center',
    padding: '3px 2px', background: T.bg.card, borderRadius: 3,
    border: '1px solid', gap: 1,
  },
  layerName: { fontSize: 8, fontWeight: 700, letterSpacing: 0.5 },
  layerDesc: { fontSize: 6, color: T.text.faint },
  layerBar: { width: '100%', height: 2, background: T.border.dim, borderRadius: 1, overflow: 'hidden' },
  layerStat: { fontSize: 6, fontWeight: 600 },
  sparkRow: {
    display: 'flex', gap: 4, flex: 1,
  },
  sparkCell: {
    flex: 1, display: 'flex', flexDirection: 'column', gap: 2,
    background: T.bg.card, borderRadius: 3, padding: '3px 5px',
    border: `1px solid ${T.border.dim}`,
  },
  sparkLabel: { fontSize: 6, color: T.text.muted, letterSpacing: 1 },
  sparkVal: { fontSize: 9, fontWeight: 700, color: T.green.primary, textAlign: 'right' },
  silentNote: {
    textAlign: 'center', fontSize: 8, color: T.text.faint, fontStyle: 'italic', marginTop: 4,
  },
};
