import { useRef, useEffect } from 'react'
import { formatPrice, formatVol } from '../utils/format'

export default function Heatmap({ data }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)
    const W = rect.width
    const H = rect.height

    ctx.clearRect(0, 0, W, H)

    const { bids = [], asks = [], mid = 0 } = data
    if (!bids.length && !asks.length) {
      ctx.fillStyle = '#333'
      ctx.font = '11px monospace'
      ctx.fillText('Waiting for order book...', W / 2 - 80, H / 2)
      return
    }

    const allLevels = [...bids, ...asks]
    const maxQty = Math.max(...allLevels.map(l => l.qty), 0.001)
    const rowH = Math.min(H / (allLevels.length + 2), 22)
    const startY = 20

    // Title
    ctx.fillStyle = '#555'
    ctx.font = '9px monospace'
    ctx.fillText('ORDER BOOK HEATMAP', 8, 12)

    // Mid price line
    const midY = startY + bids.length * rowH
    ctx.strokeStyle = '#f0b90b'
    ctx.lineWidth = 1
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(0, midY)
    ctx.lineTo(W, midY)
    ctx.stroke()
    ctx.setLineDash([])

    ctx.fillStyle = '#f0b90b'
    ctx.font = 'bold 10px monospace'
    ctx.fillText(`MID: ${formatPrice(mid)}`, 8, midY - 3)

    // Draw bids (green, below mid)
    bids.forEach((bid, i) => {
      const y = startY + i * rowH
      const w = (bid.qty / maxQty) * (W - 80)

      // Background bar
      ctx.fillStyle = 'rgba(0, 200, 83, 0.12)'
      ctx.fillRect(60, y, w, rowH - 2)

      // Border glow for large orders
      if (bid.qty > maxQty * 0.5) {
        ctx.shadowColor = '#00c853'
        ctx.shadowBlur = 12
        ctx.fillStyle = 'rgba(0, 200, 83, 0.3)'
        ctx.fillRect(60, y, w, rowH - 2)
        ctx.shadowBlur = 0
      }

      // Price label
      ctx.fillStyle = '#00e676'
      ctx.font = '9px monospace'
      ctx.textAlign = 'right'
      ctx.fillText(formatPrice(bid.price), 55, y + rowH - 5)
      ctx.textAlign = 'left'

      // Volume
      ctx.fillStyle = '#00e67680'
      ctx.font = '8px monospace'
      ctx.fillText(bid.qty.toFixed(3), 62 + w, y + rowH - 5)
    })

    // Draw asks (red, above mid)
    asks.forEach((ask, i) => {
      const y = midY + 8 + i * rowH
      const w = (ask.qty / maxQty) * (W - 80)

      ctx.fillStyle = 'rgba(255, 23, 68, 0.12)'
      ctx.fillRect(60, y, w, rowH - 2)

      if (ask.qty > maxQty * 0.5) {
        ctx.shadowColor = '#ff1744'
        ctx.shadowBlur = 12
        ctx.fillStyle = 'rgba(255, 23, 68, 0.3)'
        ctx.fillRect(60, y, w, rowH - 2)
        ctx.shadowBlur = 0
      }

      ctx.fillStyle = '#ff1744'
      ctx.font = '9px monospace'
      ctx.textAlign = 'right'
      ctx.fillText(formatPrice(ask.price), 55, y + rowH - 5)
      ctx.textAlign = 'left'

      ctx.fillStyle = '#ff174480'
      ctx.font = '8px monospace'
      ctx.fillText(ask.qty.toFixed(3), 62 + w, y + rowH - 5)
    })
  }, [data])

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '100%', display: 'block' }}
    />
  )
}
