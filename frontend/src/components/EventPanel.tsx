// MANTIS Dashboard — Event Engine Panel
// Displays detected structural market events with strength scores and forward outcomes
import { useState, useMemo } from 'react';
import { useStore } from '../store';
import { formatPrice, formatDelta, formatVol, timeAgo } from '../services/format';
import type { MarketEvent, EventFilter } from '../types';

const EVENT_COLORS: Record<string, string> = {
  absorption: '#f0b90b',
  exhaustion: '#ff6b35',
  liquidity_sweep: '#00bcd4',
  delta_divergence: '#9c27b0',
  imbalance: '#2196f3',
};

const SIDE_COLORS: Record<string, string> = {
  buy_absorption: '#26a69a',
  sell_absorption: '#ef5350',
  buy_exhaustion: '#26a69a',
  sell_exhaustion: '#ef5350',
  high_sweep: '#ef5350',
  low_sweep: '#26a69a',
  bearish_divergence: '#ef5350',
  bullish_divergence: '#26a69a',
  buy_imbalance: '#26a69a',
  sell_imbalance: '#ef5350',
};

function formatBps(v: number): string {
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}bps`;
}

function strengthBar(score: number): { width: string; color: string } {
  const pct = Math.round(score * 100);
  let color = '#444';
  if (score >= 0.7) color = '#f0b90b';
  else if (score >= 0.4) color = '#ff9800';
  else color = '#666';
  return { width: `${Math.max(pct, 8)}%`, color };
}

function EventCard({ event, expanded, onToggle }: {
  event: MarketEvent;
  expanded: boolean;
  onToggle: () => void;
}) {
  const sideColor = SIDE_COLORS[event.side] || '#888';
  const typeColor = EVENT_COLORS[event.event_type] || '#888';

  const strength = 'absorption_strength_score' in event ? event.absorption_strength_score
    : 'exhaustion_strength_score' in event ? event.exhaustion_strength_score
    : 'sweep_strength_score' in event ? event.sweep_strength_score
    : 'divergence_strength_score' in event ? event.divergence_strength_score
    : 'imbalance_ratio' in event ? Math.min(event.imbalance_ratio / 5, 1)
    : 0;

  const bar = strengthBar(strength);
  const fwd = event.forward;

  // Build summary line
  let summary = '';
  switch (event.event_type) {
    case 'absorption':
      summary = `${event.side === 'buy_absorption' ? 'Buy' : 'Sell'} absorption @ ${formatPrice(event.price_level)} | Vol: ${formatVol(event.aggressive_volume)} | Δ: ${formatDelta(event.signed_delta)}`;
      break;
    case 'exhaustion':
      summary = `${event.side === 'buy_exhaustion' ? 'Buy' : 'Sell'} exhaustion @ ${formatPrice(event.price)} | ${event.bubble_count} bubbles | impact: ${event.price_impact_per_volume.toFixed(4)}`;
      break;
    case 'liquidity_sweep':
      summary = `${event.side === 'high_sweep' ? 'High' : 'Low'} sweep @ ${formatPrice(event.swept_level)} | dist: ${event.sweep_distance.toFixed(1)} | ${event.reclaim_status ? 'RECLAIMED' : 'no reclaim'}`;
      break;
    case 'delta_divergence':
      summary = `${event.side === 'bearish_divergence' ? 'Bearish' : 'Bullish'} divergence | price: ${event.price_structure} | CVD: ${event.cvd_structure}`;
      break;
    case 'imbalance':
      summary = `${event.side === 'buy_imbalance' ? 'Buy' : 'Sell'} imbalance | ratio: ${event.imbalance_ratio.toFixed(1)}x | ${event.classification}`;
      break;
  }

  return (
    <div style={styles.card} onClick={onToggle}>
      {/* Header row */}
      <div style={styles.cardHeader}>
        <span style={{ ...styles.typeTag, background: typeColor }}>
          {event.event_type.toUpperCase()}
        </span>
        <span style={{ ...styles.sideTag, color: sideColor }}>
          {event.side.replace('_', ' ').toUpperCase()}
        </span>
        <span style={styles.strengthBadge}>
          <span style={{ ...styles.strengthFill, width: bar.width, background: bar.color }} />
          <span style={styles.strengthText}>{(strength * 100).toFixed(0)}%</span>
        </span>
        <span style={styles.timeAgo}>{timeAgo(event.timestamp)}</span>
      </div>

      {/* Summary */}
      <div style={styles.summary}>{summary}</div>

      {/* Expanded detail */}
      {expanded && (
        <div style={styles.detail}>
          {/* Event-specific fields */}
          {event.event_type === 'absorption' && (
            <div style={styles.fieldGrid}>
              <Field label="Window" value={`${event.window_seconds}s`} />
              <Field label="Agg Vol" value={formatVol(event.aggressive_volume)} />
              <Field label="Delta" value={formatDelta(event.signed_delta)} />
              <Field label="Price Δ" value={`${event.price_change_after_aggression.toFixed(1)}`} />
              <Field label="Vol Pctl" value={`${(event.local_volume_percentile * 100).toFixed(0)}%`} />
              <Field label="Δ Pctl" value={`${(event.delta_percentile * 100).toFixed(0)}%`} />
              <Field label="Book Liq" value={formatVol(event.book_liquidity_context)} />
              <Field label="VWAP Dist" value={`${event.vwap_distance.toFixed(1)}`} />
              <Field label="Spread" value={`${event.spread_context.toFixed(1)}`} />
              <Field label="Regime" value={event.regime_context} />
            </div>
          )}

          {event.event_type === 'exhaustion' && (
            <div style={styles.fieldGrid}>
              <Field label="Agg Vol" value={formatVol(event.aggressive_volume)} />
              <Field label="Delta" value={formatDelta(event.delta)} />
              <Field label="Bubbles" value={`${event.bubble_count}`} />
              <Field label="Impact/Vol" value={event.price_impact_per_volume.toFixed(4)} />
              <Field label="Cont Fail" value={`${(event.continuation_failure_score * 100).toFixed(0)}%`} />
              <Field label="CVD Div" value={event.cvd_divergence_context.toFixed(2)} />
              <Field label="Extreme" value={event.local_extreme_context} />
            </div>
          )}

          {event.event_type === 'liquidity_sweep' && (
            <div style={styles.fieldGrid}>
              <Field label="Swept" value={formatPrice(event.swept_level)} />
              <Field label="Distance" value={`${event.sweep_distance.toFixed(1)}`} />
              <Field label="Volume" value={formatVol(event.sweep_volume)} />
              <Field label="Delta" value={formatDelta(event.sweep_delta)} />
              <Field label="Reclaimed" value={event.reclaim_status ? 'YES' : 'NO'} />
              <Field label="Reversal" value={event.reversal_confirmation ? 'CONFIRMED' : 'pending'} />
            </div>
          )}

          {event.event_type === 'delta_divergence' && (
            <div style={styles.fieldGrid}>
              <Field label="Price" value={event.price_structure} />
              <Field label="CVD" value={event.cvd_structure} />
              <Field label="Window" value={`${event.divergence_window}s`} />
              <Field label="Det Price" value={formatPrice(event.price_at_detection)} />
              <Field label="Det CVD" value={formatDelta(event.cvd_at_detection)} />
              <Field label="Regime" value={event.local_trend_context} />
            </div>
          )}

          {event.event_type === 'imbalance' && (
            <div style={styles.fieldGrid}>
              <Field label="Buy Vol" value={formatVol(event.volume_buy)} />
              <Field label="Sell Vol" value={formatVol(event.volume_sell)} />
              <Field label="Delta" value={formatDelta(event.delta)} />
              <Field label="Ratio" value={`${event.imbalance_ratio.toFixed(1)}x`} />
              <Field label="Price Resp" value={`${event.price_response.toFixed(1)}`} />
              <Field label="Class" value={event.classification} />
            </div>
          )}

          {/* Forward outcome */}
          <div style={styles.forwardSection}>
            <div style={styles.forwardTitle}>FORWARD OUTCOME</div>
            {fwd.measured ? (
              <div style={styles.forwardGrid}>
                <ForwardPnl label="10s" bps={fwd.pnl_at_10s_bps} />
                <ForwardPnl label="30s" bps={fwd.pnl_at_30s_bps} />
                <ForwardPnl label="60s" bps={fwd.pnl_at_60s_bps} />
                <ForwardPnl label="120s" bps={fwd.pnl_at_120s_bps} />
                <ForwardPnl label="300s" bps={fwd.pnl_at_300s_bps} />
                <div style={styles.forwardNet}>
                  Net @60s: <span style={{
                    color: fwd.net_pnl_at_60s_bps > 0 ? '#26a69a' : '#ef5350',
                    fontWeight: 700,
                  }}>{formatBps(fwd.net_pnl_at_60s_bps)}</span>
                  <span style={{ color: '#555', fontSize: 8 }}> (incl {fwd.fees_assumed_bps * 2}bps fees)</span>
                </div>
              </div>
            ) : (
              <div style={styles.forwardPending}>
                Measuring... ({Math.round((fwd.price_at_10s > 0 ? 1 : 0) * 20 +
                  (fwd.price_at_30s > 0 ? 1 : 0) * 20 +
                  (fwd.price_at_60s > 0 ? 1 : 0) * 20 +
                  (fwd.price_at_120s > 0 ? 1 : 0) * 20 +
                  (fwd.price_at_300s > 0 ? 1 : 0) * 20)}%)
              </div>
            )}
            <div style={styles.mfeMae}>
              <span style={{ color: '#26a69a' }}>MFE: ${fwd.max_favorable_excursion.toFixed(1)}</span>
              <span style={{ color: '#ef5350' }}>MAE: ${fwd.max_adverse_excursion.toFixed(1)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div style={styles.field}>
      <span style={styles.fieldLabel}>{label}</span>
      <span style={styles.fieldValue}>{value}</span>
    </div>
  );
}

function ForwardPnl({ label, bps }: { label: string; bps: number }) {
  return (
    <div style={styles.forwardPnl}>
      <span style={styles.forwardLabel}>{label}</span>
      <span style={{
        color: bps > 0 ? '#26a69a' : bps < 0 ? '#ef5350' : '#666',
        fontWeight: 600,
        fontSize: 9,
      }}>{formatBps(bps)}</span>
    </div>
  );
}

export function EventPanel() {
  const events = useStore(s => s.events);
  const eventStats = useStore(s => s.eventStats);
  const eventFilter = useStore(s => s.eventFilter);
  const setEventFilter = useStore(s => s.setEventFilter);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [maxEvents] = useState(30);

  const filtered = useMemo(() => {
    let result = events;
    if (eventFilter?.event_type) {
      result = result.filter(e => e.event_type === eventFilter.event_type);
    }
    if (eventFilter?.side) {
      result = result.filter(e => e.side === eventFilter.side);
    }
    if (eventFilter?.min_strength) {
      result = result.filter(e => {
        const s = 'absorption_strength_score' in e ? e.absorption_strength_score
          : 'exhaustion_strength_score' in e ? e.exhaustion_strength_score
          : 'sweep_strength_score' in e ? e.sweep_strength_score
          : 'divergence_strength_score' in e ? e.divergence_strength_score
          : 'imbalance_ratio' in e ? Math.min(e.imbalance_ratio / 5, 1)
          : 0;
        return s >= eventFilter.min_strength!;
      });
    }
    return result.slice(0, maxEvents);
  }, [events, eventFilter, maxEvents]);

  const toggleFilter = (type: string) => {
    if (eventFilter?.event_type === type) {
      setEventFilter(null);
    } else {
      setEventFilter({ event_type: type });
    }
  };

  return (
    <div style={styles.panel}>
      {/* Header */}
      <div style={styles.header}>
        <span style={styles.headerTitle}>◆ EVENT ENGINE</span>
        <span style={styles.headerStats}>
          {eventStats.total} events | avg {(eventStats.avg_strength * 100).toFixed(0)}% strength
        </span>
      </div>

      {/* Type filter chips */}
      <div style={styles.filters}>
        {Object.entries(EVENT_COLORS).map(([type, color]) => (
          <button
            key={type}
            style={{
              ...styles.filterChip,
              background: eventFilter?.event_type === type ? color : 'transparent',
              borderColor: color,
              color: eventFilter?.event_type === type ? '#000' : color,
            }}
            onClick={() => toggleFilter(type)}
          >
            {type} {eventStats.by_type[type] || 0}
          </button>
        ))}
      </div>

      {/* Event list */}
      <div style={styles.eventList}>
        {filtered.length === 0 ? (
          <div style={styles.empty}>
            {events.length === 0
              ? 'No events detected yet. Waiting for order flow...'
              : 'No events match current filter.'}
          </div>
        ) : (
          filtered.map(evt => (
            <EventCard
              key={evt.event_id}
              event={evt}
              expanded={expandedId === evt.event_id}
              onToggle={() => setExpandedId(expandedId === evt.event_id ? null : evt.event_id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    background: '#0a0a0f',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px 12px',
    borderBottom: '1px solid #1a1a2e',
    flexShrink: 0,
  },
  headerTitle: {
    fontSize: 10,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 2,
  },
  headerStats: {
    fontSize: 8,
    color: '#666',
  },
  filters: {
    display: 'flex',
    gap: 4,
    padding: '6px 12px',
    flexShrink: 0,
    flexWrap: 'wrap' as const,
  },
  filterChip: {
    fontSize: 7,
    padding: '2px 6px',
    borderRadius: 3,
    border: '1px solid',
    cursor: 'pointer',
    fontWeight: 600,
    letterSpacing: 0.5,
    transition: 'all 0.2s',
    background: 'transparent',
    fontFamily: 'inherit',
  },
  eventList: {
    flex: 1,
    overflow: 'auto',
    padding: '4px 8px',
  },
  empty: {
    color: '#444',
    fontSize: 9,
    padding: '12px 0',
    textAlign: 'center' as const,
  },
  card: {
    background: '#0d0d14',
    border: '1px solid #1a1a2e',
    borderRadius: 4,
    padding: '6px 8px',
    marginBottom: 4,
    cursor: 'pointer',
    transition: 'border-color 0.2s',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    marginBottom: 3,
  },
  typeTag: {
    fontSize: 7,
    fontWeight: 700,
    padding: '1px 4px',
    borderRadius: 2,
    color: '#000',
    letterSpacing: 1,
  },
  sideTag: {
    fontSize: 8,
    fontWeight: 700,
    letterSpacing: 0.5,
  },
  strengthBadge: {
    position: 'relative' as const,
    width: 40,
    height: 8,
    background: '#1a1a2e',
    borderRadius: 4,
    overflow: 'hidden',
    marginLeft: 'auto',
  },
  strengthFill: {
    position: 'absolute' as const,
    left: 0,
    top: 0,
    height: '100%',
    borderRadius: 4,
    transition: 'width 0.5s',
  },
  strengthText: {
    position: 'absolute' as const,
    right: 2,
    top: -1,
    fontSize: 7,
    color: '#888',
    fontWeight: 600,
  },
  timeAgo: {
    fontSize: 7,
    color: '#555',
    marginLeft: 4,
  },
  summary: {
    fontSize: 8,
    color: '#999',
    lineHeight: 1.3,
  },
  detail: {
    marginTop: 6,
    paddingTop: 6,
    borderTop: '1px solid #1a1a2e',
  },
  fieldGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '2px 8px',
    marginBottom: 6,
  },
  field: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '1px 0',
  },
  fieldLabel: {
    fontSize: 7,
    color: '#555',
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
  },
  fieldValue: {
    fontSize: 8,
    color: '#ccc',
    fontWeight: 500,
  },
  forwardSection: {
    marginTop: 4,
    padding: '4px 0',
    borderTop: '1px dashed #1a1a2e',
  },
  forwardTitle: {
    fontSize: 7,
    color: '#555',
    letterSpacing: 2,
    marginBottom: 4,
  },
  forwardGrid: {
    display: 'flex',
    gap: 8,
    marginBottom: 4,
  },
  forwardPnl: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: 1,
  },
  forwardLabel: {
    fontSize: 7,
    color: '#555',
  },
  forwardNet: {
    fontSize: 8,
    color: '#999',
    marginLeft: 'auto',
  },
  forwardPending: {
    fontSize: 8,
    color: '#555',
    fontStyle: 'italic' as const,
  },
  mfeMae: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: 8,
    marginTop: 2,
  },
};
