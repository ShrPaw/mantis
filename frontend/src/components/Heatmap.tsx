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
      ctx.fillStyle = '#333';
      ctx.font = '11px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('Waiting for order book...', W / 2, H / 2);
      ctx.textAlign = 'left';
      return;
    }

    const allLevels = [...bids, ...asks];
    const maxQty = Math.max(...allLevels.map(l => l.qty), 0.001);
    const rowH = Math.min(Math.floor((H - 30) / (allLevels.length + 2)), 20);
    const startY = 22;
    const priceW = 65;

    // Title
    ctx.fillStyle = '#444';
    ctx.font = '8px monospace';
    ctx.fillText('ORDER BOOK', 6, 10);

    // Wall indicator
    const wallThreshold = maxQty * 0.4;
    const hasBidsWall = bids.some(b => b.qty > wallThreshold);
    const hasAsksWall = asks.some(a => a.qty > wallThreshold);

    if (hasBidsWall || hasAsksWall) {
      ctx.fillStyle = '#f0b90b';
      ctx.font = '8px monospace';
      ctx.textAlign = 'right';
      ctx.fillText('◆ WALL', W - 6, 10);
      ctx.textAlign = 'left';
    }

    // Mid price line
    const midY = startY + bids.length * rowH + 2;
    ctx.strokeStyle = '#f0b90b50';
    ctx.lineWidth = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(W, midY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Mid price label
    ctx.fillStyle = '#f0b90b';
    ctx.font = 'bold 10px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`$${formatPrice(mid)}`, W / 2, midY - 4);
    ctx.textAlign = 'left';

    // Spread
    if (bids.length > 0 && asks.length > 0) {
      const spread = asks[asks.length - 1].price - bids[0].price;
      ctx.fillStyle = '#555';
      ctx.font = '7px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`spread: ${formatPrice(Math.abs(spread))}`, W / 2, midY + 10);
      ctx.textAlign = 'left';
    }

    // Draw bids
    bids.forEach((bid, i) => {
      const y = startY + i * rowH;
      const w = (bid.qty / maxQty) * (W - priceW - 10);
      const isWall = bid.qty > wallThreshold;

      // Background bar
      ctx.fillStyle = isWall ? 'rgba(0, 200, 83, 0.25)' : 'rgba(0, 200, 83, 0.08)';
      ctx.fillRect(priceW, y, w, rowH - 1);

      // Wall glow
      if (isWall) {
        ctx.shadowColor = '#00c853';
        ctx.shadowBlur = 10;
        ctx.fillStyle = 'rgba(0, 200, 83, 0.35)';
        ctx.fillRect(priceW, y, w, rowH - 1);
        ctx.shadowBlur = 0;
      }

      // Price label
      ctx.fillStyle = isWall ? '#00e676' : '#00e67680';
      ctx.font = `${isWall ? 'bold ' : ''}9px monospace`;
      ctx.textAlign = 'right';
      ctx.fillText(formatPrice(bid.price), priceW - 4, y + rowH - 4);
      ctx.textAlign = 'left';

      // Quantity
      ctx.fillStyle = '#00e67660';
      ctx.font = '7px monospace';
      ctx.fillText(formatSize(bid.qty), priceW + w + 3, y + rowH - 4);
    });

    // Draw asks
    asks.forEach((ask, i) => {
      const y = midY + 14 + i * rowH;
      const w = (ask.qty / maxQty) * (W - priceW - 10);
      const isWall = ask.qty > wallThreshold;

      ctx.fillStyle = isWall ? 'rgba(255, 23, 68, 0.25)' : 'rgba(255, 23, 68, 0.08)';
      ctx.fillRect(priceW, y, w, rowH - 1);

      if (isWall) {
        ctx.shadowColor = '#ff1744';
        ctx.shadowBlur = 10;
        ctx.fillStyle = 'rgba(255, 23, 68, 0.35)';
        ctx.fillRect(priceW, y, w, rowH - 1);
        ctx.shadowBlur = 0;
      }

      ctx.fillStyle = isWall ? '#ff1744' : '#ff174480';
      ctx.font = `${isWall ? 'bold ' : ''}9px monospace`;
      ctx.textAlign = 'right';
      ctx.fillText(formatPrice(ask.price), priceW - 4, y + rowH - 4);
      ctx.textAlign = 'left';

      ctx.fillStyle = '#ff174460';
      ctx.font = '7px monospace';
      ctx.fillText(formatSize(ask.qty), priceW + w + 3, y + rowH - 4);
    });

  }, [heatmap]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '100%', display: 'block' }}
    />
  );
}
