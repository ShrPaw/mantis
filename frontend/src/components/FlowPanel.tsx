// MANTIS Dashboard — Order Flow Panel
import { useStore } from '../store';
import { formatDelta, formatPct, formatVol, formatPrice } from '../services/format';

export function FlowPanel() {
  const flow = useStore(s => s.flow);
  const deltaColor = (v: number | undefined) => (v ?? 0) >= 0 ? '#00e676' : '#ff1744';

  const buyPct = flow.taker_buy_vol && flow.taker_sell_vol
    ? (flow.taker_buy_vol / (flow.taker_buy_vol + flow.taker_sell_vol) * 100)
    : 50;
  const sellPct = 100 - buyPct;

  return (
    <div style={styles.panel}>
      {/* Order Flow Section */}
      <Section title="ORDER FLOW">
        <Metric label="Taker Buy" value={formatVol(flow.taker_buy_vol)} color="#00e676" />
        <Metric label="Taker Sell" value={formatVol(flow.taker_sell_vol)} color="#ff1744" />
        <div style={styles.separator} />
        <Metric label="Delta" value={formatDelta(flow.delta)} color={deltaColor(flow.delta)} />
        <Metric label="Cum Delta" value={formatDelta(flow.cum_delta)} color={deltaColor(flow.cum_delta)} />
        <div style={styles.separator} />
        <Metric label="Imbalance" value={formatPct(flow.imbalance ?? 0)} color={deltaColor(flow.imbalance)} />
        <Metric label="Trades" value={String(flow.trade_count ?? 0)} />
        <Metric label="Freq" value={(flow.trade_frequency ?? 0).toFixed(1) + '/s'} />
      </Section>

      {/* Session Stats */}
      <Section title="SESSION">
        <Metric label="VWAP" value={formatPrice(flow.vwap)} color="#f0b90b" />
        <Metric label="High" value={formatPrice(flow.session_high)} color="#00e676" />
        <Metric label="Low" value={formatPrice(flow.session_low)} color="#ff1744" />
      </Section>

      {/* Delta Bar */}
      <Section title="DELTA BAR">
        <div style={styles.barOuter}>
          <div style={{ ...styles.barBuy, width: `${buyPct}%` }} />
          <div style={{ ...styles.barSell, width: `${sellPct}%` }} />
        </div>
        <div style={styles.barLabels}>
          <span style={{ color: '#00e676' }}>{buyPct.toFixed(1)}%</span>
          <span style={{ color: '#ff1744' }}>{sellPct.toFixed(1)}%</span>
        </div>
      </Section>

      {/* Cumulative Delta Visual */}
      <Section title="CUMULATIVE DELTA">
        <div style={{
          ...styles.cumDeltaVal,
          color: deltaColor(flow.cum_delta),
        }}>
          {formatDelta(flow.cum_delta)}
        </div>
        {/* Mini delta direction indicator */}
        <div style={styles.directionIndicator}>
          {(flow.cum_delta ?? 0) > 0 ? (
            <span style={{ color: '#00e676', fontSize: 18 }}>▲</span>
          ) : (flow.cum_delta ?? 0) < 0 ? (
            <span style={{ color: '#ff1744', fontSize: 18 }}>▼</span>
          ) : (
            <span style={{ color: '#555', fontSize: 18 }}>—</span>
          )}
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={styles.section}>
      <div style={styles.sectionTitle}>{title}</div>
      {children}
    </div>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={styles.metric}>
      <span style={styles.metricLabel}>{label}</span>
      <span style={{ ...styles.metricValue, color: color || '#e0e0e0' }}>{value}</span>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    padding: '6px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    flex: 1,
    overflow: 'auto',
  },
  section: {
    marginBottom: 10,
  },
  sectionTitle: {
    fontSize: 8,
    color: '#444',
    letterSpacing: 2,
    marginBottom: 4,
    borderBottom: '1px solid #1a1a2e',
    paddingBottom: 3,
    textTransform: 'uppercase' as const,
  },
  separator: {
    height: 1,
    background: '#1a1a2e',
    margin: '3px 0',
  },
  metric: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '1px 0',
    fontSize: 10,
  },
  metricLabel: {
    color: '#555',
    fontSize: 9,
  },
  metricValue: {
    fontWeight: 600,
    fontVariantNumeric: 'tabular-nums' as const,
    fontSize: 10,
  },
  barOuter: {
    display: 'flex',
    height: 5,
    borderRadius: 2,
    overflow: 'hidden',
    marginTop: 3,
  },
  barBuy: {
    background: '#00e676',
    transition: 'width 0.3s',
  },
  barSell: {
    background: '#ff1744',
    transition: 'width 0.3s',
  },
  barLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 8,
    marginTop: 2,
  },
  cumDeltaVal: {
    fontSize: 22,
    fontWeight: 700,
    textAlign: 'center' as const,
    padding: '6px 0 2px',
    fontVariantNumeric: 'tabular-nums' as const,
  },
  directionIndicator: {
    textAlign: 'center' as const,
    padding: '2px 0',
  },
};
