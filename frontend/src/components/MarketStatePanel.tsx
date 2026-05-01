// MANTIS Operator Dashboard — Market State Panel
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';

function classifyRegime(market: any, spe: any): { regime: string; color: string; explanation: string } {
  const freq = market?.trade_frequency ?? 0;
  const state = spe?.current_state ?? 'IDLE';

  if (state === 'CASCADE') return { regime: 'CASCADE', color: '#ef5350', explanation: 'Forced directional move detected — liquidation cascade in progress' };
  if (state === 'UNWIND') return { regime: 'UNWIND', color: '#ff9800', explanation: 'Forced position closure — funding extreme + OI declining' };

  if (freq > 5) return { regime: 'HIGH_VOLUME', color: '#26a69a', explanation: 'Elevated trade frequency — active market' };
  if (freq < 1) return { regime: 'LOW_VOLUME', color: '#555', explanation: 'Low trade frequency — quiet market' };

  return { regime: 'IDLE', color: '#555', explanation: 'Market is idle — no structural pressure context' };
}

function getBlockReason(spe: any): string {
  if (!spe?.enabled) return 'SPE module disabled';
  const lc = spe?.layer_counts ?? {};
  const l1 = lc['L1_context_gate'];
  if (l1 && l1.fail > 0 && l1.pass === 0) return 'L1 blocked — no CASCADE/UNWIND state';
  const l2 = lc['L2_pressure'];
  if (l2 && l2.fail > 0 && l2.pass === 0) return 'L2 blocked — no crowd pressure detected';
  const l3 = lc['L3_displacement'];
  if (l3 && l3.fail > 0 && l3.pass === 0) return 'L3 blocked — no displacement confirmed';
  if (spe.current_state === 'IDLE') return 'L1 blocked — market is IDLE';
  return 'Waiting for structural conditions';
}

export const MarketStatePanel: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const market = status?.market;
  const spe = status?.spe;
  const { regime, color, explanation } = classifyRegime(market, spe);
  const blockReason = getBlockReason(spe);

  return (
    <div style={S.panel}>
      <div style={S.title}>MARKET STATE</div>

      <div style={S.stateRow}>
        <span style={{ ...S.regimeBadge, color, borderColor: color + '40', background: color + '15' }}>{regime}</span>
        <span style={S.speState}>
          SPE: <span style={{ color: spe?.current_state === 'IDLE' ? '#555' : '#ff9800' }}>{spe?.current_state ?? 'IDLE'}</span>
        </span>
      </div>

      <div style={S.explanation}>{explanation}</div>

      <div style={S.divider} />

      <div style={S.detailGrid}>
        <Detail label="Price" value={market?.last_price ? `$${market.last_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'} />
        <Detail label="VWAP" value={market?.vwap ? `$${market.vwap.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'} />
        <Detail label="Session H/L" value={market ? `$${market.session_high?.toLocaleString()} / $${market.session_low?.toLocaleString()}` : '—'} />
        <Detail label="Frequency" value={market?.trade_frequency ? `${market.trade_frequency.toFixed(1)}/s` : '—'} />
        <Detail label="Imbalance" value={market?.imbalance != null ? `${(market.imbalance * 100).toFixed(1)}%` : '—'} />
        <Detail label="Spread" value="N/A" />
      </div>

      <div style={S.divider} />

      <div style={S.blockReason}>
        <span style={{ color: '#666', fontSize: 9 }}>SPE status: </span>
        <span style={{ color: '#888', fontSize: 10 }}>{blockReason}</span>
      </div>

      {spe?.raw_evaluations === 0 && (
        <div style={S.silentNotice}>
          System silent by design. No valid high-pressure context.
        </div>
      )}
    </div>
  );
};

const Detail: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10 }}>
    <span style={{ color: '#555' }}>{label}</span>
    <span style={{ color: '#ccc', fontWeight: 500 }}>{value}</span>
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
  stateRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 6,
  },
  regimeBadge: {
    fontSize: 12,
    fontWeight: 700,
    padding: '3px 10px',
    borderRadius: 4,
    border: '1px solid',
    letterSpacing: 1,
  },
  speState: {
    fontSize: 10,
    color: '#888',
    fontFamily: "'JetBrains Mono', monospace",
  },
  explanation: {
    fontSize: 10,
    color: '#777',
    lineHeight: 1.4,
  },
  divider: {
    height: 1,
    background: '#1a1a2e',
    margin: '8px 0',
  },
  detailGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '4px 16px',
  },
  blockReason: {
    padding: '4px 8px',
    background: '#111',
    borderRadius: 4,
    border: '1px solid #1a1a2e',
  },
  silentNotice: {
    marginTop: 6,
    padding: '6px 8px',
    background: '#f0b90b08',
    border: '1px solid #f0b90b20',
    borderRadius: 4,
    fontSize: 10,
    color: '#f0b90b',
    textAlign: 'center',
    fontStyle: 'italic',
  },
};
