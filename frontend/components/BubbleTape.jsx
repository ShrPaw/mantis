import { formatPrice, formatVol, timeAgo } from '../utils/format'

export default function BubbleTape({ trades }) {
  return (
    <div style={styles.panel}>
      <div style={styles.title}>LARGE TRADES</div>
      <div style={styles.list}>
        {trades.length === 0 && (
          <div style={styles.empty}>Waiting for large trades...</div>
        )}
        {trades.map((t, i) => (
          <BubbleRow key={i} trade={t} />
        ))}
      </div>
    </div>
  )
}

function BubbleRow({ trade }) {
  const isBuy = trade.side === 'buy'
  const size = Math.min(Math.max(trade.qty / 5, 0.4), 1) // scale 0.4–1
  return (
    <div style={styles.row}>
      <div style={{
        ...styles.bubble,
        width: size * 40,
        height: size * 40,
        background: isBuy ? 'rgba(0,230,118,0.15)' : 'rgba(255,23,68,0.15)',
        border: `2px solid ${isBuy ? '#00e676' : '#ff1744'}`,
      }}>
        <span style={{ color: isBuy ? '#00e676' : '#ff1744', fontSize: 9, fontWeight: 700 }}>
          {trade.qty?.toFixed(2)}
        </span>
      </div>
      <div style={styles.info}>
        <div style={styles.priceRow}>
          <span style={{ color: isBuy ? '#00e676' : '#ff1744', fontWeight: 600 }}>
            {isBuy ? '▲ BUY' : '▼ SELL'}
          </span>
          <span style={styles.price}>{formatPrice(trade.price)}</span>
        </div>
        <div style={styles.meta}>
          <span>{formatVol(trade.qty)} BTC</span>
          <span>${trade.value_usd?.toLocaleString()}</span>
        </div>
      </div>
    </div>
  )
}

const styles = {
  panel: { padding: '8px 12px', height: '100%', display: 'flex', flexDirection: 'column' },
  title: {
    fontSize: 9, color: '#555', letterSpacing: 2, marginBottom: 8,
    borderBottom: '1px solid #1a1a2e', paddingBottom: 4, flexShrink: 0,
  },
  list: { flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 4 },
  empty: { color: '#333', fontSize: 11, textAlign: 'center', padding: 20 },
  row: { display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' },
  bubble: {
    borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0,
  },
  info: { flex: 1, minWidth: 0 },
  priceRow: { display: 'flex', justifyContent: 'space-between', fontSize: 11 },
  price: { color: '#e0e0e0', fontWeight: 600, fontVariantNumeric: 'tabular-nums' },
  meta: { display: 'flex', gap: 8, fontSize: 9, color: '#555', marginTop: 2 },
}
