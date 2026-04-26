export function formatPrice(p) {
  return p?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '—'
}

export function formatVol(v) {
  if (v >= 1000) return (v / 1000).toFixed(1) + 'K'
  return v?.toFixed(3) ?? '—'
}

export function formatDelta(d) {
  const sign = d >= 0 ? '+' : ''
  return sign + (d?.toFixed(3) ?? '—')
}

export function formatPct(p) {
  return (p * 100).toFixed(1) + '%'
}

export function timeAgo(ts) {
  const sec = Math.floor(Date.now() / 1000 - ts)
  if (sec < 60) return sec + 's'
  if (sec < 3600) return Math.floor(sec / 60) + 'm'
  return Math.floor(sec / 3600) + 'h'
}
