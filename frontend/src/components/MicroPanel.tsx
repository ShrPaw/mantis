// MANTIS Dashboard — Microstructure Analysis Panel
import { useStore } from '../store';
import { formatPrice, formatDelta, formatVol } from '../services/format';

export function MicroPanel() {
  const micro = useStore(s => s.micro);

  return (
    <div style={styles.panel}>
      {/* Delta Imbalance */}
      <Section title="DELTA IMBALANCE" hint="Buy vs sell pressure">
        <div style={styles.imbalanceContainer}>
          <div style={styles.imbalanceBarOuter}>
            <div style={{
              ...styles.imbalanceBar,
              background: micro.deltaImbalance.status === 'strong_buy'
                ? '#26a69a' : micro.deltaImbalance.status === 'strong_sell'
                ? '#ef5350' : '#333',
              width: `${Math.max(micro.deltaImbalance.strength * 100, 5)}%`,
            }} />
          </div>
          <div style={styles.imbalanceLabel}>
            {micro.deltaImbalance.status === 'strong_buy' && (
              <span style={{ color: '#26a69a' }}>▲ BUY DOMINANCE</span>
            )}
            {micro.deltaImbalance.status === 'strong_sell' && (
              <span style={{ color: '#ef5350' }}>▼ SELL DOMINANCE</span>
            )}
            {micro.deltaImbalance.status === 'neutral' && (
              <span style={{ color: '#666' }}>— BALANCED</span>
            )}
          </div>
          <div style={styles.imbalanceDesc}>{micro.deltaImbalance.description}</div>
        </div>
      </Section>

      {/* Absorption Proxy */}
      <Section title="ABSORPTION" hint="High vol, low delta">
        {micro.absorptionProxy.length === 0 ? (
          <div style={styles.empty}>None detected</div>
        ) : (
          micro.absorptionProxy.slice(0, 3).map((a, i) => (
            <div key={i} style={styles.absorptionRow}>
              <span style={styles.absorptionPrice}>{formatPrice(a.price)}</span>
              <span style={styles.absorptionVol}>Vol: {formatVol(a.volume)}</span>
              <span style={{
                color: Math.abs(a.delta) < 0.1 ? '#f0b90b' : '#666',
                fontSize: 8,
                fontWeight: Math.abs(a.delta) < 0.1 ? 600 : 400,
              }}>
                Δ {formatDelta(a.delta)}
              </span>
            </div>
          ))
        )}
      </Section>

      {/* Liquidity Pulls */}
      <Section title="LIQUIDITY PULLS" hint="Vanished walls">
        {micro.liquidityPulls.length === 0 ? (
          <div style={styles.empty}>None detected</div>
        ) : (
          micro.liquidityPulls.slice(0, 3).map((p, i) => (
            <div key={i} style={styles.pullRow}>
              <span style={{
                color: p.side === 'bid' ? '#ef5350' : '#26a69a',
                fontSize: 9,
                fontWeight: 700,
              }}>
                {p.side === 'bid' ? '▼ BID' : '▲ ASK'}
              </span>
              <span style={styles.pullPrice}>{formatPrice(p.price)}</span>
              <span style={styles.pullQty}>{formatVol(p.removed_qty)} removed</span>
            </div>
          ))
        )}
      </Section>

      {/* Breakout Strength */}
      <Section title="BREAKOUT" hint="Price at range extreme">
        {micro.breakoutStrength.detected ? (
          <div style={styles.breakoutContainer}>
            <div style={{
              ...styles.breakoutDir,
              color: micro.breakoutStrength.direction === 'up' ? '#26a69a' : '#ef5350',
            }}>
              {micro.breakoutStrength.direction === 'up' ? '▲ UPSIDE' : '▼ DOWNSIDE'}
            </div>
            <div style={{
              ...styles.breakoutConf,
              color: micro.breakoutStrength.volume_confirmed ? '#26a69a' : '#ff9800',
            }}>
              {micro.breakoutStrength.volume_confirmed ? '● Volume confirms' : '○ Weak volume'}
            </div>
          </div>
        ) : (
          <div style={styles.empty}>None detected</div>
        )}
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
  sectionTitleRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    borderBottom: '1px solid #1a1a2e',
    paddingBottom: 2,
    marginBottom: 3,
  },
  sectionTitle: {
    fontSize: 7,
    color: '#666',
    letterSpacing: 2,
  },
  sectionHint: {
    fontSize: 7,
    color: '#444',
    fontStyle: 'italic' as const,
  },
  empty: {
    color: '#444',
    fontSize: 9,
    padding: '2px 0',
  },
  imbalanceContainer: {
    padding: '4px 0',
  },
  imbalanceBarOuter: {
    height: 4,
    borderRadius: 2,
    background: '#1a1a2e',
    overflow: 'hidden',
    marginBottom: 4,
  },
  imbalanceBar: {
    height: '100%',
    borderRadius: 2,
    transition: 'all 0.5s',
  },
  imbalanceLabel: {
    fontSize: 10,
    fontWeight: 600,
    marginBottom: 2,
  },
  imbalanceDesc: {
    fontSize: 8,
    color: '#666',
  },
  absorptionRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '2px 0',
    fontSize: 9,
  },
  absorptionPrice: {
    color: '#f0b90b',
    fontWeight: 600,
  },
  absorptionVol: {
    color: '#888',
    fontSize: 8,
  },
  pullRow: {
    display: 'flex',
    gap: 6,
    alignItems: 'center',
    padding: '2px 0',
    fontSize: 9,
  },
  pullPrice: {
    color: '#e0e0e0',
    fontSize: 9,
  },
  pullQty: {
    color: '#888',
    fontSize: 8,
  },
  breakoutContainer: {
    padding: '4px 0',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  breakoutDir: {
    fontSize: 11,
    fontWeight: 700,
  },
  breakoutConf: {
    fontSize: 8,
    fontWeight: 600,
  },
};
