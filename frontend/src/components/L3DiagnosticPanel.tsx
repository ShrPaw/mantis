// MANTIS Operator Dashboard — L3 1M Displacement Diagnostic Panel
// Shadow diagnostic showing production L3 status + 5 shadow variant evaluations
// All field access is defensive — handles missing/null/error states gracefully.
import React, { useEffect, useState, useCallback } from 'react';
import { T } from '../styles/operatorTheme';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const POLL_INTERVAL = 5000;

// ── Types (all fields optional for safety) ──

interface L3Metrics {
  body_bps?: number | null;
  range_bps?: number | null;
  close_to_close_bps?: number | null;
  leg_3c_bps?: number | null;
  leg_5c_bps?: number | null;
  directional_efficiency_3c?: number | null;
  directional_efficiency_5c?: number | null;
  pullback_ratio?: number | null;
  max_extension_bps?: number | null;
  volume_percentile?: number | null;
  volatility_percentile?: number | null;
}

interface L3CalibrationData {
  status?: string;
  production_l3_status?: string;
  production_l3_block_reason?: string;
  shadow_3c_pass?: boolean;
  shadow_stress_pass?: boolean;
  shadow_single_candle_pass?: boolean;
  shadow_5c_pass?: boolean;
  metrics?: L3Metrics;
  interpretation?: string;
  ready?: boolean;
  candles_evaluated?: number;
  percentile_ranks?: Record<string, number | undefined>;
}

// ── Helpers ──

const STATUS_COLORS: Record<string, string> = {
  PASS: T.status.success,
  FAIL: T.status.danger,
  NOT_EVALUATED: T.text.muted,
};

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return v.toFixed(decimals);
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return (v * 100).toFixed(0) + '%';
}

function rankColor(rank: number | null | undefined): string {
  if (rank === null || rank === undefined) return T.text.muted;
  if (rank >= 0.85) return T.status.success;
  if (rank >= 0.6) return T.status.warning;
  return T.text.muted;
}

// ── Sub-components ──

function StatusBadge({ label, pass, prod }: { label: string; pass?: boolean; prod?: string }) {
  const color = prod
    ? (STATUS_COLORS[prod] || T.text.muted)
    : (pass ? T.status.success : T.status.danger);
  const text = prod || (pass ? 'PASS' : 'FAIL');

  return (
    <div style={S.badgeRow}>
      <span style={S.badgeLabel}>{label}</span>
      <span style={{ ...S.badgeValue, color, textShadow: `0 0 6px ${color}40` }}>{text}</span>
    </div>
  );
}

function MetricRow({ label, value, unit, rank }: {
  label: string; value: string; unit?: string; rank?: number | null;
}) {
  return (
    <div style={S.metricRow}>
      <span style={S.metricLabel}>{label}</span>
      <span style={S.metricValue}>
        {value}
        {unit && value !== '—' && <span style={S.metricUnit}>{unit}</span>}
      </span>
      {rank !== undefined && rank !== null && (
        <span style={{ ...S.rankBadge, color: rankColor(rank) }}>
          p{(rank * 100).toFixed(0)}
        </span>
      )}
    </div>
  );
}

// ── Main Panel ──

export const L3DiagnosticPanel: React.FC = () => {
  const [data, setData] = useState<L3CalibrationData | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/l3/calibration`);
      if (!resp.ok) {
        setFetchError(`HTTP ${resp.status}`);
        return;
      }
      const json: L3CalibrationData = await resp.json();

      // Validate: must have status field
      if (!json || typeof json !== 'object') {
        setFetchError('invalid_response');
        return;
      }

      // Check for error status (old backend) — show as warming up
      if (json.status === 'error') {
        setFetchError(json.production_l3_block_reason || 'calibration error');
        return;
      }

      setData(json);
      setFetchError(null);
    } catch {
      // silent — panel just won't update
    }
  }, []);

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchData]);

  // ── Error state (inside panel only, never blacks out cockpit) ──
  if (fetchError) {
    return (
      <div style={S.panel}>
        <div style={S.title}>L3 1M DISPLACEMENT DIAGNOSTIC</div>
        <div style={S.errorCard}>
          <span style={S.errorIcon}>⚠</span>
          <span style={S.errorText}>{fetchError}</span>
        </div>
      </div>
    );
  }

  // ── No data yet ──
  if (!data) {
    return (
      <div style={S.panel}>
        <div style={S.title}>L3 1M DISPLACEMENT DIAGNOSTIC</div>
        <div style={S.empty}>Connecting...</div>
      </div>
    );
  }

  // ── Not ready (warming up) ──
  if (!data.ready) {
    return (
      <div style={S.panel}>
        <div style={S.title}>L3 1M DISPLACEMENT DIAGNOSTIC</div>
        <div style={S.warmingUp}>
          <span style={S.warmingIcon}>◎</span>
          <span>Calibration warming up</span>
          <span style={S.warmingCount}>{data.candles_evaluated ?? 0}/5 candles</span>
        </div>
      </div>
    );
  }

  // ── Ready — full render ──
  const m = data.metrics || {};
  const ranks = data.percentile_ranks || {};

  return (
    <div style={S.panel}>
      <div style={S.title}>L3 1M DISPLACEMENT DIAGNOSTIC</div>

      {/* Status grid */}
      <div style={S.statusGrid}>
        <StatusBadge label="PROD L3" pass={false} prod={data.production_l3_status} />
        <StatusBadge label="3C DISP" pass={data.shadow_3c_pass} />
        <StatusBadge label="STRESS" pass={data.shadow_stress_pass} />
        <StatusBadge label="SINGLE" pass={data.shadow_single_candle_pass} />
        <StatusBadge label="5C LEG" pass={data.shadow_5c_pass} />
      </div>

      {/* Production block reason */}
      {data.production_l3_status === 'FAIL' && data.production_l3_block_reason && (
        <div style={S.blockReason}>
          PROD: {data.production_l3_block_reason}
        </div>
      )}

      {/* Metrics */}
      <div style={S.metricsSection}>
        <div style={S.sectionLabel}>CURRENT METRICS</div>
        <MetricRow label="body" value={fmt(m.body_bps)} unit=" bps" rank={ranks.body_bps_rank_60} />
        <MetricRow label="range" value={fmt(m.range_bps)} unit=" bps" rank={ranks.range_bps_rank_60} />
        <MetricRow label="3c leg" value={fmt(m.leg_3c_bps)} unit=" bps" rank={ranks.leg_3c_bps_rank_60} />
        <MetricRow label="5c leg" value={fmt(m.leg_5c_bps)} unit=" bps" rank={ranks.leg_5c_bps_rank_60} />
        <MetricRow label="eff 3c" value={fmt(m.directional_efficiency_3c, 3)} />
        <MetricRow label="eff 5c" value={fmt(m.directional_efficiency_5c, 3)} />
        <MetricRow label="pullback" value={fmt(m.pullback_ratio, 3)} />
        <MetricRow label="vol pct" value={fmtPct(m.volume_percentile)} />
        <MetricRow label="vol rank" value={fmtPct(m.volatility_percentile)} />
      </div>

      {/* Interpretation */}
      {data.interpretation && (
        <div style={S.interpretation}>
          {data.interpretation}
        </div>
      )}

      {/* Footer */}
      <div style={S.footer}>
        {(data.candles_evaluated ?? 0)} candles evaluated
      </div>
    </div>
  );
};

// ── Styles ──

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: `linear-gradient(180deg, ${T.bg.panel} 0%, ${T.bg.surface} 100%)`,
    border: `1px solid ${T.border.mid}`,
    borderRadius: 6,
    padding: '10px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  title: {
    fontSize: 9,
    fontWeight: 700,
    color: T.accent.cyan,
    letterSpacing: 2,
    marginBottom: 4,
    textShadow: `0 0 8px rgba(0,229,200,0.2)`,
  },
  empty: {
    fontSize: 9,
    color: T.text.muted,
    textAlign: 'center',
    padding: '12px 0',
    fontStyle: 'italic',
  },
  errorCard: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '6px 8px',
    background: 'rgba(255,95,95,0.06)',
    border: `1px solid rgba(255,95,95,0.12)`,
    borderRadius: 4,
  },
  errorIcon: {
    color: T.status.warning,
    fontSize: 11,
  },
  errorText: {
    fontSize: 8,
    color: T.status.warning,
    lineHeight: 1.3,
  },
  warmingUp: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 4,
    padding: '12px 0',
    fontSize: 9,
    color: T.text.muted,
  },
  warmingIcon: {
    fontSize: 14,
    color: T.accent.cyan,
    animation: 'pulse 2s infinite',
  },
  warmingCount: {
    fontSize: 8,
    color: T.text.faint,
    fontFamily: T.font.mono,
  },
  statusGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(5, 1fr)',
    gap: 3,
  },
  badgeRow: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 2,
    padding: '4px 2px',
    background: 'rgba(255,255,255,0.02)',
    borderRadius: 3,
    border: `1px solid ${T.border.dim}`,
  },
  badgeLabel: {
    fontSize: 7,
    color: T.text.muted,
    letterSpacing: 0.5,
    fontWeight: 600,
  },
  badgeValue: {
    fontSize: 9,
    fontWeight: 700,
    letterSpacing: 0.5,
  },
  blockReason: {
    fontSize: 8,
    color: T.status.danger,
    padding: '4px 6px',
    background: 'rgba(255,95,95,0.06)',
    borderRadius: 3,
    border: `1px solid rgba(255,95,95,0.12)`,
    lineHeight: 1.3,
  },
  metricsSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
  },
  sectionLabel: {
    fontSize: 7,
    fontWeight: 700,
    color: T.text.muted,
    letterSpacing: 1.5,
    marginBottom: 2,
  },
  metricRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '2px 0',
  },
  metricLabel: {
    fontSize: 8,
    color: T.text.dim,
    width: 50,
    flexShrink: 0,
    letterSpacing: 0.3,
  },
  metricValue: {
    fontSize: 9,
    color: T.text.main,
    fontFamily: T.font.mono,
    fontWeight: 600,
    flex: 1,
  },
  metricUnit: {
    fontSize: 7,
    color: T.text.muted,
    marginLeft: 1,
  },
  rankBadge: {
    fontSize: 7,
    fontWeight: 700,
    fontFamily: T.font.mono,
    minWidth: 28,
    textAlign: 'right' as const,
  },
  interpretation: {
    fontSize: 8,
    color: T.accent.cyan,
    padding: '5px 6px',
    background: 'rgba(0,229,200,0.04)',
    borderRadius: 3,
    border: `1px solid rgba(0,229,200,0.1)`,
    lineHeight: 1.4,
    fontStyle: 'italic',
  },
  footer: {
    fontSize: 7,
    color: T.text.faint,
    textAlign: 'center' as const,
    letterSpacing: 0.5,
  },
};
