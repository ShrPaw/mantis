import { useEffect, useRef } from 'react'
import { createChart, CrosshairMode } from 'lightweight-charts'

export default function PriceChart({ trades, flow, candles }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)
  const candleRef = useRef({ open: 0, high: 0, low: Infinity, close: 0, time: 0 })
  const bubblesRef = useRef([])
  const loadedRef = useRef(false)

  // Init chart
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#0a0a0f' },
        textColor: '#444',
        fontSize: 10,
      },
      grid: {
        vertLines: { color: '#111118' },
        horzLines: { color: '#111118' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#333', labelBackgroundColor: '#1a1a2e' },
        horzLine: { color: '#333', labelBackgroundColor: '#1a1a2e' },
      },
      rightPriceScale: {
        borderColor: '#1a1a2e',
        scaleMargins: { top: 0.05, bottom: 0.05 },
      },
      timeScale: {
        borderColor: '#1a1a2e',
        timeVisible: true,
        secondsVisible: false,
      },
    })

    const series = chart.addCandlestickSeries({
      upColor: '#00c853',
      downColor: '#ff1744',
      borderUpColor: '#00c853',
      borderDownColor: '#ff1744',
      wickUpColor: '#00c85380',
      wickDownColor: '#ff174480',
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

  // Load historical candles
  useEffect(() => {
    if (!seriesRef.current || !candles || !candles.length || loadedRef.current) return
    loadedRef.current = true

    const formatted = candles.map(c => ({
      time: c.time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }))

    seriesRef.current.setData(formatted)

    // Set current candle state to last historical candle
    const last = candles[candles.length - 1]
    candleRef.current = {
      time: last.time,
      open: last.open,
      high: last.high,
      low: last.low,
      close: last.close,
    }

    // Scroll to latest
    chartRef.current?.timeScale().scrollToRealTime()
  }, [candles])

  // Update candles from live trade stream
  useEffect(() => {
    if (!seriesRef.current || !trades.length) return

    const trade = trades[0]
    const candleOpen = Math.floor(trade.timestamp / 60) * 60
    const c = candleRef.current

    if (candleOpen !== c.time) {
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
    if (!trade.qty || trade.qty < 0.5) return

    const marker = {
      time: Math.floor(trade.timestamp / 60) * 60,
      position: trade.side === 'buy' ? 'belowBar' : 'aboveBar',
      color: trade.side === 'buy' ? '#00c853' : '#ff1744',
      shape: trade.side === 'buy' ? 'arrowUp' : 'arrowDown',
      text: `${trade.qty.toFixed(2)}`,
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
