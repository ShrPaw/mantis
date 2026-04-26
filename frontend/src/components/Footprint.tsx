// MANTIS Dashboard — Footprint Chart (Canvas)
import { useRef, useEffect } from 'react';
import { useStore } from '../store';
import { formatDelta } from '../services/format';

export function Footprint() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const footprints = useStore(s => s.footprints);

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
    const W = rect.width;
    const H = rect.height;

    ctx.clearRect(0, 0, W, H);

    if (!footprints || footprints.length === 0) {
      ctx.fillStyle = '#333';
      ctx.font = '11px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('Building footprint data...', W / 2, H / 2);
      ctx.textAlign = 'left';
      return;
    }

    // Title
    ctx.fillStyle = '#444';
    ctx.font = '8px monospace';
    ctx.fillText('FOOTPRINT (VOLUME CLUSTERS)', 6, 10);

    const candles = footprints.slice(-8);
    const candleW = Math.min(100, (W - 10) / candles.length);
    const startX = 6;
    const topY = 16;
    const maxH = H - topY - 6;

    // Global max volume
    let globalMaxVol = 0;
    for (const c of candles) {
      for (const lv of c.levels) {
        globalMaxVol = Math.max(globalMaxVol, lv.bid_vol + lv.ask_vol);
      }
    }
    if (globalMaxVol === 0) globalMaxVol = 1;

    candles.forEach((candle, ci) => {
      const x = startX + ci * candleW;
      const isGreen = candle.close >= candle.open;

      // Background column
      const bgColor = isGreen ? 'rgba(0, 230, 118, 0.03)' : 'rgba(255, 23, 68, 0.03)';
      ctx.fillStyle = bgColor;
      ctx.fillRect(x, topY, candleW - 2, maxH);

      // Time label
      const d = new Date(candle.open_time * 1000);
      const mins = d.toTimeString().slice(0, 5);
      ctx.fillStyle = '#666';
      ctx.font = '7px monospace';
      ctx.fillText(mins, x + 2, topY + 9);

      // Delta
      ctx.fillStyle = candle.total_delta >= 0 ? '#00e676' : '#ff1744';
      ctx.font = '7px monospace';
      ctx.fillText(`Δ${formatDelta(candle.total_delta)}`, x + 2, topY + 18);

      // Volume levels (top 7 by volume)
      const levels = [...candle.levels]
        .sort((a, b) => (b.bid_vol + b.ask_vol) - (a.bid_vol + a.ask_vol))
        .slice(0, 7);

      levels.forEach((lv, li) => {
        const ly = topY + 24 + li * 13;
        if (ly > H - 8) return;

        const total = lv.bid_vol + lv.ask_vol;
        const barW = (total / globalMaxVol) * (candleW - 14);

        const bidW = total > 0 ? (lv.bid_vol / total) * barW : 0;

        // Bid bar (green)
        ctx.fillStyle = 'rgba(0, 230, 118, 0.2)';
        ctx.fillRect(x + 2, ly, bidW, 9);

        // Ask bar (red)
        ctx.fillStyle = 'rgba(255, 23, 68, 0.2)';
        ctx.fillRect(x + 2 + bidW, ly, barW - bidW, 9);

        // Imbalance highlight
        if (Math.abs(lv.imbalance) > 0.6) {
          ctx.strokeStyle = lv.imbalance > 0 ? '#00e67660' : '#ff174460';
          ctx.lineWidth = 1;
          ctx.strokeRect(x + 1, ly - 1, barW + 2, 11);
        }

        // Price label
        ctx.fillStyle = '#777';
        ctx.font = '6px monospace';
        ctx.fillText(lv.price.toFixed(1), x + Math.min(barW + 4, candleW - 14), ly + 7);
      });

      // Total volume footer
      ctx.fillStyle = '#444';
      ctx.font = '6px monospace';
      ctx.fillText(`V:${candle.total_vol.toFixed(1)}`, x + 2, H - 2);
    });
  }, [footprints]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '100%', display: 'block' }}
    />
  );
}
