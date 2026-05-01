// MANTIS Operator Dashboard — Live Metrics (holographic theme)
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

export const OperatorMetrics: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const market = status?.market;
  const backend = status?.backend;
  const buyVol = market?.taker_buy_vol ?? 0;
  const sellVol = market?.taker_sell_vol ?? 0;
  const totalVol = buyVol + sellVol;
  const buyPct = totalVol > 0 ? (buyVol / totalVol * 100) : 50;

  return (
    <div style={S.panel}>
      <div style={S.title}>LIVE METRICS</div>
      <div style={{ textAlign: 'center', marginBottom: 8 }}>
        <span style={S.price}>
          {market?.last_price ? `$${market.last_price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
        </span>
      </div>
      <div style={S.grid}>
        <Row label="Delta" value={market?.delta != null ? fmtSigned(market.delta, 3) : '—'} color={(market?.delta ?? 0) >= 0 ? T.green.primary : T.status.danger} />
        <Row label="Cum Delta" value={market?.cum_delta != null ? fmtSigned(market.cum_delta, 3) : '—'} color={(market?.cum_delta ?? 0) >= 0 ? T.green.primary : T.status.danger} />
        <Row label="Buy Vol" value={buyVol > 0 ? buyVol.toFixed(3) : '—'} color={T.green.primary} />
        <Row label="Sell Vol" value={sellVol > 0 ? sellVol.toFixed(3) : '—'} color={T.status.danger} />
        <Row label="Frequency" value={market?.trade_frequency ? `${market.trade_frequency.toFixed(1)}/s` : '—'} color={T.text.main} />
        <Row label="Imbalance" value={market?.imbalance != null ? `${(market.imbalance * 100).toFixed(1)}%` : '—'} color={(market?.imbalance ?? 0) >= 0 ? T.green.primary : T.status.danger} />
        <Row label="Candles" value={backend?.candles_loaded?.toString() ?? '—'} color={T.text.main} />
        <Row label="Clients" value={backend?.clients?.toString() ?? '—'} color={T.text.main} />
      </div>
      <div style={S.divider} />
      <div style={{ marginTop: 'auto' }}>
        <div style={{ fontSize: 8, color: T.text.muted, letterSpacing: 1, marginBottom: 4 }}>VOLUME SPLIT</div>
        <div style={S.volBar}>
          <div style={{ ...S.volBuy, width: `${buyPct}%` }} />
          <div style={{ ...S.volSell, width: `${100 - buyPct}%` }} />
        </div>
        <div style={S.volPcts}>
          <span style={{ color: T.green.primary }}>BUY {buyPct.toFixed(0)}%</span>
          <span style={{ color: T.status.danger }}>SELL {(100 - buyPct).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
};

function fmtSigned(v: number, d: number): string { return (v >= 0 ? '+' : '') + v.toFixed(d); }

const Row: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10 }}>
    <span style={{ color: T.text.dim }}>{label}</span>
    <span style={{ color, fontWeight: 600, textShadow: `0 0 4px ${color}20` }}>{value}</span>
  </div>
);

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: `linear-gradient(180deg, ${T.bg.panel} 0%, ${T.bg.surface} 100%)`,
    border: `1px solid ${T.border.mid}`,
    borderRadius: 6,
    padding: '10px 12px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  title: { fontSize: 9, fontWeight: 700, color: T.green.primary, letterSpacing: 2, marginBottom: 8, textShadow: `0 0 8px ${T.green.glow}` },
  price: {
    fontSize: 22, fontWeight: 700, color: T.text.bright,
    textShadow: `0 0 16px ${T.green.glow}`,
    letterSpacing: 1,
  },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px 12px' },
  divider: { height: 1, background: T.border.dim, margin: '8px 0' },
  volBar: { display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', background: T.border.dim },
  volBuy: { background: `linear-gradient(90deg, ${T.green.dim}, ${T.green.primary})`, transition: 'width 0.3s', boxShadow: `0 0 6px ${T.green.glow}` },
  volSell: { background: `linear-gradient(90deg, ${T.status.danger}, #cc4444)`, transition: 'width 0.3s' },
  volPcts: { display: 'flex', justifyContent: 'space-between', fontSize: 8, marginTop: 3 },
};
