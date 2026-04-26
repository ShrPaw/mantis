import { useState, useCallback } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import PriceChart from './components/PriceChart'
import FlowPanel from './components/FlowPanel'
import BubbleTape from './components/BubbleTape'
import Heatmap from './components/Heatmap'
import Footprint from './components/Footprint'
import StatusBar from './components/StatusBar'

const WS_URL = `ws://${window.location.hostname}:8000/ws`

export default function App() {
  const [flow, setFlow] = useState({})
  const [heatmap, setHeatmap] = useState({ bids: [], asks: [], mid: 0 })
  const [footprints, setFootprints] = useState([])
  const [largeTrades, setLargeTrades] = useState([])
  const [absorption, setAbsorption] = useState([])
  const [trades, setTrades] = useState([])

  const { connected, on } = useWebSocket(WS_URL)

  // Register stream handlers
  const registered = useCallback(() => {
    on('init', (data) => {
      setFlow(data.flow)
      setHeatmap(data.heatmap)
      setFootprints(data.footprints)
      setLargeTrades(data.large_trades)
      setAbsorption(data.absorption)
    })
    on('flow_metrics', setFlow)
    on('heatmap', setHeatmap)
    on('footprints', setFootprints)
    on('absorption', setAbsorption)
    on('large_trade', (trade) => {
      setLargeTrades(prev => [trade, ...prev].slice(0, 100))
      setTrades(prev => [trade, ...prev].slice(0, 50))
    })
  }, [on])

  // Run once
  useState(() => { registered() })

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div style={styles.title}>
          <span style={styles.symbol}>BTCUSDT</span>
          <span style={styles.sub}>MICROSTRUCTURE</span>
        </div>
        <StatusBar connected={connected} flow={flow} />
      </div>

      {/* Main Grid */}
      <div style={styles.grid}>
        {/* Left: Flow Panel */}
        <div style={styles.leftPanel}>
          <FlowPanel flow={flow} />
        </div>

        {/* Center: Chart + Footprint */}
        <div style={styles.centerPanel}>
          <div style={styles.chartArea}>
            <PriceChart trades={trades} flow={flow} />
          </div>
          <div style={styles.footprintArea}>
            <Footprint data={footprints} />
          </div>
        </div>

        {/* Right: Heatmap + Bubbles */}
        <div style={styles.rightPanel}>
          <div style={styles.heatmapArea}>
            <Heatmap data={heatmap} />
          </div>
          <div style={styles.bubbleArea}>
            <BubbleTape trades={largeTrades} />
          </div>
        </div>
      </div>
    </div>
  )
}

const styles = {
  container: {
    width: '100vw',
    height: '100vh',
    display: 'flex',
    flexDirection: 'column',
    background: '#0a0a0f',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '8px 16px',
    borderBottom: '1px solid #1a1a2e',
    background: '#0d0d14',
    flexShrink: 0,
  },
  title: { display: 'flex', alignItems: 'baseline', gap: 12 },
  symbol: {
    fontSize: 18,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 1,
  },
  sub: {
    fontSize: 10,
    color: '#555',
    letterSpacing: 3,
    textTransform: 'uppercase',
  },
  grid: {
    flex: 1,
    display: 'grid',
    gridTemplateColumns: '240px 1fr 300px',
    gridTemplateRows: '1fr 280px',
    gap: 1,
    background: '#1a1a2e',
    overflow: 'hidden',
  },
  leftPanel: {
    gridRow: '1 / 3',
    background: '#0d0d14',
    overflow: 'auto',
  },
  centerPanel: {
    display: 'flex',
    flexDirection: 'column',
    background: '#0a0a0f',
  },
  chartArea: { flex: 1, minHeight: 0 },
  footprintArea: { height: 280, borderTop: '1px solid #1a1a2e' },
  rightPanel: {
    gridRow: '1 / 3',
    display: 'flex',
    flexDirection: 'column',
    background: '#0d0d14',
  },
  heatmapArea: { flex: 1, overflow: 'hidden' },
  bubbleArea: { height: 280, borderTop: '1px solid #1a1a2e', overflow: 'auto' },
}
