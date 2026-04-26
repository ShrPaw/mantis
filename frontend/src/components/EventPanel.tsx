// MANTIS Dashboard — Event Engine Panel
// EventFeed + EventCard + EventFilter + EventStatsPanel + EventReplayPanel
import { useState, useMemo, useCallback } from 'react';
import { useStore } from '../store';
import { formatPrice, formatDelta, formatVol, timeAgo } from '../services/format';
import type { MarketEvent, EventFilter, ForwardOutcome } from '../types';

// ============================================================
// Constants
// ============================================================

const EVENT_COLORS: Record<string, string> = {
  absorption: '#f0b90b',
  exhaustion: '#ff6b35',
  liquidity_sweep: '#00bcd4',
  delta_divergence: '#9c27b0',
  imbalance: '#2196f3',
  large_trade_cluster: '#e91e63',
  range_break: '#4caf50',
  vwap_reaction: '#ff5722',
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
  buy_cluster: '#26a69a',
  sell_cluster: '#ef5350',
  up_break: '#26a69a',
  down_break: '#ef5350',
  above_vwap: '#26a69a',
  below_vwap: '#ef5350',
};

function formatBps(v: number | null): string {
  if (v === null) return '—';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}bps`;
}

function strengthPct(score: number): number {
  return Math.round(score * 100);
}

// ============================================================
// ForwardOutcomeDisplay
// ============================================================

function ForwardOutcomeView({ fwd, side }: { fwd: ForwardOutcome; side: string }) {
  if (fwd.is_complete) {
    const ret60 = fwd.future_return_60s;
    const color = ret60 !== null ? (ret60 > 0 ? '#26a69a' : '#ef5350') : '#666';
    return (
      <div style={fwdStyles.container}>
        <div style={fwdStyles.row}>
          <FwdCell label="10s" val={fwd.future_return_10s} />
          <FwdCell label="30s" val={fwd.future_return_30s} />
          <FwdCell label="60s" val={fwd.future_return_60s} />
          <FwdCell label="120s" val={fwd.future_return_120s} />
          <FwdCell label="300s" val={fwd.future_return_300s} />
        </div>
        <div style={fwdStyles.mfeRow}>
          <span style={{ color: '#26a69a', fontSize: 8 }}>MFE30: {fwd.max_favorable_excursion_30s?.toFixed(1) ?? '—'}</span>
          <span style={{ color: '#ef5350', fontSize: 8 }}>MAE30: {fwd.max_adverse_excursion_30s?.toFixed(1) ?? '—'}</span>
          <span style={{ color: '#26a69a', fontSize: 8 }}>MFE120: {fwd.max_favorable_excursion_120s?.toFixed(1) ?? '—'}</span>
          <span style={{ color: '#ef5350', fontSize: 8 }}>MAE120: {fwd.max_adverse_excursion_120s?.toFixed(1) ?? '—'}</span>
        </div>
        <div style={fwdStyles.tpRow}>
          <span style={{ fontSize: 8, color: fwd.hit_tp_0_10pct ? '#26a69a' : '#444' }}>TP10bps {fwd.hit_tp_0_10pct ? '✓' : '✗'}</span>
          <span style={{ fontSize: 8, color: fwd.hit_tp_0_20pct ? '#26a69a' : '#444' }}>TP20bps {fwd.hit_tp_0_20pct ? '✓' : '✗'}</span>
          <span style={{ fontSize: 8, color: fwd.hit_sl_0_10pct ? '#ef5350' : '#444' }}>SL10bps {fwd.hit_sl_0_10pct ? '✓' : '✗'}</span>
          <span style={{ fontSize: 8, color: fwd.hit_sl_0_20pct ? '#ef5350' : '#444' }}>SL20bps {fwd.hit_sl_0_20pct ? '✓' : '✗'}</span>
        </div>
      </div>
    );
  }

  // Pending — show progress
  const measured = [
    fwd.future_return_10s !== null,
    fwd.future_return_30s !== null,
    fwd.future_return_60s !== null,
    fwd.future_return_120s !== null,
    fwd.future_return_300s !== null,
  ];
  const pct = measured.filter(Boolean).length * 20;

  return (
    <div style={fwdStyles.container}>
      <div style={fwdStyles.pending}>
        <div style={fwdStyles.pendingBar}>
          <div style={{ ...fwdStyles.pendingFill, width: `${pct}%` }} />
        </div>
        <span style={fwdStyles.pendingText}>Measuring... {pct}%</span>
      </div>
    </div>
  );
}

function FwdCell({ label, val }: { label: string; val: number | null }) {
  const color = val !== null ? (val > 0 ? '#26a69a' : val < 0 ? '#ef5350' : '#666') : '#333';
  return (
    <div style={fwdStyles.cell}>
      <span style={fwdStyles.cellLabel}>{label}</span>
      <span style={{ ...fwdStyles.cellVal, color }}>{formatBps(val)}</span>
    </div>
  );
}

const fwdStyles: Record<string, React.CSSProperties> = {
  container: { marginTop: 4, paddingTop: 4, borderTop: '1px dashed #1a1a2e' },
  row: { display: 'flex', gap: 6, marginBottom: 3 },
  cell: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 },
  cellLabel: { fontSize: 7, color: '#555' },
  cellVal: { fontSize: 9, fontWeight: 600 },
  mfeRow: { display: 'flex', justifyContent: 'space-between', marginBottom: 2 },
  tpRow: { display: 'flex', justifyContent: 'space-between' },
  pending: { display: 'flex', alignItems: 'center', gap: 6 },
  pendingBar: { flex: 1, height: 3, background: '#1a1a2e', borderRadius: 2, overflow: 'hidden' },
  pendingFill: { height: '100%', background: '#f0b90b', borderRadius: 2, transition: 'width 0.5s' },
  pendingText: { fontSize: 8, color: '#555', whiteSpace: 'nowrap' as const },
};

// ============================================================
// EventCard
// ============================================================

function EventCard({ event, expanded, onToggle }: {
  event: MarketEvent;
  expanded: boolean;
  onToggle: () => void;
}) {
  const sideColor = SIDE_COLORS[event.side] || '#888';
  const typeColor = EVENT_COLORS[event.event_type] || '#888';
  const str = event.scores.strength_score;
  const conf = event.scores.confidence_score;

  // Build summary
  let summary = '';
  switch (event.event_type) {
    case 'absorption':
      summary = `${event.side === 'buy_absorption' ? 'Buy' : 'Sell'} absorption @ ${formatPrice(event.price)} | Vol: ${formatVol(event.aggressive_volume)} | Δ: ${formatDelta(event.signed_delta)}`;
      break;
    case 'exhaustion':
      summary = `${event.side === 'buy_exhaustion' ? 'Buy' : 'Sell'} exhaustion @ ${formatPrice(event.price)} | ${event.bubble_count} bubbles`;
      break;
    case 'liquidity_sweep':
      summary = `${event.side === 'high_sweep' ? 'High' : 'Low'} sweep @ ${formatPrice(event.swept_level)} | ${event.reclaim_status ? 'RECLAIMED' : 'no reclaim'}`;
      break;
    case 'delta_divergence':
      summary = `${event.side === 'bearish_divergence' ? 'Bearish' : 'Bullish'} divergence | ${event.price_structure} vs ${event.cvd_structure}`;
      break;
    case 'imbalance':
      summary = `${event.side === 'buy_imbalance' ? 'Buy' : 'Sell'} ${event.imbalance_ratio.toFixed(1)}x | ${event.classification}`;
      break;
    case 'large_trade_cluster':
      summary = `${event.number_of_large_trades} large trades | ${formatVol(event.total_cluster_volume)} BTC | ${event.continuation_or_failure_label}`;
      break;
    case 'range_break':
      summary = `${event.side === 'up_break' ? '▲' : '▼'} break [${formatPrice(event.range_low)}-${formatPrice(event.range_high)}] | ${event.failed_break_status ? 'FAILED' : 'continues'}`;
      break;
    case 'vwap_reaction':
      summary = `VWAP ${event.reaction_type} @ ${formatPrice(event.price)} | dist: ${event.distance_to_vwap.toFixed(1)}`;
      break;
  }

  return (
    <div style={cardStyles.card} onClick={onToggle}>
      {/* Header */}
      <div style={cardStyles.header}>
        <span style={{ ...cardStyles.typeTag, background: typeColor }}>
          {event.event_type.replace(/_/g, ' ').toUpperCase()}
        </span>
        <span style={{ ...cardStyles.sideTag, color: sideColor }}>
          {event.side.replace(/_/g, ' ').toUpperCase()}
        </span>
        <div style={cardStyles.scoreBadges}>
          <span style={cardStyles.scoreBadge}>
            S:{strengthPct(str)}
          </span>
          <span style={cardStyles.scoreBadge}>
            C:{strengthPct(conf)}
          </span>
        </div>
        <span style={cardStyles.time}>{timeAgo(event.timestamp)}</span>
        <span style={{
          ...cardStyles.statusDot,
          background: event.is_active ? '#f0b90b' : '#333',
        }} />
      </div>

      {/* Explanation */}
      <div style={cardStyles.explanation}>{event.explanation}</div>

      {/* Summary */}
      <div style={cardStyles.summary}>{summary}</div>

      {/* Expanded detail */}
      {expanded && (
        <div style={cardStyles.detail}>
          {/* Scores breakdown */}
          <div style={cardStyles.scoreSection}>
            <ScoreBar label="Strength" value={str} color="#f0b90b" />
            <ScoreBar label="Confidence" value={conf} color="#2196f3" />
            <ScoreBar label="Noise" value={event.scores.noise_score} color="#ef5350" />
            <div style={cardStyles.scoreComponents}>
              {Object.entries(event.scores.strength_components).map(([k, v]) => (
                <span key={k} style={cardStyles.componentChip}>{k}: {(v * 100).toFixed(0)}%</span>
              ))}
            </div>
          </div>

          {/* Forward outcome */}
          <ForwardOutcomeView fwd={event.forward} side={event.side} />

          {/* Context */}
          <div style={cardStyles.contextRow}>
            <span style={cardStyles.contextChip}>Regime: {event.context_metrics.regime || '—'}</span>
            {event.validation_tags.map((t, i) => (
              <span key={i} style={cardStyles.contextChip}>{t}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={sbStyles.row}>
      <span style={sbStyles.label}>{label}</span>
      <div style={sbStyles.barOuter}>
        <div style={{ ...sbStyles.barFill, width: `${strengthPct(value)}%`, background: color }} />
      </div>
      <span style={sbStyles.val}>{strengthPct(value)}</span>
    </div>
  );
}

const sbStyles: Record<string, React.CSSProperties> = {
  row: { display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 },
  label: { fontSize: 7, color: '#555', width: 55 },
  barOuter: { flex: 1, height: 3, background: '#1a1a2e', borderRadius: 2, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 2, transition: 'width 0.5s' },
  val: { fontSize: 8, color: '#888', width: 20, textAlign: 'right' as const },
};

const cardStyles: Record<string, React.CSSProperties> = {
  card: {
    background: '#0d0d14',
    border: '1px solid #1a1a2e',
    borderRadius: 4,
    padding: '6px 8px',
    marginBottom: 4,
    cursor: 'pointer',
    transition: 'border-color 0.2s',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    marginBottom: 3,
    flexWrap: 'wrap' as const,
  },
  typeTag: {
    fontSize: 7,
    fontWeight: 700,
    padding: '1px 4px',
    borderRadius: 2,
    color: '#000',
    letterSpacing: 0.5,
  },
  sideTag: {
    fontSize: 8,
    fontWeight: 700,
    letterSpacing: 0.5,
  },
  scoreBadges: {
    display: 'flex',
    gap: 3,
    marginLeft: 'auto',
  },
  scoreBadge: {
    fontSize: 7,
    color: '#888',
    background: '#1a1a2e',
    padding: '1px 3px',
    borderRadius: 2,
  },
  time: {
    fontSize: 7,
    color: '#444',
  },
  statusDot: {
    width: 5,
    height: 5,
    borderRadius: '50%',
  },
  explanation: {
    fontSize: 8,
    color: '#999',
    lineHeight: 1.3,
    marginBottom: 2,
  },
  summary: {
    fontSize: 8,
    color: '#666',
    fontStyle: 'italic' as const,
  },
  detail: {
    marginTop: 6,
    paddingTop: 6,
    borderTop: '1px solid #1a1a2e',
  },
  scoreSection: {
    marginBottom: 6,
  },
  scoreComponents: {
    display: 'flex',
    gap: 4,
    flexWrap: 'wrap' as const,
    marginTop: 3,
  },
  componentChip: {
    fontSize: 7,
    color: '#555',
    background: '#1a1a2e',
    padding: '1px 3px',
    borderRadius: 2,
  },
  contextRow: {
    display: 'flex',
    gap: 4,
    flexWrap: 'wrap' as const,
    marginTop: 4,
  },
  contextChip: {
    fontSize: 7,
    color: '#444',
    background: '#0a0a0f',
    padding: '1px 4px',
    borderRadius: 2,
    border: '1px solid #1a1a2e',
  },
};

// ============================================================
// EventFilterBar
// ============================================================

function EventFilterBar() {
  const eventFilter = useStore(s => s.eventFilter);
  const setEventFilter = useStore(s => s.setEventFilter);
  const eventStats = useStore(s => s.eventStats);

  const toggleFilter = useCallback((type: string) => {
    if (eventFilter?.event_type === type) {
      setEventFilter(null);
    } else {
      setEventFilter({ event_type: type });
    }
  }, [eventFilter, setEventFilter]);

  return (
    <div style={filterStyles.container}>
      {Object.entries(EVENT_COLORS).map(([type, color]) => {
        const count = eventStats.by_type[type] || 0;
        const active = eventFilter?.event_type === type;
        return (
          <button
            key={type}
            style={{
              ...filterStyles.chip,
              background: active ? color : 'transparent',
              borderColor: color,
              color: active ? '#000' : color,
            }}
            onClick={() => toggleFilter(type)}
          >
            {type.replace(/_/g, ' ')} {count}
          </button>
        );
      })}
    </div>
  );
}

const filterStyles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    gap: 3,
    padding: '6px 8px',
    flexShrink: 0,
    flexWrap: 'wrap' as const,
    borderBottom: '1px solid #1a1a2e',
  },
  chip: {
    fontSize: 7,
    padding: '2px 5px',
    borderRadius: 3,
    border: '1px solid',
    cursor: 'pointer',
    fontWeight: 600,
    letterSpacing: 0.3,
    transition: 'all 0.2s',
    background: 'transparent',
    fontFamily: 'inherit',
  },
};

// ============================================================
// EventStatsPanel
// ============================================================

function EventStatsPanel() {
  const stats = useStore(s => s.eventStats);

  return (
    <div style={statsStyles.container}>
      <div style={statsStyles.row}>
        <StatBox label="Total" value={stats.total} />
        <StatBox label="Fired" value={stats.fired} />
        <StatBox label="Deduped" value={stats.deduped} />
        <StatBox label="Pending" value={stats.pending_outcomes} />
      </div>
      <div style={statsStyles.row}>
        <StatBox label="Avg Str" value={`${strengthPct(stats.avg_strength)}%`} />
        <StatBox label="Avg Conf" value={`${strengthPct(stats.avg_confidence)}%`} />
        <StatBox label="Measured" value={stats.measured_count} />
      </div>
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: number | string }) {
  return (
    <div style={statBoxStyles.box}>
      <span style={statBoxStyles.label}>{label}</span>
      <span style={statBoxStyles.value}>{value}</span>
    </div>
  );
}

const statsStyles: Record<string, React.CSSProperties> = {
  container: {
    padding: '6px 8px',
    borderBottom: '1px solid #1a1a2e',
    flexShrink: 0,
  },
  row: {
    display: 'flex',
    gap: 8,
    marginBottom: 3,
  },
};

const statBoxStyles: Record<string, React.CSSProperties> = {
  box: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 1,
  },
  label: {
    fontSize: 7,
    color: '#555',
    letterSpacing: 0.5,
  },
  value: {
    fontSize: 10,
    color: '#ccc',
    fontWeight: 600,
  },
};

// ============================================================
// EventReplayPanel
// ============================================================

function EventReplayPanel() {
  const events = useStore(s => s.events);
  const [selectedType, setSelectedType] = useState<string>('all');

  const filtered = useMemo(() => {
    if (selectedType === 'all') return events;
    return events.filter(e => e.event_type === selectedType);
  }, [events, selectedType]);

  // Compute performance stats by type
  const perfByType = useMemo(() => {
    const result: Record<string, { count: number; avgRet60: number; winRate: number }> = {};
    for (const evt of events) {
      if (!evt.forward.is_complete) continue;
      const t = evt.event_type;
      if (!result[t]) result[t] = { count: 0, avgRet60: 0, winRate: 0 };
      result[t].count++;
      const ret = evt.forward.future_return_60s || 0;
      result[t].avgRet60 += ret;
      if (ret > 0) result[t].winRate++;
    }
    for (const t of Object.keys(result)) {
      const r = result[t];
      if (r.count > 0) {
        r.avgRet60 /= r.count;
        r.winRate /= r.count;
      }
    }
    return result;
  }, [events]);

  const completedEvents = events.filter(e => e.forward.is_complete);

  return (
    <div style={replayStyles.container}>
      <div style={replayStyles.title}>◆ EVENT REPLAY / VALIDATION</div>
      <div style={replayStyles.subtitle}>
        {completedEvents.length} events with complete outcomes
      </div>

      {/* Performance by type */}
      {Object.entries(perfByType).length > 0 && (
        <div style={replayStyles.perfSection}>
          <div style={replayStyles.perfTitle}>PERFORMANCE BY TYPE (60s)</div>
          {Object.entries(perfByType).map(([type, perf]) => (
            <div key={type} style={replayStyles.perfRow}>
              <span style={{ ...replayStyles.perfType, color: EVENT_COLORS[type] || '#888' }}>
                {type.replace(/_/g, ' ')}
              </span>
              <span style={replayStyles.perfN}>n={perf.count}</span>
              <span style={{
                ...replayStyles.perfRet,
                color: perf.avgRet60 > 0 ? '#26a69a' : '#ef5350',
              }}>
                {formatBps(perf.avgRet60)}
              </span>
              <span style={replayStyles.perfWR}>
                WR: {(perf.winRate * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Filter */}
      <div style={replayStyles.filterRow}>
        <button
          style={{
            ...replayStyles.filterBtn,
            background: selectedType === 'all' ? '#333' : 'transparent',
          }}
          onClick={() => setSelectedType('all')}
        >ALL</button>
        {Object.keys(EVENT_COLORS).map(t => (
          <button
            key={t}
            style={{
              ...replayStyles.filterBtn,
              background: selectedType === t ? EVENT_COLORS[t] : 'transparent',
              color: selectedType === t ? '#000' : EVENT_COLORS[t],
            }}
            onClick={() => setSelectedType(t)}
          >{t.slice(0, 4)}</button>
        ))}
      </div>

      {/* Event list */}
      <div style={replayStyles.list}>
        {filtered.slice(0, 20).map(evt => (
          <div key={evt.event_id} style={replayStyles.listItem}>
            <span style={{ color: EVENT_COLORS[evt.event_type] || '#888', fontSize: 8 }}>
              {evt.event_type.slice(0, 6)}
            </span>
            <span style={{ color: SIDE_COLORS[evt.side] || '#888', fontSize: 8 }}>
              {evt.side.slice(0, 8)}
            </span>
            <span style={{ color: '#ccc', fontSize: 8 }}>{formatPrice(evt.price)}</span>
            <span style={{ color: '#888', fontSize: 8 }}>{strengthPct(evt.scores.strength_score)}%</span>
            <span style={{
              fontSize: 8,
              color: evt.forward.future_return_60s !== null
                ? (evt.forward.future_return_60s > 0 ? '#26a69a' : '#ef5350')
                : '#444',
            }}>
              {evt.forward.future_return_60s !== null ? formatBps(evt.forward.future_return_60s) : 'pending'}
            </span>
            <span style={{ fontSize: 7, color: '#444' }}>{timeAgo(evt.timestamp)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const replayStyles: Record<string, React.CSSProperties> = {
  container: {
    padding: '6px 8px',
    borderTop: '1px solid #1a1a2e',
  },
  title: {
    fontSize: 8,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 1,
    marginBottom: 2,
  },
  subtitle: {
    fontSize: 7,
    color: '#555',
    marginBottom: 6,
  },
  perfSection: {
    marginBottom: 8,
  },
  perfTitle: {
    fontSize: 7,
    color: '#555',
    letterSpacing: 1,
    marginBottom: 3,
    borderBottom: '1px solid #1a1a2e',
    paddingBottom: 2,
  },
  perfRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '2px 0',
  },
  perfType: {
    fontSize: 8,
    fontWeight: 600,
    width: 80,
  },
  perfN: {
    fontSize: 7,
    color: '#555',
    width: 30,
  },
  perfRet: {
    fontSize: 9,
    fontWeight: 600,
    width: 60,
  },
  perfWR: {
    fontSize: 8,
    color: '#888',
  },
  filterRow: {
    display: 'flex',
    gap: 2,
    marginBottom: 6,
    flexWrap: 'wrap' as const,
  },
  filterBtn: {
    fontSize: 7,
    padding: '2px 4px',
    borderRadius: 2,
    border: '1px solid #333',
    cursor: 'pointer',
    color: '#888',
    background: 'transparent',
    fontFamily: 'inherit',
  },
  list: {
    maxHeight: 200,
    overflow: 'auto',
  },
  listItem: {
    display: 'flex',
    gap: 6,
    alignItems: 'center',
    padding: '2px 0',
    borderBottom: '1px solid #0a0a0f',
  },
};

// ============================================================
// Main EventPanel
// ============================================================

export function EventPanel() {
  const events = useStore(s => s.events);
  const eventFilter = useStore(s => s.eventFilter);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showReplay, setShowReplay] = useState(false);

  const filtered = useMemo(() => {
    let result = events;
    if (eventFilter?.event_type) {
      result = result.filter(e => e.event_type === eventFilter.event_type);
    }
    if (eventFilter?.side) {
      result = result.filter(e => e.side === eventFilter.side);
    }
    return result.slice(0, 30);
  }, [events, eventFilter]);

  return (
    <div style={panelStyles.container}>
      {/* Header */}
      <div style={panelStyles.header}>
        <span style={panelStyles.headerTitle}>◆ EVENT ENGINE PRO</span>
        <button
          style={panelStyles.replayBtn}
          onClick={() => setShowReplay(!showReplay)}
        >
          {showReplay ? 'FEED' : 'REPLAY'}
        </button>
      </div>

      {/* Stats */}
      <EventStatsPanel />

      {/* Filter */}
      <EventFilterBar />

      {/* Content */}
      {showReplay ? (
        <EventReplayPanel />
      ) : (
        <div style={panelStyles.eventList}>
          {filtered.length === 0 ? (
            <div style={panelStyles.empty}>
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
      )}
    </div>
  );
}

const panelStyles: Record<string, React.CSSProperties> = {
  container: {
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
    padding: '8px 10px',
    borderBottom: '1px solid #1a1a2e',
    flexShrink: 0,
  },
  headerTitle: {
    fontSize: 10,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 2,
  },
  replayBtn: {
    fontSize: 7,
    padding: '2px 6px',
    borderRadius: 3,
    border: '1px solid #f0b90b',
    color: '#f0b90b',
    background: 'transparent',
    cursor: 'pointer',
    fontWeight: 600,
    letterSpacing: 1,
    fontFamily: 'inherit',
  },
  eventList: {
    flex: 1,
    overflow: 'auto',
    padding: '4px 6px',
  },
  empty: {
    color: '#444',
    fontSize: 9,
    padding: '12px 0',
    textAlign: 'center' as const,
  },
};
