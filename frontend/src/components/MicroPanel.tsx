// MANTIS Dashboard — Microstructure Analysis Panel
import { useStore } from '../store';
import { formatPrice, formatDelta, formatVol } from '../services/format';

export function MicroPanel() {
  const micro = useStore(s => s.micro);
  const flow = useStore(s => s.flow);

  return (
    <div style={styles.panel}>
      {/* Delta Imbalance */}
      <Section title="DELTA IMBALANCE">
        <div style={styles.imbalanceContainer}>
          <div style={{
            ...styles.imbalanceIndicator,
            background: micro.deltaImbalance.status === 'strong_buy'
              ? '#00e676' : micro.deltaImbalance.status === 'strong_sell'
              ? '#ff1744' : '#333',
            width: `${Math.max(micro.deltaImbalance.strength * 100, 5)}%`,
          }} />
          <div style={styles.imbalanceLabel}>
            {micro.deltaImbalance.status === 'strong_buy' && (
              <span style={{ color: '#00e676' }}>▲ BUY DOMINANCE</span>
            )}
            {micro.deltaImbalance.status === 'strong_sell' && (
              <span style={{ color: '#ff1744' }}>▼ SELL DOMINANCE</span>
            )}
            {micro.deltaImbalance.status === 'neutral' && (
              <span style={{ color: '#555' }}>— BALANCED</span>
            )}
          </div>
          <div style={styles.imbalanceDesc}>{micro.deltaImbalance.description}</div>
        </div>
      </Section>

      {/* Absorption Proxy */}
      <Section title="ABSORPTION ZONES">
        {micro.absorptionProxy.length === 0 ? (
          <div style={styles.empty}>No absorption detected</div>
        ) : (
          micro.absorptionProxy.slice(0, 3).map((a, i) => (
            <div key={i} style={styles.absorptionRow}>
              <span style={styles.absorptionPrice}>{formatPrice(a.price)}</span>
              <span style={styles.absorptionVol}>V:{formatVol(a.volume)}</span>
              <span style={{
                color: Math.abs(a.delta) < 0.1 ? '#f0b90b' : '#555',
                fontSize: 8,
              }}>
                Δ:{formatDelta(a.delta)}
              </span>
            </div>
          ))
        )}
      </Section>

      {/* Liquidity Pulls */}
      <Section title="LIQUIDITY PULLS">
        {micro.liquidityPulls.length === 0 ? (
          <div style={styles.empty}>No recent pulls</div>
        ) : (
          micro.liquidityPulls.slice(0, 3).map((p, i) => (
            <div key={i} style={styles.pullRow}>
              <span style={{
                color: p.side === 'bid' ? '#ff1744' : '#00e676',
                fontSize: 9,
                fontWeight: 600,
              }}>
                {p.side === 'bid' ? '▼ BID' : '▲ ASK'}
              </span>
              <span style={styles.pullPrice}>{formatPrice(p.price)}</span>
              <span style={styles.pullQty}>{formatVol(p.removed_qty)}</span>
            </div>
          ))
        )}
      </Section>

      {/* Breakout Strength */}
      <Section title="BREAKOUT STRENGTH">
        {micro.breakoutStrength.detected ? (
          <div style={styles.breakoutContainer}>
            <div style={{
              ...styles.breakoutDir,
              color: micro.breakoutStrength.direction === 'up' ? '#00e676' : '#ff1744',
            }}>
              {micro.breakoutStrength.direction === 'up' ? '▲ UP' : '▼ DOWN'}
            </div>
            <div style={{
              ...styles.breakoutConf,
              color: micro.breakoutStrength.volume_confirmed ? '#00e676' : '#ff9800',
            }}>
              {micro.breakoutStrength.volume_confirmed ? '● VOL CONFIRMED' : '○ WEAK VOLUME'}
            </div>
          </div>
        ) : (
          <div style={styles.empty}>No breakout detected</div>
        )}
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

const styles: Record<string, React.CSSProperties> = {
  panel: {
    padding: '4px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    borderTop: '1px solid #1a1a2e',
    flexShrink: 0,
  },
  section: {
    marginBottom: 8,
  },
  sectionTitle: {
    fontSize: 7,
    color: '#444',
    letterSpacing: 2,
    marginBottom: 3,
    borderBottom: '1px solid #1a1a2e',
    paddingBottom: 2,
  },
  empty: {
    color: '#333',
    fontSize: 9,
    padding: '2px 0',
  },
  imbalanceContainer: {
    padding: '4px 0',
  },
  imbalanceIndicator: {
    height: 3,
    borderRadius: 1,
    transition: 'all 0.5s',
    marginBottom: 3,
  },
  imbalanceLabel: {
    fontSize: 10,
    fontWeight: 600,
    marginBottom: 1,
  },
  imbalanceDesc: {
    fontSize: 8,
    color: '#555',
  },
  absorptionRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '1px 0',
    fontSize: 9,
  },
  absorptionPrice: {
    color: '#f0b90b',
    fontWeight: 500,
  },
  absorptionVol: {
    color: '#666',
    fontSize: 8,
  },
  pullRow: {
    display: 'flex',
    gap: 6,
    alignItems: 'center',
    padding: '1px 0',
    fontSize: 9,
  },
  pullPrice: {
    color: '#e0e0e0',
    fontSize: 9,
  },
  pullQty: {
    color: '#666',
    fontSize: 8,
  },
  breakoutContainer: {
    padding: '4px 0',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  breakoutDir: {
    fontSize: 12,
    fontWeight: 700,
  },
  breakoutConf: {
    fontSize: 8,
    fontWeight: 600,
  },
};
