// MANTIS Operator Dashboard — Live Metrics Panel
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';

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

      <div style={S.priceRow}>
        <span style={S.price}>
          {market?.last_price ? `$${market.last_price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
        </span>
      </div>

      <div style={S.grid}>
        <Row label="Delta" value={market?.delta != null ? formatSigned(market.delta, 3) : '—'} color={(market?.delta ?? 0) >= 0 ? '#26a69a' : '#ef5350'} />
        <Row label="Cum Delta" value={market?.cum_delta != null ? formatSigned(market.cum_delta, 3) : '—'} color={(market?.cum_delta ?? 0) >= 0 ? '#26a69a' : '#ef5350'} />
        <Row label="Buy Vol" value={buyVol > 0 ? buyVol.toFixed(3) : '—'} color="#26a69a" />
        <Row label="Sell Vol" value={sellVol > 0 ? sellVol.toFixed(3) : '—'} color="#ef5350" />
        <Row label="Frequency" value={market?.trade_frequency ? `${market.trade_frequency.toFixed(1)}/s` : '—'} color="#ccc" />
        <Row label="Imbalance" value={market?.imbalance != null ? `${(market.imbalance * 100).toFixed(1)}%` : '—'} color={(market?.imbalance ?? 0) >= 0 ? '#26a69a' : '#ef5350'} />
        <Row label="Candles" value={backend?.candles_loaded?.toString() ?? '—'} color="#ccc" />
        <Row label="Clients" value={backend?.clients?.toString() ?? '—'} color="#ccc" />
      </div>

      <div style={S.divider} />

      {/* Volume bar */}
      <div style={S.volSection}>
        <div style={S.volLabel}>Volume Split</div>
        <div style={S.volBar}>
          <div style={{ ...S.volBuy, width: `${buyPct}%` }} />
          <div style={{ ...S.volSell, width: `${100 - buyPct}%` }} />
        </div>
        <div style={S.volPcts}>
          <span style={{ color: '#26a69a' }}>BUY {buyPct.toFixed(0)}%</span>
          <span style={{ color: '#ef5350' }}>SELL {(100 - buyPct).toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
};

function formatSigned(v: number, decimals: number): string {
  const sign = v >= 0 ? '+' : '';
  return sign + v.toFixed(decimals);
}

const Row: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10 }}>
    <span style={{ color: '#555' }}>{label}</span>
    <span style={{ color, fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{value}</span>
  </div>
);

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: '#0c0c14',
    border: '1px solid #1a1a2e',
    borderRadius: 6,
    padding: '10px 12px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
  },
  title: {
    fontSize: 10,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 2,
    marginBottom: 8,
  },
  priceRow: {
    marginBottom: 8,
    textAlign: 'center' as const,
  },
  price: {
    fontSize: 22,
    fontWeight: 700,
    color: '#fff',
    fontFamily: "'JetBrains Mono', monospace",
    letterSpacing: 1,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '3px 12px',
  },
  divider: {
    height: 1,
    background: '#1a1a2e',
    margin: '8px 0',
  },
  volSection: {
    marginTop: 'auto',
  },
  volLabel: {
    fontSize: 8,
    color: '#555',
    letterSpacing: 1,
    marginBottom: 4,
  },
  volBar: {
    display: 'flex',
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
    background: '#1a1a2e',
  },
  volBuy: {
    background: '#26a69a',
    transition: 'width 0.3s ease',
  },
  volSell: {
    background: '#ef5350',
    transition: 'width 0.3s ease',
  },
  volPcts: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 8,
    marginTop: 3,
    fontFamily: "'JetBrains Mono', monospace",
  },
};
