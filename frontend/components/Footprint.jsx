import { useRef, useEffect } from 'react'
import { formatPrice, formatVol, formatDelta } from '../utils/format'

export default function Footprint({ data }) {
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

    if (!data || data.length === 0) {
      ctx.fillStyle = '#333'
      ctx.font = '11px monospace'
      ctx.fillText('Building footprint data...', W / 2 - 80, H / 2)
      return
    }

    ctx.fillStyle = '#555'
    ctx.font = '9px monospace'
    ctx.fillText('FOOTPRINT (LAST 10 CANDLES)', 8, 12)

    // Show last N candles that fit
    const candles = data.slice(-10)
    const candleW = Math.min(120, (W - 20) / candles.length)
    const startX = 10
    const topY = 24
    const maxH = H - topY - 10

    // Find global max volume for scaling
    let globalMaxVol = 0
    for (const c of candles) {
      for (const lv of c.levels) {
        globalMaxVol = Math.max(globalMaxVol, lv.bid_vol + lv.ask_vol)
      }
    }
    if (globalMaxVol === 0) globalMaxVol = 1

    candles.forEach((candle, ci) => {
      const x = startX + ci * candleW

      // Candle header
      const isOpen = candle.open > 0
      const isGreen = candle.close >= candle.open
      const color = isGreen ? '#00e676' : '#ff1744'

      // OHLC mini bar
      ctx.fillStyle = color + '30'
      ctx.fillRect(x, topY, candleW - 4, maxH)

      // Header: time + delta
      const mins = new Date(candle.open_time * 1000).toTimeString().slice(0, 5)
      ctx.fillStyle = '#888'
      ctx.font = '8px monospace'
      ctx.fillText(mins, x + 2, topY + 10)

      ctx.fillStyle = candle.total_delta >= 0 ? '#00e676' : '#ff1744'
      ctx.font = '8px monospace'
      ctx.fillText(`Δ${formatDelta(candle.total_delta)}`, x + 2, topY + 20)

      // Volume levels (top 8 by volume)
      const levels = candle.levels
        .sort((a, b) => (b.bid_vol + b.ask_vol) - (a.bid_vol + a.ask_vol))
        .slice(0, 8)

      levels.forEach((lv, li) => {
        const ly = topY + 28 + li * 14
        if (ly > H - 10) return

        const total = lv.bid_vol + lv.ask_vol
        const barW = ((total / globalMaxVol) * (candleW - 20))

        // Bid bar (left)
        const bidW = (lv.bid_vol / total) * barW
        ctx.fillStyle = 'rgba(0, 230, 118, 0.25)'
        ctx.fillRect(x + 2, ly, bidW, 10)

        // Ask bar (right)
        ctx.fillStyle = 'rgba(255, 23, 68, 0.25)'
        ctx.fillRect(x + 2 + bidW, ly, barW - bidW, 10)

        // Imbalance highlight
        if (Math.abs(lv.imbalance) > 0.6) {
          ctx.strokeStyle = lv.imbalance > 0 ? '#00e676' : '#ff1744'
          ctx.lineWidth = 1
          ctx.strokeRect(x + 1, ly, barW + 2, 10)
        }

        // Price label
        ctx.fillStyle = '#aaa'
        ctx.font = '7px monospace'
        ctx.fillText(lv.price.toFixed(1), x + barW + 6, ly + 8)
      })

      // Total volume footer
      ctx.fillStyle = '#555'
      ctx.font = '7px monospace'
      ctx.fillText(`V:${candle.total_vol.toFixed(2)}`, x + 2, H - 4)
    })
  }, [data])

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: '100%', display: 'block' }}
    />
  )
}
