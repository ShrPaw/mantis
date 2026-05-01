// MANTIS Operator Dashboard — Market State Panel (redesigned)
// Shows market regime, SPE state, and explicit "what to do" actions
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

function classifyRegime(market: any, spe: any): { regime: string; color: string; explanation: string } {
  const freq = market?.trade_frequency ?? 0;
  const state = spe?.current_state ?? 'IDLE';
  if (state === 'CASCADE') return { regime: 'CASCADE', color: T.status.danger, explanation: 'Forced directional move — liquidation cascade in progress' };
  if (state === 'UNWIND') return { regime: 'UNWIND', color: T.status.warning, explanation: 'Forced position closure — funding extreme + OI declining' };
  if (freq > 5) return { regime: 'HIGH_VOLUME', color: T.green.primary, explanation: 'Elevated trade frequency — active market' };
  if (freq < 1) return { regime: 'LOW_VOLUME', color: T.text.muted, explanation: 'Low trade frequency — quiet market' };
  return { regime: 'IDLE', color: T.text.dim, explanation: 'Market is idle — no structural pressure context' };
}

function getWhatToDo(spe: any): { text: string; color: string } {
  const raw = spe?.raw_evaluations ?? 0;
  const full8 = spe?.full_8_layer_passes ?? 0;
  const currentState = spe?.current_state ?? 'IDLE';

  if (full8 > 0 && (currentState === 'CASCADE' || currentState === 'UNWIND')) {
    return { text: 'Candidate detected — review manually', color: T.green.primary };
  }
  if (raw > 0 && (currentState === 'CASCADE' || currentState === 'UNWIND')) {
    return { text: 'Wait for pressure — observing structural conditions', color: T.status.warning };
  }
  if (raw === 0) {
    return { text: 'Market idle — observe only', color: T.text.muted };
  }
  return { text: 'Context invalid — observe only', color: T.text.dim };
}

export const MarketStatePanel: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const market = status?.market;
  const spe = status?.spe;
  const { regime, color, explanation } = classifyRegime(market, spe);
  const whatToDo = getWhatToDo(spe);

  return (
    <div style={S.panel}>
      <div style={S.title}>MARKET STATE</div>
      <div style={S.stateRow}>
        <span style={{ ...S.regimeBadge, color, borderColor: color + '40', background: color + '12', textShadow: `0 0 8px ${color}40` }}>{regime}</span>
        <span style={{ color: T.text.dim, fontSize: 10 }}>
          SPE: <span style={{ color: spe?.current_state === 'IDLE' ? T.text.muted : T.status.warning }}>{spe?.current_state ?? 'IDLE'}</span>
        </span>
      </div>
      <div style={S.explanation}>{explanation}</div>

      {/* What to do */}
      <div style={S.actionBox}>
        <span style={S.actionLabel}>WHAT TO DO</span>
        <span style={{ ...S.actionText, color: whatToDo.color }}>{whatToDo.text}</span>
      </div>

      <div style={S.divider} />
      <div style={S.detailGrid}>
        <Detail label="Price" value={market?.last_price ? `$${market.last_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'} />
        <Detail label="VWAP" value={market?.vwap ? `$${market.vwap.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'} />
        <Detail label="Session H/L" value={market ? `$${market.session_high?.toLocaleString()} / $${market.session_low?.toLocaleString()}` : '—'} />
        <Detail label="Frequency" value={market?.trade_frequency ? `${market.trade_frequency.toFixed(1)}/s` : '—'} />
        <Detail label="Imbalance" value={market?.imbalance != null ? `${(market.imbalance * 100).toFixed(1)}%` : '—'} />
        <Detail label="Delta" value={market?.delta != null ? `${market.delta >= 0 ? '+' : ''}${market.delta.toFixed(3)}` : '—'} />
      </div>
    </div>
  );
};

const Detail: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10 }}>
    <span style={{ color: T.text.dim }}>{label}</span>
    <span style={{ color: T.text.main, fontWeight: 500 }}>{value}</span>
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
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03), ${T.border.dim} 0 2px 8px rgba(0,0,0,0.3)`,
  },
  title: {
    fontSize: 9,
    fontWeight: 700,
    color: T.green.primary,
    letterSpacing: 2,
    marginBottom: 8,
    textShadow: `0 0 8px ${T.green.glow}`,
  },
  stateRow: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 },
  regimeBadge: {
    fontSize: 11,
    fontWeight: 700,
    padding: '3px 10px',
    borderRadius: 4,
    border: '1px solid',
    letterSpacing: 1,
  },
  explanation: { fontSize: 10, color: T.text.dim, lineHeight: 1.4, marginBottom: 8 },
  actionBox: {
    padding: '6px 8px',
    background: T.bg.card,
    borderRadius: 4,
    border: `1px solid ${T.border.bright}`,
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    marginBottom: 4,
  },
  actionLabel: {
    fontSize: 7,
    color: T.text.muted,
    letterSpacing: 1,
    fontWeight: 700,
  },
  actionText: {
    fontSize: 10,
    fontWeight: 600,
  },
  divider: { height: 1, background: T.border.dim, margin: '6px 0' },
  detailGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px 14px' },
};
