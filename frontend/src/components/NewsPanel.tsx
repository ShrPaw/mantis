// MANTIS Dashboard — News & Macro Events Panel
import { useState, useEffect } from 'react';

interface NewsEvent {
  title: string;
  time: string;
  timestamp: number;
  impact: 'high' | 'medium';
  category: string;
}

// Static macro events (would be replaced with API in production)
const MACRO_EVENTS: NewsEvent[] = [
  { title: 'FOMC Rate Decision', time: 'TBD', timestamp: 0, impact: 'high', category: 'FED' },
  { title: 'CPI (YoY)', time: 'TBD', timestamp: 0, impact: 'high', category: 'DATA' },
  { title: 'Non-Farm Payrolls', time: 'TBD', timestamp: 0, impact: 'high', category: 'DATA' },
  { title: 'Initial Jobless Claims', time: 'TBD', timestamp: 0, impact: 'medium', category: 'DATA' },
  { title: 'PPI (MoM)', time: 'TBD', timestamp: 0, impact: 'medium', category: 'DATA' },
  { title: 'Retail Sales', time: 'TBD', timestamp: 0, impact: 'medium', category: 'DATA' },
];

function getUpcomingEvents(): NewsEvent[] {
  // In production, this would fetch from an economic calendar API
  // For now, return static list with estimated times
  const now = Date.now();
  return MACRO_EVENTS.map((e, i) => ({
    ...e,
    timestamp: now + (i + 1) * 3600000 * (4 + i * 2),
    time: new Date(now + (i + 1) * 3600000 * (4 + i * 2)).toUTCString().slice(17, 22) + ' UTC',
  }));
}

function getTimeUntil(ts: number): string {
  if (ts <= 0) return 'TBD';
  const diff = ts - Date.now();
  if (diff < 0) return 'NOW';
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 24) return `${Math.floor(h / 24)}d ${h % 24}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export function NewsPanel() {
  const [events, setEvents] = useState<NewsEvent[]>([]);
  const [volZone, setVolZone] = useState(false);

  useEffect(() => {
    setEvents(getUpcomingEvents());
    const interval = setInterval(() => {
      setEvents(getUpcomingEvents());
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  // Check if any high-impact event is within 1 hour
  useEffect(() => {
    const soon = events.some(e =>
      e.impact === 'high' && e.timestamp > 0 && (e.timestamp - Date.now()) < 3600000
    );
    setVolZone(soon);
  }, [events]);

  return (
    <div style={styles.panel}>
      <div style={styles.title}>
        <span>MACRO EVENTS</span>
        {volZone && (
          <span style={styles.volZone}>⚡ HIGH VOL</span>
        )}
      </div>

      {/* Volatility zone warning */}
      {volZone && (
        <div style={styles.warning}>
          ⚠ HIGH VOLATILITY ZONE — Reduced liquidity expected
        </div>
      )}

      {/* Event list */}
      <div style={styles.list}>
        {events.map((e, i) => {
          const isImminent = e.timestamp > 0 && (e.timestamp - Date.now()) < 7200000;
          return (
            <div key={i} style={{
              ...styles.event,
              borderColor: e.impact === 'high' ? '#ff980040' : '#1a1a2e',
              background: isImminent ? '#ff980008' : 'transparent',
            }}>
              <div style={styles.eventHeader}>
                <span style={{
                  ...styles.impactBadge,
                  background: e.impact === 'high' ? '#ff9800' : '#555',
                  color: e.impact === 'high' ? '#000' : '#fff',
                }}>
                  {e.impact === 'high' ? 'HIGH' : 'MED'}
                </span>
                <span style={styles.category}>{e.category}</span>
              </div>
              <div style={styles.eventTitle}>{e.title}</div>
              <div style={styles.eventTime}>
                <span>{e.time}</span>
                <span style={{
                  ...styles.countdown,
                  color: isImminent ? '#ff9800' : '#555',
                }}>
                  {getTimeUntil(e.timestamp)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Disclaimer */}
      <div style={styles.disclaimer}>
        Static schedule — verify times independently
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
    borderTop: '1px solid #1a1a2e',
    flex: 1,
    overflow: 'auto',
  },
  title: {
    fontSize: 8,
    color: '#444',
    letterSpacing: 2,
    marginBottom: 4,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  volZone: {
    fontSize: 8,
    color: '#ff9800',
    fontWeight: 700,
    animation: 'pulse 2s infinite',
  },
  warning: {
    fontSize: 9,
    color: '#ff9800',
    background: 'rgba(255, 152, 0, 0.08)',
    border: '1px solid rgba(255, 152, 0, 0.2)',
    borderRadius: 3,
    padding: '4px 8px',
    marginBottom: 4,
  },
  list: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 3,
  },
  event: {
    padding: '5px 8px',
    borderRadius: 3,
    border: '1px solid #1a1a2e',
  },
  eventHeader: {
    display: 'flex',
    gap: 6,
    alignItems: 'center',
    marginBottom: 2,
  },
  impactBadge: {
    fontSize: 7,
    fontWeight: 700,
    padding: '1px 4px',
    borderRadius: 2,
    letterSpacing: 1,
  },
  category: {
    fontSize: 7,
    color: '#555',
    letterSpacing: 1,
  },
  eventTitle: {
    fontSize: 10,
    color: '#e0e0e0',
    fontWeight: 500,
  },
  eventTime: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 8,
    color: '#666',
    marginTop: 2,
  },
  countdown: {
    fontWeight: 600,
    fontVariantNumeric: 'tabular-nums' as const,
  },
  disclaimer: {
    fontSize: 7,
    color: '#333',
    textAlign: 'center' as const,
    padding: '4px 0',
    marginTop: 'auto',
  },
};
