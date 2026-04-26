// MANTIS Dashboard — Number & time formatting utilities

export function formatPrice(p: number | undefined | null): string {
  if (p == null || !isFinite(p)) return '—';
  return p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatVol(v: number | undefined | null): string {
  if (v == null) return '—';
  if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M';
  if (v >= 1000) return (v / 1000).toFixed(1) + 'K';
  return v.toFixed(3);
}

export function formatDelta(d: number | undefined | null): string {
  if (d == null) return '—';
  const sign = d >= 0 ? '+' : '';
  return sign + d.toFixed(3);
}

export function formatPct(p: number | undefined | null): string {
  if (p == null) return '—';
  return (p * 100).toFixed(1) + '%';
}

export function formatUSD(v: number | undefined | null): string {
  if (v == null) return '—';
  if (v >= 1000000) return '$' + (v / 1000000).toFixed(1) + 'M';
  if (v >= 1000) return '$' + (v / 1000).toFixed(0) + 'K';
  return '$' + v.toFixed(0);
}

export function timeAgo(ts: number): string {
  const sec = Math.floor(Date.now() / 1000 - ts);
  if (sec < 0) return 'now';
  if (sec < 60) return sec + 's';
  if (sec < 3600) return Math.floor(sec / 60) + 'm';
  return Math.floor(sec / 3600) + 'h';
}

export function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toTimeString().slice(0, 8);
}

export function formatSize(s: number): string {
  if (s >= 1) return s.toFixed(2);
  if (s >= 0.01) return s.toFixed(3);
  return s.toFixed(4);
}
