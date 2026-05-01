// MANTIS Operator Dashboard — Observation Logger Panel (holographic theme)
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

function formatSize(b: number | undefined): string {
  if (!b) return '—';
  if (b < 1024) return `${b}B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)}KB`;
  return `${(b / 1048576).toFixed(1)}MB`;
}

function timeAgo(ts: number | null | undefined): string {
  if (!ts) return '—';
  const s = Math.floor(Date.now() / 1000 - ts);
  if (s < 0) return 'just now';
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export const ObservationLoggerPanel: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const obs = status?.observation_logger;

  return (
    <div style={S.panel}>
      <div style={S.title}>OBSERVATION LOGGER</div>

      {!obs?.detected ? (
        <div style={S.notDetected}>
          <span style={{ fontSize: 20, color: T.text.faint }}>◉</span>
          <span style={{ color: T.text.dim, fontWeight: 600, fontSize: 10 }}>Logger not detected</span>
          <div style={{ fontSize: 8, color: T.text.muted, textAlign: 'center', lineHeight: 1.5 }}>
            Start with:
            <code style={{ display: 'block', marginTop: 3, padding: '3px 6px', background: T.bg.card, borderRadius: 3, color: T.text.dim, fontSize: 8 }}>
              python scripts/run_short_stress_observation.py --interval 30
            </code>
          </div>
        </div>
      ) : (
        <>
          <div style={{ marginBottom: 6 }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: T.green.primary, letterSpacing: 1, textShadow: `0 0 8px ${T.green.glow}` }}>● ACTIVE</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 4 }}>
            <FileRow label="Health" file={obs?.health_file} ts={obs?.last_health_ts} />
            <FileRow label="Metrics" file={obs?.metrics_file} ts={obs?.last_metrics_ts} />
            <FileRow label="Events" file={obs?.events_file} ts={obs?.last_event_ts} />
            <FileRow label="Summary" file={obs?.summary_file} />
          </div>
          <div style={{ height: 1, background: T.border.dim, margin: '8px 0' }} />
          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 3 }}>
            <StatRow label="Unique events" value={(obs?.unique_events ?? 0).toString()} />
            <StatRow label="Acct violations" value={(obs?.accounting_violations ?? 0).toString()} color={obs?.accounting_violations ? T.status.danger : T.green.primary} />
            <StatRow label="OO violations" value={(obs?.observation_only_violations ?? 0).toString()} color={obs?.observation_only_violations ? T.status.danger : T.green.primary} />
          </div>
        </>
      )}
    </div>
  );
};

const FileRow: React.FC<{ label: string; file: any; ts?: number | null }> = ({ label, file, ts }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 9 }}>
    <span style={{ color: T.text.dim }}>{label}</span>
    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ color: file?.exists ? T.green.primary : T.text.muted, fontSize: 8 }}>{file?.exists ? formatSize(file.size) : 'missing'}</span>
      {ts && <span style={{ color: T.text.faint, fontSize: 8 }}>{timeAgo(ts)}</span>}
    </span>
  </div>
);

const StatRow: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10 }}>
    <span style={{ color: T.text.dim }}>{label}</span>
    <span style={{ color: color || T.text.main, fontWeight: 600 }}>{value}</span>
  </div>
);

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: `linear-gradient(180deg, ${T.bg.panel} 0%, ${T.bg.surface} 100%)`,
    border: `1px solid ${T.border.mid}`,
    borderRadius: 6,
    padding: '10px 12px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  title: { fontSize: 9, fontWeight: 700, color: T.green.primary, letterSpacing: 2, marginBottom: 8, textShadow: `0 0 8px ${T.green.glow}` },
  notDetected: { flex: 1, display: 'flex', flexDirection: 'column' as const, alignItems: 'center', justifyContent: 'center', gap: 6 },
};
