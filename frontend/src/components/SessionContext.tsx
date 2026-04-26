// MANTIS Dashboard — Session Context (Asia/London/NY levels)
import { useStore } from '../store';
import { formatPrice } from '../services/format';

interface SessionInfo {
  name: string;
  color: string;
  icon: string;
  active: boolean;
  high: number | null;
  low: number | null;
}

function getSessions(): SessionInfo[] {
  const now = new Date();
  const utcH = now.getUTCHours();
  const utcM = now.getUTCMinutes();
  const utcNow = utcH + utcM / 60;

  // Asia: 00:00-08:00 UTC
  const asiaActive = utcNow >= 0 && utcNow < 8;
  // London: 08:00-16:00 UTC
  const londonActive = utcNow >= 8 && utcNow < 16;
  // NY: 13:00-21:00 UTC
  const nyActive = utcNow >= 13 && utcNow < 21;

  return [
    { name: 'ASIA', color: '#9c27b0', icon: '🌏', active: asiaActive, high: null, low: null },
    { name: 'LONDON', color: '#2196f3', icon: '🇬🇧', active: londonActive, high: null, low: null },
    { name: 'NEW YORK', color: '#ff9800', icon: '🇺🇸', active: nyActive, high: null, low: null },
  ];
}

function getNextSession(): string {
  const now = new Date();
  const utcH = now.getUTCHours();

  if (utcH < 8) {
    const mins = (8 - utcH) * 60 - now.getUTCMinutes();
    return `London in ${Math.floor(mins / 60)}h${mins % 60}m`;
  }
  if (utcH < 13) {
    const mins = (13 - utcH) * 60 - now.getUTCMinutes();
    return `NY in ${Math.floor(mins / 60)}h${mins % 60}m`;
  }
  if (utcH < 21) {
    const mins = (21 - utcH) * 60 - now.getUTCMinutes();
    return `Close in ${Math.floor(mins / 60)}h${mins % 60}m`;
  }
  const mins = (24 - utcH + 8) * 60 - now.getUTCMinutes();
  return `London in ${Math.floor(mins / 60)}h${mins % 60}m`;
}

export function SessionContext() {
  const flow = useStore(s => s.flow);
  const sessions = getSessions();
  const nextSession = getNextSession();

  // Compute session levels from flow data
  // In production these would be computed from historical data
  // For now, we use session high/low as proxy
  const sessionHigh = flow.session_high;
  const sessionLow = flow.session_low;

  return (
    <div style={styles.panel}>
      <div style={styles.title}>SESSIONS</div>

      {/* UTC Clock */}
      <div style={styles.clock}>
        <span style={styles.clockLabel}>UTC</span>
        <span style={styles.clockTime}>
          {new Date().toUTCString().slice(17, 25)}
        </span>
      </div>

      {/* Next session */}
      <div style={styles.nextSession}>{nextSession}</div>

      {/* Session cards */}
      {sessions.map(s => (
        <div key={s.name} style={{
          ...styles.sessionCard,
          borderColor: s.active ? s.color : '#1a1a2e',
          background: s.active ? `${s.color}10` : 'transparent',
        }}>
          <div style={styles.sessionHeader}>
            <span style={{ ...styles.sessionName, color: s.active ? s.color : '#555' }}>
              {s.icon} {s.name}
            </span>
            {s.active && (
              <span style={{ ...styles.activeDot, background: s.color }}>●</span>
            )}
          </div>
        </div>
      ))}

      {/* Session Range */}
      <div style={styles.section}>
        <div style={styles.sectionTitle}>RANGE</div>
        <div style={styles.rangeRow}>
          <span style={{ color: '#00e676', fontSize: 9 }}>H</span>
          <span style={styles.rangeValue}>{formatPrice(sessionHigh)}</span>
        </div>
        <div style={styles.rangeRow}>
          <span style={{ color: '#ff1744', fontSize: 9 }}>L</span>
          <span style={styles.rangeValue}>{formatPrice(sessionLow)}</span>
        </div>
        {sessionHigh > 0 && sessionLow < Infinity && (
          <div style={styles.rangeRow}>
            <span style={{ color: '#555', fontSize: 9 }}>RNG</span>
            <span style={styles.rangeValue}>
              {formatPrice(sessionHigh - sessionLow)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    padding: '8px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  title: {
    fontSize: 8,
    color: '#444',
    letterSpacing: 2,
    marginBottom: 4,
    borderBottom: '1px solid #1a1a2e',
    paddingBottom: 3,
  },
  clock: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '4px 0',
  },
  clockLabel: {
    fontSize: 8,
    color: '#555',
    letterSpacing: 1,
  },
  clockTime: {
    fontSize: 14,
    fontWeight: 700,
    color: '#e0e0e0',
    fontVariantNumeric: 'tabular-nums' as const,
  },
  nextSession: {
    fontSize: 9,
    color: '#f0b90b',
    padding: '2px 0 6px',
    borderBottom: '1px solid #1a1a2e',
  },
  sessionCard: {
    padding: '4px 8px',
    borderRadius: 3,
    border: '1px solid #1a1a2e',
    marginTop: 2,
  },
  sessionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sessionName: {
    fontSize: 9,
    fontWeight: 600,
  },
  activeDot: {
    fontSize: 8,
  },
  section: {
    marginTop: 8,
    borderTop: '1px solid #1a1a2e',
    paddingTop: 6,
  },
  sectionTitle: {
    fontSize: 7,
    color: '#444',
    letterSpacing: 2,
    marginBottom: 4,
  },
  rangeRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '1px 0',
  },
  rangeValue: {
    color: '#e0e0e0',
    fontSize: 10,
    fontWeight: 500,
    fontVariantNumeric: 'tabular-nums' as const,
  },
};
