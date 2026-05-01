// MANTIS — Pressure Heatmap
// Simplified pressure visualization: spread/imbalance/depth over time
// Honest labeling — this is a proxy, not a full exchange heatmap
import React, { useRef, useEffect } from 'react';
import { useStore } from '../store';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

export const PressureHeatmap: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const historyRef = useRef<{ imbalance: number; freq: number; delta: number; spread: number }[]>([]);
  const frameRef = useRef<number>(0);
  const flow = useStore(s => s.flow);
  const heatmap = useStore(s => s.heatmap);
  const opStatus = useOperatorStore(s => s.status);
  const market = opStatus?.market;

  // Collect pressure data points
  useEffect(() => {
    const imbalance = flow.imbalance ?? 0;
    const freq = flow.trade_frequency ?? 0;
    const delta = flow.delta ?? 0;

    // Estimate spread from bid/ask
    let spread = 0;
    if (heatmap.bids.length > 0 && heatmap.asks.length > 0) {
      const bestBid = Math.max(...heatmap.bids.map(b => b.price));
      const bestAsk = Math.min(...heatmap.asks.map(a => a.price));
      spread = bestAsk - bestBid;
    }

    historyRef.current.push({ imbalance, freq, delta, spread });
    if (historyRef.current.length > 200) {
      historyRef.current = historyRef.current.slice(-200);
    }
  }, [flow.imbalance, flow.trade_frequency, flow.delta, heatmap.bids, heatmap.asks]);

  // Draw
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const r = canvas.getBoundingClientRect();
      canvas.width = r.width * dpr;
      canvas.height = r.height * dpr;
      ctx.scale(dpr, dpr);
      const w = r.width;
      const h = r.height;

      ctx.clearRect(0, 0, w, h);

      const data = historyRef.current;
      if (data.length < 2) {
        ctx.fillStyle = T.text.faint;
        ctx.font = '9px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText('Collecting pressure data...', w / 2, h / 2);
        frameRef.current = requestAnimationFrame(draw);
        return;
      }

      const colW = Math.max(2, w / data.length);
      const rows = 4; // imbalance, freq, delta, spread
      const rowH = h / rows;

      // Row labels
      ctx.fillStyle = T.text.faint;
      ctx.font = '7px JetBrains Mono, monospace';
      ctx.textAlign = 'left';
      const labels = ['IMBALANCE', 'FREQUENCY', 'DELTA', 'SPREAD'];
      for (let r = 0; r < rows; r++) {
        ctx.fillText(labels[r], 2, r * rowH + 10);
      }

      for (let i = 0; i < data.length; i++) {
        const d = data[i];
        const x = i * colW;

        // Imbalance row (top) — green/red intensity
        const imbNorm = Math.min(Math.abs(d.imbalance) * 5, 1);
        const imbColor = d.imbalance >= 0 ? `rgba(57,255,136,${imbNorm * 0.6})` : `rgba(255,95,95,${imbNorm * 0.6})`;
        ctx.fillStyle = imbColor;
        ctx.fillRect(x, 0, colW - 1, rowH - 1);

        // Frequency row — intensity based on trade rate
        const freqNorm = Math.min(d.freq / 8, 1);
        ctx.fillStyle = `rgba(0,229,200,${freqNorm * 0.5})`;
        ctx.fillRect(x, rowH, colW - 1, rowH - 1);

        // Delta row — green/red
        const deltaNorm = Math.min(Math.abs(d.delta) / 2, 1);
        const deltaColor = d.delta >= 0 ? `rgba(38,166,154,${deltaNorm * 0.6})` : `rgba(239,83,80,${deltaNorm * 0.6})`;
        ctx.fillStyle = deltaColor;
        ctx.fillRect(x, rowH * 2, colW - 1, rowH - 1);

        // Spread row — yellow intensity
        const spreadNorm = Math.min(d.spread / 20, 1);
        ctx.fillStyle = `rgba(240,185,11,${spreadNorm * 0.4})`;
        ctx.fillRect(x, rowH * 3, colW - 1, rowH - 1);
      }

      // Row dividers
      ctx.strokeStyle = T.border.dim;
      ctx.lineWidth = 0.5;
      for (let r = 1; r < rows; r++) {
        ctx.beginPath();
        ctx.moveTo(0, r * rowH);
        ctx.lineTo(w, r * rowH);
        ctx.stroke();
      }

      // Current values on right
      const latest = data[data.length - 1];
      ctx.fillStyle = T.text.main;
      ctx.font = '8px JetBrains Mono, monospace';
      ctx.textAlign = 'right';
      ctx.fillText(`${(latest.imbalance * 100).toFixed(1)}%`, w - 2, 10);
      ctx.fillText(`${latest.freq.toFixed(1)}/s`, w - 2, rowH + 10);
      ctx.fillText(`${latest.delta >= 0 ? '+' : ''}${latest.delta.toFixed(3)}`, w - 2, rowH * 2 + 10);
      ctx.fillText(`${latest.spread.toFixed(1)}`, w - 2, rowH * 3 + 10);

      frameRef.current = requestAnimationFrame(draw);
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, []);

  return (
    <div style={S.panel}>
      <div style={S.header}>
        <span style={S.title}>PRESSURE HEATMAP</span>
        <span style={S.note}>proxy · imbalance/frequency/delta/spread over time</span>
      </div>
      <canvas ref={canvasRef} style={{ width: '100%', flex: 1, display: 'block' }} />
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
  note: { fontSize: 6, color: T.text.faint, fontStyle: 'italic', letterSpacing: 0.5 },
};
