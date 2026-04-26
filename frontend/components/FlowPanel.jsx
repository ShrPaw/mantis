import { formatDelta, formatPct, formatVol, formatPrice } from '../utils/format'

export default function FlowPanel({ flow }) {
  const deltaColor = (v) => (v ?? 0) >= 0 ? '#00e676' : '#ff1744'

  return (
    <div style={styles.panel}>
      <div style={styles.section}>
        <div style={styles.sectionTitle}>ORDER FLOW</div>

        <Metric label="Taker Buy" value={formatVol(flow.taker_buy_vol)} color="#00e676" />
        <Metric label="Taker Sell" value={formatVol(flow.taker_sell_vol)} color="#ff1744" />

        <div style={styles.separator} />

        <Metric label="Delta" value={formatDelta(flow.delta)} color={deltaColor(flow.delta)} />
        <Metric label="Cum Delta" value={formatDelta(flow.cum_delta)} color={deltaColor(flow.cum_delta)} />

        <div style={styles.separator} />

        <Metric label="Imbalance" value={formatPct(flow.imbalance ?? 0)} color={deltaColor(flow.imbalance)} />
        <Metric label="Trades" value={flow.trade_count ?? 0} />
        <Metric label="Freq" value={(flow.trade_frequency ?? 0).toFixed(1) + '/s'} />
      </div>

      <div style={styles.section}>
        <div style={styles.sectionTitle}>SESSION</div>
        <Metric label="VWAP" value={formatPrice(flow.vwap)} color="#f0b90b" />
        <Metric label="High" value={formatPrice(flow.session_high)} color="#00e676" />
        <Metric label="Low" value={formatPrice(flow.session_low)} color="#ff1744" />
      </div>

      {/* Delta Bar Visualization */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>DELTA BAR</div>
        <DeltaBar buy={flow.taker_buy_vol ?? 0} sell={flow.taker_sell_vol ?? 0} />
      </div>

      {/* Cumulative Delta Spark */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>CUMULATIVE DELTA</div>
        <div style={{
          ...styles.cumDeltaVal,
          color: deltaColor(flow.cum_delta),
        }}>
          {formatDelta(flow.cum_delta)}
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value, color }) {
  return (
    <div style={styles.metric}>
      <span style={styles.metricLabel}>{label}</span>
      <span style={{ ...styles.metricValue, color: color || '#e0e0e0' }}>{value}</span>
    </div>
  )
}

function DeltaBar({ buy, sell }) {
  const total = buy + sell || 1
  const buyPct = (buy / total * 100).toFixed(1)
  const sellPct = (sell / total * 100).toFixed(1)
  return (
    <div>
      <div style={styles.deltaBarOuter}>
        <div style={{ ...styles.deltaBarBuy, width: buyPct + '%' }} />
        <div style={{ ...styles.deltaBarSell, width: sellPct + '%' }} />
      </div>
      <div style={styles.deltaBarLabels}>
        <span style={{ color: '#00e676' }}>{buyPct}%</span>
        <span style={{ color: '#ff1744' }}>{sellPct}%</span>
      </div>
    </div>
  )
}

const styles = {
  panel: { padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 4 },
  section: { marginBottom: 12 },
  sectionTitle: {
    fontSize: 9, color: '#555', letterSpacing: 2, marginBottom: 6,
    borderBottom: '1px solid #1a1a2e', paddingBottom: 4,
  },
  separator: { height: 1, background: '#1a1a2e', margin: '4px 0' },
  metric: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '2px 0', fontSize: 11,
  },
  metricLabel: { color: '#666', fontSize: 10 },
  metricValue: { fontWeight: 600, fontVariantNumeric: 'tabular-nums' },
  deltaBarOuter: { display: 'flex', height: 6, borderRadius: 3, overflow: 'hidden', marginTop: 4 },
  deltaBarBuy: { background: '#00e676', transition: 'width 0.2s' },
  deltaBarSell: { background: '#ff1744', transition: 'width 0.2s' },
  deltaBarLabels: { display: 'flex', justifyContent: 'space-between', fontSize: 9, marginTop: 2 },
  cumDeltaVal: {
    fontSize: 24, fontWeight: 700, textAlign: 'center', padding: '8px 0',
    fontVariantNumeric: 'tabular-nums',
  },
}
