// MANTIS Dashboard — Order Flow Panel
import { useStore } from '../store';
import { formatDelta, formatPct, formatVol, formatPrice } from '../services/format';

export function FlowPanel() {
  const flow = useStore(s => s.flow);
  const deltaColor = (v: number | undefined) => (v ?? 0) >= 0 ? '#26a69a' : '#ef5350';

  const buyPct = flow.taker_buy_vol && flow.taker_sell_vol
    ? (flow.taker_buy_vol / (flow.taker_buy_vol + flow.taker_sell_vol) * 100)
    : 50;
  const sellPct = 100 - buyPct;

  return (
    <div style={styles.panel}>
      {/* Order Flow Section */}
      <Section title="ORDER FLOW" hint="Taker aggression">
        <Metric label="Taker Buy" value={formatVol(flow.taker_buy_vol)} color="#26a69a" hint="aggressive buys" />
        <Metric label="Taker Sell" value={formatVol(flow.taker_sell_vol)} color="#ef5350" hint="aggressive sells" />
        <div style={styles.separator} />
        <Metric label="Delta" value={formatDelta(flow.delta)} color={deltaColor(flow.delta)} hint="buy − sell" />
        <Metric label="Cum Delta" value={formatDelta(flow.cum_delta)} color={deltaColor(flow.cum_delta)} hint="running total" />
        <div style={styles.separator} />
        <Metric label="Imbalance" value={formatPct(flow.imbalance ?? 0)} color={deltaColor(flow.imbalance)} hint="bias strength" />
        <Metric label="Trades" value={String(flow.trade_count ?? 0)} />
        <Metric label="Freq" value={(flow.trade_frequency ?? 0).toFixed(1) + '/s'} hint="trades per sec" />
      </Section>

      {/* Session Stats */}
      <Section title="SESSION" hint="Since start">
        <Metric label="VWAP" value={formatPrice(flow.vwap)} color="#f0b90b" hint="volume-weighted avg" />
        <Metric label="High" value={formatPrice(flow.session_high)} color="#26a69a" />
        <Metric label="Low" value={formatPrice(flow.session_low)} color="#ef5350" />
      </Section>

      {/* Delta Bar */}
      <Section title="VOLUME SPLIT">
        <div style={styles.barOuter}>
          <div style={{ ...styles.barBuy, width: `${buyPct}%` }} />
          <div style={{ ...styles.barSell, width: `${sellPct}%` }} />
        </div>
        <div style={styles.barLabels}>
          <span style={{ color: '#26a69a' }}>Buy {buyPct.toFixed(1)}%</span>
          <span style={{ color: '#ef5350' }}>Sell {sellPct.toFixed(1)}%</span>
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
        <div style={styles.directionIndicator}>
          {(flow.cum_delta ?? 0) > 0 ? (
            <span style={{ color: '#26a69a', fontSize: 18 }}>▲</span>
          ) : (flow.cum_delta ?? 0) < 0 ? (
            <span style={{ color: '#ef5350', fontSize: 18 }}>▼</span>
          ) : (
            <span style={{ color: '#555', fontSize: 18 }}>—</span>
          )}
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children, hint }: { title: string; children: React.ReactNode; hint?: string }) {
  return (
    <div style={styles.section}>
      <div style={styles.sectionTitleRow}>
        <span style={styles.sectionTitle}>{title}</span>
        {hint && <span style={styles.sectionHint}>{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function Metric({ label, value, color, hint }: { label: string; value: string; color?: string; hint?: string }) {
  return (
    <div style={styles.metric}>
      <span style={styles.metricLabel} title={hint}>{label}</span>
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
  sectionTitleRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    borderBottom: '1px solid #1a1a2e',
    paddingBottom: 3,
    marginBottom: 4,
  },
  sectionTitle: {
    fontSize: 8,
    color: '#666',
    letterSpacing: 2,
    textTransform: 'uppercase' as const,
  },
  sectionHint: {
    fontSize: 7,
    color: '#444',
    fontStyle: 'italic' as const,
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
    padding: '2px 0',
    fontSize: 10,
  },
  metricLabel: {
    color: '#777',
    fontSize: 9,
    cursor: 'help',
  },
  metricValue: {
    fontWeight: 600,
    fontVariantNumeric: 'tabular-nums' as const,
    fontSize: 10,
  },
  barOuter: {
    display: 'flex',
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
    marginTop: 3,
  },
  barBuy: {
    background: '#26a69a',
    transition: 'width 0.3s',
  },
  barSell: {
    background: '#ef5350',
    transition: 'width 0.3s',
  },
  barLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 8,
    marginTop: 3,
  },
  cumDeltaVal: {
    fontSize: 24,
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
