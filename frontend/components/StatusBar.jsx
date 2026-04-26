import { formatPrice, formatDelta, formatPct, formatVol } from '../utils/format'

export default function StatusBar({ connected, flow }) {
  return (
    <div style={styles.bar}>
      <span style={{
        ...styles.dot,
        background: connected ? '#00e676' : '#ff1744',
      }} />
      <span style={styles.label}>{connected ? 'LIVE' : 'OFFLINE'}</span>
      <span style={styles.sep}>|</span>
      <span style={styles.price}>{formatPrice(flow.last_price)}</span>
      <span style={styles.sep}>|</span>
      <span style={styles.label}>VWAP</span>
      <span style={styles.val}>{formatPrice(flow.vwap)}</span>
      <span style={styles.sep}>|</span>
      <span style={styles.label}>H</span>
      <span style={styles.val}>{formatPrice(flow.session_high)}</span>
      <span style={styles.label}>L</span>
      <span style={styles.val}>{formatPrice(flow.session_low)}</span>
      <span style={styles.sep}>|</span>
      <span style={styles.label}>Δ</span>
      <span style={{
        ...styles.val,
        color: (flow.delta ?? 0) >= 0 ? '#00e676' : '#ff1744',
      }}>{formatDelta(flow.delta)}</span>
      <span style={styles.label}>ΣΔ</span>
      <span style={{
        ...styles.val,
        color: (flow.cum_delta ?? 0) >= 0 ? '#00e676' : '#ff1744',
      }}>{formatDelta(flow.cum_delta)}</span>
      <span style={styles.sep}>|</span>
      <span style={styles.label}>IMB</span>
      <span style={{
        ...styles.val,
        color: (flow.imbalance ?? 0) >= 0 ? '#00e676' : '#ff1744',
      }}>{formatPct(flow.imbalance ?? 0)}</span>
    </div>
  )
}

const styles = {
  bar: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 },
  dot: { width: 8, height: 8, borderRadius: '50%' },
  label: { color: '#666', fontSize: 10, textTransform: 'uppercase' },
  val: { color: '#e0e0e0', fontWeight: 600 },
  price: { color: '#f0b90b', fontWeight: 700, fontSize: 14 },
  sep: { color: '#333' },
}
