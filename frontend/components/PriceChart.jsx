import { useEffect, useRef } from 'react'
import { createChart, CrosshairMode } from 'lightweight-charts'

export default function PriceChart({ trades, flow }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)
  const candleRef = useRef({ open: 0, high: 0, low: Infinity, close: 0, time: 0 })
  const bubblesRef = useRef([])

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#0a0a0f' },
        textColor: '#555',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: '#111' },
        horzLines: { color: '#111' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#333', labelBackgroundColor: '#1a1a2e' },
        horzLine: { color: '#333', labelBackgroundColor: '#1a1a2e' },
      },
      rightPriceScale: {
        borderColor: '#1a1a2e',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: '#1a1a2e',
        timeVisible: true,
        secondsVisible: false,
      },
    })

    const series = chart.addCandlestickSeries({
      upColor: '#00e676',
      downColor: '#ff1744',
      borderUpColor: '#00e676',
      borderDownColor: '#ff1744',
      wickUpColor: '#00e676',
      wickDownColor: '#ff1744',
    })

    chartRef.current = chart
    seriesRef.current = series

    const ro = new ResizeObserver(() => {
      chart.applyOptions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight,
      })
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [])

  // Update candles from trade stream
  useEffect(() => {
    if (!seriesRef.current || !trades.length) return

    const trade = trades[0] // newest
    const candleOpen = Math.floor(trade.timestamp / 60) * 60
    const c = candleRef.current

    if (candleOpen !== c.time) {
      // New candle — commit previous
      if (c.time > 0 && c.open > 0) {
        seriesRef.current.update({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low === Infinity ? c.open : c.low,
          close: c.close,
        })
      }
      c.time = candleOpen
      c.open = trade.price
      c.high = trade.price
      c.low = trade.price
      c.close = trade.price
    } else {
      c.high = Math.max(c.high, trade.price)
      c.low = Math.min(c.low, trade.price)
      c.close = trade.price
    }

    // Live update current candle
    seriesRef.current.update({
      time: c.time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    })
  }, [trades])

  // Overlay bubble markers on large trades
  useEffect(() => {
    if (!seriesRef.current || !trades.length) return
    const trade = trades[0]
    const marker = {
      time: Math.floor(trade.timestamp / 60) * 60,
      position: trade.side === 'buy' ? 'belowBar' : 'aboveBar',
      color: trade.side === 'buy' ? '#00e676' : '#ff1744',
      shape: trade.side === 'buy' ? 'arrowUp' : 'arrowDown',
      text: `${trade.qty.toFixed(2)} BTC`,
      size: trade.qty > 2 ? 3 : trade.qty > 1 ? 2 : 1,
    }
    bubblesRef.current.push(marker)
    if (bubblesRef.current.length > 200) bubblesRef.current = bubblesRef.current.slice(-200)
    seriesRef.current.setMarkers(bubblesRef.current)
  }, [trades])

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
  )
}
