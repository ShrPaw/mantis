// MANTIS Operator Dashboard — Observation Logger Panel
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';

function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

function timeAgo(ts: number | null | undefined): string {
  if (!ts) return '—';
  const sec = Math.floor(Date.now() / 1000 - ts);
  if (sec < 0) return 'just now';
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

export const ObservationLoggerPanel: React.FC = () => {
  const status = useOperatorStore(s => s.status);
  const obs = status?.observation_logger;

  return (
    <div style={S.panel}>
      <div style={S.title}>OBSERVATION LOGGER</div>

      {!obs?.detected ? (
        <div style={S.notDetected}>
          <div style={S.notDetectedIcon}>◉</div>
          <div style={S.notDetectedText}>Observation logger not detected</div>
          <div style={S.notDetectedCmd}>
            Start it with:
            <code style={S.code}>python scripts/run_short_stress_observation.py --interval 30</code>
          </div>
        </div>
      ) : (
        <>
          <div style={S.statusRow}>
            <span style={S.activeBadge}>● ACTIVE</span>
          </div>

          <div style={S.fileGrid}>
            <FileRow label="Health" file={obs?.health_file} ts={obs?.last_health_ts} />
            <FileRow label="Metrics" file={obs?.metrics_file} ts={obs?.last_metrics_ts} />
            <FileRow label="Events" file={obs?.events_file} ts={obs?.last_event_ts} />
            <FileRow label="Summary" file={obs?.summary_file} />
          </div>

          <div style={S.divider} />

          <div style={S.stats}>
            <StatRow label="Unique SPE events" value={(obs?.unique_events ?? 0).toString()} />
            <StatRow label="Acct violations" value={(obs?.accounting_violations ?? 0).toString()} color={obs?.accounting_violations ? '#ef5350' : '#26a69a'} />
            <StatRow label="OO violations" value={(obs?.observation_only_violations ?? 0).toString()} color={obs?.observation_only_violations ? '#ef5350' : '#26a69a'} />
          </div>
        </>
      )}
    </div>
  );
};

const FileRow: React.FC<{ label: string; file: any; ts?: number | null }> = ({ label, file, ts }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 9 }}>
    <span style={{ color: '#555' }}>{label}</span>
    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{ color: file?.exists ? '#26a69a' : '#555', fontSize: 8 }}>
        {file?.exists ? formatFileSize(file.size) : 'missing'}
      </span>
      {ts && <span style={{ color: '#444', fontSize: 8 }}>{timeAgo(ts)}</span>}
    </span>
  </div>
);

const StatRow: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 10 }}>
    <span style={{ color: '#555' }}>{label}</span>
    <span style={{ color: color || '#ccc', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{value}</span>
  </div>
);

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: '#0c0c14',
    border: '1px solid #1a1a2e',
    borderRadius: 6,
    padding: '10px 12px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
  },
  title: {
    fontSize: 10,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 2,
    marginBottom: 8,
  },
  notDetected: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  notDetectedIcon: {
    fontSize: 24,
    color: '#333',
  },
  notDetectedText: {
    fontSize: 10,
    color: '#555',
    fontWeight: 600,
  },
  notDetectedCmd: {
    fontSize: 8,
    color: '#444',
    textAlign: 'center' as const,
    lineHeight: 1.5,
  },
  code: {
    display: 'block',
    marginTop: 4,
    padding: '3px 6px',
    background: '#111',
    borderRadius: 3,
    color: '#888',
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: 8,
  },
  statusRow: {
    marginBottom: 6,
  },
  activeBadge: {
    fontSize: 10,
    fontWeight: 700,
    color: '#26a69a',
    letterSpacing: 1,
  },
  fileGrid: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 4,
  },
  divider: {
    height: 1,
    background: '#1a1a2e',
    margin: '8px 0',
  },
  stats: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 3,
  },
};
