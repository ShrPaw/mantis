// MANTIS Dashboard — Live Trade Tape
import { useStore } from '../store';
import { formatPrice, formatVol, formatUSD, formatTime } from '../services/format';

export function TradeTape() {
  const tradeTape = useStore(s => s.tradeTape);

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.title}>TRADE TAPE</span>
          <span style={styles.subtitle}>large trades only (≥0.5 BTC)</span>
        </div>
        <span style={styles.liveIndicator}>● LIVE</span>
      </div>
      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>TIME</th>
              <th style={styles.th}>SIDE</th>
              <th style={styles.thRight}>PRICE</th>
              <th style={styles.thRight}>SIZE (BTC)</th>
              <th style={styles.thRight}>VALUE</th>
            </tr>
          </thead>
          <tbody>
            {tradeTape.length === 0 && (
              <tr>
                <td colSpan={5} style={styles.empty}>Waiting for large trades...</td>
              </tr>
            )}
            {tradeTape.map((t, i) => {
              const isBuy = t.side === 'buy';
              const color = isBuy ? '#26a69a' : '#ef5350';
              return (
                <tr key={`${t.timestamp}-${i}`} style={styles.tr}>
                  <td style={styles.td}>{formatTime(t.timestamp)}</td>
                  <td style={{ ...styles.td, color, fontWeight: 700 }}>
                    {isBuy ? 'BUY' : 'SELL'}
                  </td>
                  <td style={{ ...styles.tdRight, color: '#e0e0e0', fontWeight: 600 }}>
                    {formatPrice(t.price)}
                  </td>
                  <td style={{ ...styles.tdRight, color }}>
                    {formatVol(t.qty)}
                  </td>
                  <td style={{ ...styles.tdRight, color: '#aaa' }}>
                    {formatUSD(t.value_usd)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '5px 10px',
    borderBottom: '1px solid #1a1a2e',
    flexShrink: 0,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 8,
  },
  title: {
    fontSize: 8,
    color: '#666',
    letterSpacing: 2,
    fontWeight: 600,
  },
  subtitle: {
    fontSize: 7,
    color: '#444',
  },
  liveIndicator: {
    fontSize: 8,
    color: '#26a69a',
    fontWeight: 600,
  },
  tableWrapper: {
    flex: 1,
    overflow: 'auto',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontSize: 10,
  },
  th: {
    fontSize: 7,
    color: '#555',
    letterSpacing: 1,
    padding: '4px 8px',
    textAlign: 'left' as const,
    borderBottom: '1px solid #1a1a2e',
    position: 'sticky' as const,
    top: 0,
    background: '#0d0d14',
    fontWeight: 600,
  },
  thRight: {
    fontSize: 7,
    color: '#555',
    letterSpacing: 1,
    padding: '4px 8px',
    textAlign: 'right' as const,
    borderBottom: '1px solid #1a1a2e',
    position: 'sticky' as const,
    top: 0,
    background: '#0d0d14',
    fontWeight: 600,
  },
  tr: {
    borderBottom: '1px solid #111118',
  },
  td: {
    padding: '3px 8px',
    color: '#888',
    whiteSpace: 'nowrap' as const,
  },
  tdRight: {
    padding: '3px 8px',
    textAlign: 'right' as const,
    fontVariantNumeric: 'tabular-nums' as const,
    whiteSpace: 'nowrap' as const,
  },
  empty: {
    color: '#444',
    fontSize: 10,
    textAlign: 'center' as const,
    padding: 12,
  },
};
