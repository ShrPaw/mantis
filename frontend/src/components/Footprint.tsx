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
      ctx.fillStyle = '#444';
      ctx.font = '11px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('Building footprint data...', W / 2, H / 2);
      ctx.textAlign = 'left';
      return;
    }

    // Title + legend
    ctx.fillStyle = '#555';
    ctx.font = 'bold 9px monospace';
    ctx.fillText('FOOTPRINT', 6, 12);

    ctx.font = '7px monospace';
    ctx.fillStyle = '#26a69a';
    ctx.fillText('● Bid vol', 80, 12);
    ctx.fillStyle = '#ef5350';
    ctx.fillText('● Ask vol', 130, 12);
    ctx.fillStyle = '#555';
    ctx.fillText('= volume at price', 178, 12);

    const candles = footprints.slice(-8);
    const candleW = Math.min(110, (W - 10) / candles.length);
    const startX = 6;
    const topY = 20;
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
      ctx.fillStyle = isGreen ? 'rgba(38, 166, 154, 0.04)' : 'rgba(239, 83, 80, 0.04)';
      ctx.fillRect(x, topY, candleW - 2, maxH);

      // Column border
      ctx.strokeStyle = '#1a1a2e';
      ctx.lineWidth = 0.5;
      ctx.strokeRect(x, topY, candleW - 2, maxH);

      // Time label
      const d = new Date(candle.open_time * 1000);
      const mins = d.toTimeString().slice(0, 5);
      ctx.fillStyle = '#888';
      ctx.font = 'bold 8px monospace';
      ctx.fillText(mins, x + 3, topY + 10);

      // Delta
      ctx.fillStyle = candle.total_delta >= 0 ? '#26a69a' : '#ef5350';
      ctx.font = 'bold 8px monospace';
      ctx.fillText(`Δ${formatDelta(candle.total_delta)}`, x + 3, topY + 20);

      // Volume levels (top 8 by volume)
      const levels = [...candle.levels]
        .sort((a, b) => (b.bid_vol + b.ask_vol) - (a.bid_vol + a.ask_vol))
        .slice(0, 8);

      levels.forEach((lv, li) => {
        const ly = topY + 26 + li * 14;
        if (ly > H - 10) return;

        const total = lv.bid_vol + lv.ask_vol;
        const barW = Math.max((total / globalMaxVol) * (candleW - 16), 2);
        const bidW = total > 0 ? (lv.bid_vol / total) * barW : 0;

        // Bid bar (green)
        ctx.fillStyle = 'rgba(38, 166, 154, 0.3)';
        ctx.fillRect(x + 3, ly, bidW, 10);

        // Ask bar (red)
        ctx.fillStyle = 'rgba(239, 83, 80, 0.3)';
        ctx.fillRect(x + 3 + bidW, ly, barW - bidW, 10);

        // Imbalance highlight — strong single-side dominance
        if (Math.abs(lv.imbalance) > 0.6) {
          ctx.strokeStyle = lv.imbalance > 0 ? '#26a69a' : '#ef5350';
          ctx.lineWidth = 1.5;
          ctx.strokeRect(x + 2, ly - 1, barW + 2, 12);
        }

        // Price label
        ctx.fillStyle = '#999';
        ctx.font = '7px monospace';
        ctx.textAlign = 'left';
        ctx.fillText(lv.price.toFixed(1), x + Math.min(barW + 5, candleW - 16), ly + 8);
      });

      // Total volume footer
      ctx.fillStyle = '#666';
      ctx.font = 'bold 7px monospace';
      ctx.fillText(`V:${candle.total_vol.toFixed(1)}`, x + 3, H - 3);
    });
  }, [footprints]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '100%', display: 'block' }}
    />
  );
}
