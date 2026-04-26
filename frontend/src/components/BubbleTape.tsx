// MANTIS Dashboard — Large Trade Bubble Tape
import { useStore } from '../store';
import { formatPrice, formatVol, formatUSD, timeAgo } from '../services/format';

export function BubbleTape() {
  const largeTrades = useStore(s => s.largeTrades);

  return (
    <div style={styles.panel}>
      <div style={styles.title}>
        <span>LARGE TRADES</span>
        <span style={styles.count}>{largeTrades.length}</span>
      </div>
      <div style={styles.list}>
        {largeTrades.length === 0 && (
          <div style={styles.empty}>Waiting for large trades (≥0.5 BTC)...</div>
        )}
        {largeTrades.map((t, i) => (
          <BubbleRow key={`${t.timestamp}-${i}`} trade={t} />
        ))}
      </div>
    </div>
  );
}

function BubbleRow({ trade }: { trade: any }) {
  const isBuy = trade.side === 'buy';
  const size = Math.min(Math.max(trade.qty / 5, 0.35), 1);
  const bubbleSize = size * 36;

  return (
    <div style={styles.row}>
      <div style={{
        ...styles.bubble,
        width: bubbleSize,
        height: bubbleSize,
        background: isBuy ? 'rgba(0,230,118,0.12)' : 'rgba(255,23,68,0.12)',
        border: `2px solid ${isBuy ? '#00e676' : '#ff1744'}`,
        boxShadow: `0 0 8px ${isBuy ? 'rgba(0,230,118,0.2)' : 'rgba(255,23,68,0.2)'}`,
      }}>
        <span style={{
          color: isBuy ? '#00e676' : '#ff1744',
          fontSize: 8,
          fontWeight: 700,
        }}>
          {trade.qty?.toFixed(2)}
        </span>
      </div>
      <div style={styles.info}>
        <div style={styles.priceRow}>
          <span style={{
            color: isBuy ? '#00e676' : '#ff1744',
            fontWeight: 600,
            fontSize: 10,
          }}>
            {isBuy ? '▲ BUY' : '▼ SELL'}
          </span>
          <span style={styles.price}>{formatPrice(trade.price)}</span>
        </div>
        <div style={styles.meta}>
          <span>{formatVol(trade.qty)} BTC</span>
          <span>{formatUSD(trade.value_usd)}</span>
          <span style={{ color: '#444' }}>{timeAgo(trade.timestamp)}</span>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    padding: '6px 10px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
  },
  title: {
    fontSize: 8,
    color: '#444',
    letterSpacing: 2,
    marginBottom: 6,
    borderBottom: '1px solid #1a1a2e',
    paddingBottom: 3,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexShrink: 0,
  },
  count: {
    fontSize: 8,
    color: '#555',
    background: '#1a1a2e',
    padding: '1px 5px',
    borderRadius: 2,
  },
  list: {
    flex: 1,
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 3,
  },
  empty: {
    color: '#333',
    fontSize: 10,
    textAlign: 'center' as const,
    padding: 20,
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '3px 0',
    borderBottom: '1px solid #111118',
  },
  bubble: {
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    transition: 'all 0.3s',
  },
  info: {
    flex: 1,
    minWidth: 0,
  },
  priceRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  price: {
    color: '#e0e0e0',
    fontWeight: 600,
    fontVariantNumeric: 'tabular-nums' as const,
    fontSize: 10,
  },
  meta: {
    display: 'flex',
    gap: 6,
    fontSize: 8,
    color: '#555',
    marginTop: 1,
  },
};
