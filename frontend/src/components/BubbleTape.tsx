// MANTIS Dashboard — Large Trade Bubble Tape
import { useStore } from '../store';
import { formatPrice, formatVol, formatUSD, formatTime, timeAgo } from '../services/format';

export function BubbleTape() {
  const largeTrades = useStore(s => s.largeTrades);

  return (
    <div style={styles.panel}>
      <div style={styles.title}>
        <span>LARGE TRADES (≥0.5 BTC)</span>
        <span style={styles.count}>{largeTrades.length}</span>
      </div>

      {/* Size legend */}
      <div style={styles.legend}>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendBubble, width: 10, height: 10 }} />
          <span>0.5</span>
        </span>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendBubble, width: 16, height: 16 }} />
          <span>2.0</span>
        </span>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendBubble, width: 22, height: 22 }} />
          <span>5.0+</span>
        </span>
        <span style={styles.legendSep}>|</span>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendDot, background: '#26a69a' }} />
          <span>Buy</span>
        </span>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendDot, background: '#ef5350' }} />
          <span>Sell</span>
        </span>
      </div>

      <div style={styles.list}>
        {largeTrades.length === 0 && (
          <div style={styles.empty}>Waiting for large trades...</div>
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
  const color = isBuy ? '#26a69a' : '#ef5350';
  // Scale: 0.5 BTC → 0.3, 5+ BTC → 1.0
  const size = Math.min(Math.max((trade.qty - 0.5) / 4.5, 0.25), 1);
  const bubbleSize = 14 + size * 26;

  const tooltip = [
    `${isBuy ? 'BUY' : 'SELL'} ${trade.qty?.toFixed(4)} BTC`,
    `@ ${formatPrice(trade.price)}`,
    `${formatUSD(trade.value_usd)}`,
    `${formatTime(trade.timestamp)}`,
  ].join(' | ');

  return (
    <div style={styles.row} title={tooltip}>
      <div style={{
        ...styles.bubble,
        width: bubbleSize,
        height: bubbleSize,
        background: `${color}18`,
        border: `2px solid ${color}`,
        boxShadow: `0 0 ${size * 12}px ${color}30`,
      }}>
        <span style={{ color, fontSize: size > 0.5 ? 9 : 7, fontWeight: 700 }}>
          {trade.qty?.toFixed(2)}
        </span>
      </div>
      <div style={styles.info}>
        <div style={styles.priceRow}>
          <span style={{ color, fontWeight: 700, fontSize: 10 }}>
            {isBuy ? '▲ BUY' : '▼ SELL'}
          </span>
          <span style={styles.price}>{formatPrice(trade.price)}</span>
        </div>
        <div style={styles.meta}>
          <span style={{ color: '#888' }}>{formatVol(trade.qty)} BTC</span>
          <span style={{ color: '#aaa', fontWeight: 500 }}>{formatUSD(trade.value_usd)}</span>
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
    fontSize: 9,
    color: '#555',
    letterSpacing: 1,
    marginBottom: 4,
    borderBottom: '1px solid #1a1a2e',
    paddingBottom: 3,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexShrink: 0,
  },
  count: {
    fontSize: 8,
    color: '#888',
    background: '#1a1a2e',
    padding: '1px 6px',
    borderRadius: 3,
    fontWeight: 600,
  },
  legend: {
    display: 'flex',
    gap: 8,
    alignItems: 'center',
    padding: '3px 0 5px',
    borderBottom: '1px solid #111118',
    marginBottom: 4,
    flexShrink: 0,
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 3,
    fontSize: 7,
    color: '#555',
  },
  legendBubble: {
    borderRadius: '50%',
    border: '1px solid #555',
    display: 'inline-block',
    flexShrink: 0,
  },
  legendDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    display: 'inline-block',
  },
  legendSep: {
    color: '#222',
    fontSize: 10,
  },
  list: {
    flex: 1,
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 2,
  },
  empty: {
    color: '#444',
    fontSize: 10,
    textAlign: 'center' as const,
    padding: 20,
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '4px 0',
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
    gap: 8,
    fontSize: 8,
    marginTop: 2,
  },
};
