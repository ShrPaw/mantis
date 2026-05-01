// MANTIS — Pressure Bubble Map
// Visual bubble map for large trades and event pressure
// Uses proxy data from trade bursts / imbalance — labeled honestly
import React, { useRef, useEffect } from 'react';
import { useStore } from '../store';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

interface Bubble {
  x: number;
  y: number;
  r: number;
  color: string;
  alpha: number;
  label: string;
  age: number;
}

export const PressureBubbleMap: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const bubblesRef = useRef<Bubble[]>([]);
  const frameRef = useRef<number>(0);
  const largeTrades = useStore(s => s.largeTrades);
  const events = useStore(s => s.events);
  const flow = useStore(s => s.flow);
  const opStatus = useOperatorStore(s => s.status);
  const spe = opStatus?.spe;

  // Generate bubbles from recent trades
  useEffect(() => {
    if (!largeTrades.length) return;
    const trade = largeTrades[0];
    if (!trade || trade.qty < 0.3) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const w = canvas.width / (window.devicePixelRatio || 1);
    const h = canvas.height / (window.devicePixelRatio || 1);

    const bubble: Bubble = {
      x: Math.random() * (w - 40) + 20,
      y: Math.random() * (h - 40) + 20,
      r: Math.min(4 + trade.qty * 6, 30),
      color: trade.side === 'buy' ? '#26a69a' : '#ef5350',
      alpha: 0.6,
      label: `${trade.qty.toFixed(2)}`,
      age: 0,
    };
    bubblesRef.current = [bubble, ...bubblesRef.current].slice(0, 30);
  }, [largeTrades]);

  // Generate bubbles from events
  useEffect(() => {
    if (!events.length) return;
    const evt = events[0];
    const color = evt.event_type === 'absorption' ? '#00e5c8'
      : evt.event_type === 'liquidity_sweep' ? '#ff5f5f'
      : evt.event_type === 'exhaustion' ? '#ffcc66'
      : '#39ff88';

    const canvas = canvasRef.current;
    if (!canvas) return;
    const w = canvas.width / (window.devicePixelRatio || 1);
    const h = canvas.height / (window.devicePixelRatio || 1);

    const strength = evt.scores?.strength_score ?? 0.5;
    const bubble: Bubble = {
      x: Math.random() * (w - 40) + 20,
      y: Math.random() * (h - 40) + 20,
      r: Math.min(6 + strength * 20, 35),
      color,
      alpha: 0.4,
      label: evt.event_type.substring(0, 6),
      age: 0,
    };
    bubblesRef.current = [bubble, ...bubblesRef.current].slice(0, 30);
  }, [events]);

  // Animation loop
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

      // Draw grid lines
      ctx.strokeStyle = T.border.dim;
      ctx.lineWidth = 0.5;
      for (let i = 0; i < 5; i++) {
        const y = (h / 5) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      // Update and draw bubbles
      bubblesRef.current = bubblesRef.current.filter(b => {
        b.age += 1;
        b.alpha = Math.max(0, b.alpha - 0.003);
        b.r = Math.max(0, b.r - 0.05);
        return b.alpha > 0 && b.r > 0;
      });

      for (const b of bubblesRef.current) {
        // Glow
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r + 4, 0, Math.PI * 2);
        ctx.fillStyle = b.color + '10';
        ctx.fill();

        // Main bubble
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fillStyle = b.color + Math.round(b.alpha * 255).toString(16).padStart(2, '0');
        ctx.fill();
        ctx.strokeStyle = b.color + '40';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Label
        if (b.r > 8) {
          ctx.fillStyle = T.text.bright + Math.round(b.alpha * 255).toString(16).padStart(2, '0');
          ctx.font = `${Math.min(8, b.r * 0.6)}px JetBrains Mono, monospace`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(b.label, b.x, b.y);
        }
      }

      // Delta bar at bottom
      const delta = flow.delta ?? 0;
      const maxDelta = 5;
      const barW = Math.min(Math.abs(delta) / maxDelta, 1) * (w / 2);
      const barY = h - 4;
      ctx.fillStyle = delta >= 0 ? '#26a69a40' : '#ef535040';
      if (delta >= 0) {
        ctx.fillRect(w / 2, barY, barW, 3);
      } else {
        ctx.fillRect(w / 2 - barW, barY, barW, 3);
      }
      ctx.fillStyle = '#39ff8830';
      ctx.fillRect(w / 2 - 0.5, barY, 1, 3);

      frameRef.current = requestAnimationFrame(draw);
    };

    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, [flow.delta]);

  return (
    <div style={S.panel}>
      <div style={S.header}>
        <span style={S.title}>PRESSURE BUBBLES</span>
        <span style={S.note}>proxy · trade bursts & event pressure</span>
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
