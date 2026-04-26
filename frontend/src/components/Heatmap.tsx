// MANTIS Dashboard — Order Book Heatmap (Canvas)
import { useRef, useEffect } from 'react';
import { useStore } from '../store';
import { formatPrice, formatSize } from '../services/format';

export function Heatmap() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const heatmap = useStore(s => s.heatmap);

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

    const { bids = [], asks = [], mid = 0 } = heatmap;

    if (!bids.length && !asks.length) {
      ctx.fillStyle = '#444';
      ctx.font = '11px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('Waiting for order book...', W / 2, H / 2);
      ctx.textAlign = 'left';
      return;
    }

    const allLevels = [...bids, ...asks];
    const maxQty = Math.max(...allLevels.map(l => l.qty), 0.001);
    const rowH = Math.min(Math.floor((H - 50) / (allLevels.length + 2)), 22);
    const startY = 30;
    const priceW = 70;
    const qtyW = 50;

    // Title + legend
    ctx.fillStyle = '#555';
    ctx.font = 'bold 9px monospace';
    ctx.fillText('ORDER BOOK', 6, 12);

    // Legend row
    ctx.font = '7px monospace';
    ctx.fillStyle = '#26a69a';
    ctx.fillText('● BIDS', 6, 24);
    ctx.fillStyle = '#ef5350';
    ctx.fillText('● ASKS', 55, 24);
    ctx.fillStyle = '#555';
    ctx.fillText(`depth: ${bids.length}×${asks.length}`, 105, 24);

    // Wall indicator
    const wallThreshold = maxQty * 0.4;
    const hasWall = bids.some(b => b.qty > wallThreshold) || asks.some(a => a.qty > wallThreshold);
    if (hasWall) {
      ctx.fillStyle = '#f0b90b';
      ctx.font = 'bold 8px monospace';
      ctx.textAlign = 'right';
      ctx.fillText('◆ WALL DETECTED', W - 6, 12);
      ctx.textAlign = 'left';
    }

    // Mid price separator
    const midY = startY + bids.length * rowH + 4;

    // Draw bids (green, top section)
    bids.forEach((bid, i) => {
      const y = startY + i * rowH;
      const barMaxW = W - priceW - qtyW - 8;
      const w = (bid.qty / maxQty) * barMaxW;
      const isWall = bid.qty > wallThreshold;
      const fillAlpha = isWall ? 0.35 : 0.15;

      // Bar
      ctx.fillStyle = `rgba(38, 166, 154, ${fillAlpha})`;
      ctx.fillRect(priceW, y, w, rowH - 2);

      // Wall glow
      if (isWall) {
        ctx.shadowColor = '#26a69a';
        ctx.shadowBlur = 8;
        ctx.fillStyle = 'rgba(38, 166, 154, 0.5)';
        ctx.fillRect(priceW, y, w, rowH - 2);
        ctx.shadowBlur = 0;

        // Wall border
        ctx.strokeStyle = '#26a69a80';
        ctx.lineWidth = 1;
        ctx.strokeRect(priceW, y, w, rowH - 2);
      }

      // Price label
      ctx.fillStyle = isWall ? '#26a69a' : '#26a69a90';
      ctx.font = `${isWall ? 'bold ' : ''}10px monospace`;
      ctx.textAlign = 'right';
      ctx.fillText(formatPrice(bid.price), priceW - 6, y + rowH - 5);
      ctx.textAlign = 'left';

      // Quantity label (right of bar)
      ctx.fillStyle = isWall ? '#26a69a' : '#26a69a60';
      ctx.font = `${isWall ? 'bold ' : ''}8px monospace`;
      ctx.textAlign = 'left';
      ctx.fillText(formatSize(bid.qty), priceW + w + 4, y + rowH - 5);
    });

    // Mid price line
    ctx.strokeStyle = '#f0b90b';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(W, midY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Mid price label
    ctx.fillStyle = '#f0b90b';
    ctx.font = 'bold 11px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`$${formatPrice(mid)}`, W / 2, midY - 5);
    ctx.textAlign = 'left';

    // Spread
    if (bids.length > 0 && asks.length > 0) {
      const bestBid = bids[0].price;
      const bestAsk = asks[asks.length - 1].price;
      const spread = Math.abs(bestAsk - bestBid);
      const spreadBps = (spread / mid * 10000).toFixed(1);
      ctx.fillStyle = '#666';
      ctx.font = '8px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`spread: ${formatPrice(spread)} (${spreadBps} bps)`, W / 2, midY + 12);
      ctx.textAlign = 'left';
    }

    // Draw asks (red, bottom section)
    asks.forEach((ask, i) => {
      const y = midY + 18 + i * rowH;
      const barMaxW = W - priceW - qtyW - 8;
      const w = (ask.qty / maxQty) * barMaxW;
      const isWall = ask.qty > wallThreshold;
      const fillAlpha = isWall ? 0.35 : 0.15;

      ctx.fillStyle = `rgba(239, 83, 80, ${fillAlpha})`;
      ctx.fillRect(priceW, y, w, rowH - 2);

      if (isWall) {
        ctx.shadowColor = '#ef5350';
        ctx.shadowBlur = 8;
        ctx.fillStyle = 'rgba(239, 83, 80, 0.5)';
        ctx.fillRect(priceW, y, w, rowH - 2);
        ctx.shadowBlur = 0;

        ctx.strokeStyle = '#ef535080';
        ctx.lineWidth = 1;
        ctx.strokeRect(priceW, y, w, rowH - 2);
      }

      ctx.fillStyle = isWall ? '#ef5350' : '#ef535090';
      ctx.font = `${isWall ? 'bold ' : ''}10px monospace`;
      ctx.textAlign = 'right';
      ctx.fillText(formatPrice(ask.price), priceW - 6, y + rowH - 5);
      ctx.textAlign = 'left';

      ctx.fillStyle = isWall ? '#ef5350' : '#ef535060';
      ctx.font = `${isWall ? 'bold ' : ''}8px monospace`;
      ctx.textAlign = 'left';
      ctx.fillText(formatSize(ask.qty), priceW + w + 4, y + rowH - 5);
    });

  }, [heatmap]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '100%', display: 'block' }}
    />
  );
}
