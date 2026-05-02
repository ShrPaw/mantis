// MANTIS Operator Dashboard — L3 1M Displacement Diagnostic Panel
// Shadow diagnostic showing production L3 status + 5 shadow variant evaluations
import React, { useEffect, useState, useCallback } from 'react';
import { T } from '../styles/operatorTheme';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const POLL_INTERVAL = 5000; // 5 seconds

interface L3CalibrationData {
  timestamp: number;
  candles_evaluated: number;
  production_l3_status: string;
  production_l3_block_reason: string;
  shadow_3c_pass: boolean;
  shadow_stress_pass: boolean;
  shadow_single_candle_pass: boolean;
  shadow_5c_pass: boolean;
  current: {
    body_bps: number;
    range_bps: number;
    close_to_close_bps: number;
    '3c_leg_bps': number;
    '5c_leg_bps': number;
    directional_efficiency_3c: number;
    directional_efficiency_5c: number;
    pullback_ratio: number;
    max_extension_bps: number;
    volume_percentile: number;
    volatility_percentile: number;
  };
  percentile_ranks: Record<string, number>;
  interpretation: string;
}

const STATUS_COLORS: Record<string, string> = {
  PASS: T.status.success,
  FAIL: T.status.danger,
  NOT_EVALUATED: T.text.muted,
};

function StatusBadge({ label, pass, prod }: { label: string; pass: boolean; prod?: string }) {
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
  label: string; value: number | string; unit?: string; rank?: number;
}) {
  return (
    <div style={S.metricRow}>
      <span style={S.metricLabel}>{label}</span>
      <span style={S.metricValue}>
        {typeof value === 'number' ? value.toFixed(2) : value}
        {unit && <span style={S.metricUnit}>{unit}</span>}
      </span>
      {rank !== undefined && (
        <span style={{
          ...S.rankBadge,
          color: rank >= 0.85 ? T.status.success : rank >= 0.6 ? T.status.warning : T.text.muted,
        }}>
          p{(rank * 100).toFixed(0)}
        </span>
      )}
    </div>
  );
}

export const L3DiagnosticPanel: React.FC = () => {
  const [data, setData] = useState<L3CalibrationData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/l3/calibration`);
      if (!resp.ok) return;
      const json = await resp.json();
      if (json.status === 'event_engine_disabled' || json.status === 'l3_calibrator_not_loaded') {
        setError(json.status);
        return;
      }
      setData(json);
      setError(null);
    } catch {
      // silent — panel just won't update
    }
  }, []);

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, POLL_INTERVAL);
    return () => clearInterval(timer);
  }, [fetchData]);

  if (error) {
    return (
      <div style={S.panel}>
        <div style={S.title}>L3 1M DISPLACEMENT DIAGNOSTIC</div>
        <div style={S.empty}>Calibrator {error === 'l3_calibrator_not_loaded' ? 'not loaded' : 'disabled'}</div>
      </div>
    );
  }

  if (!data || data.candles_evaluated < 5) {
    return (
      <div style={S.panel}>
        <div style={S.title}>L3 1M DISPLACEMENT DIAGNOSTIC</div>
        <div style={S.empty}>
          Warming up — {data?.candles_evaluated ?? 0}/5 candles
        </div>
      </div>
    );
  }

  const c = data.current;
  const ranks = data.percentile_ranks;

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
        <MetricRow label="body" value={c.body_bps} unit=" bps" rank={ranks.body_bps_rank_60} />
        <MetricRow label="range" value={c.range_bps} unit=" bps" rank={ranks.range_bps_rank_60} />
        <MetricRow label="3c leg" value={c['3c_leg_bps']} unit=" bps" rank={ranks['3c_leg_bps_rank_60']} />
        <MetricRow label="5c leg" value={c['5c_leg_bps']} unit=" bps" rank={ranks['5c_leg_bps_rank_60']} />
        <MetricRow label="eff 3c" value={c.directional_efficiency_3c} />
        <MetricRow label="eff 5c" value={c.directional_efficiency_5c} />
        <MetricRow label="pullback" value={c.pullback_ratio} />
        <MetricRow label="vol pct" value={(c.volume_percentile * 100).toFixed(0) + '%'} />
        <MetricRow label="vol rank" value={(c.volatility_percentile * 100).toFixed(0) + '%'} />
      </div>

      {/* Interpretation */}
      <div style={S.interpretation}>
        {data.interpretation}
      </div>

      {/* Footer */}
      <div style={S.footer}>
        {data.candles_evaluated} candles evaluated
      </div>
    </div>
  );
};

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
