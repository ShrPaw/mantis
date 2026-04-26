// MANTIS Dashboard — Main Application Layout
import './styles/global.css';
import { useWebSocket } from './hooks/useWebSocket';
import { useStore } from './store';
import { StatusBar } from './components/StatusBar';
import { PriceChart } from './components/PriceChart';
import { FlowPanel } from './components/FlowPanel';
import { Heatmap } from './components/Heatmap';
import { BubbleTape } from './components/BubbleTape';
import { TradeTape } from './components/TradeTape';
import { Footprint } from './components/Footprint';
import { MicroPanel } from './components/MicroPanel';
import { SessionContext } from './components/SessionContext';
import { NewsPanel } from './components/NewsPanel';

export default function App() {
  useWebSocket();

  const flow = useStore(s => s.flow);
  const connected = useStore(s => s.connected);

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.logo}>◆</span>
          <span style={styles.title}>MANTIS</span>
          <span style={styles.subtitle}>BTC MICROSTRUCTURE</span>
          <span style={styles.source}>HYPERLIQUID</span>
        </div>
        <StatusBar connected={connected} flow={flow} />
      </header>

      {/* Main Grid */}
      <div style={styles.grid}>
        {/* Left Column: Flow + Micro */}
        <aside style={styles.leftCol}>
          <FlowPanel />
          <MicroPanel />
        </aside>

        {/* Center: Chart + Footprint */}
        <main style={styles.center}>
          <div style={styles.chartArea}>
            <PriceChart />
          </div>
          <div style={styles.footprintArea}>
            <Footprint />
          </div>
        </main>

        {/* Right Column: Heatmap + Bubbles */}
        <aside style={styles.rightCol}>
          <div style={styles.heatmapArea}>
            <Heatmap />
          </div>
          <div style={styles.bubbleArea}>
            <BubbleTape />
          </div>
        </aside>

        {/* Bottom: Trade Tape */}
        <footer style={styles.bottom}>
          <TradeTape />
        </footer>

        {/* Far Right: Sessions + News */}
        <aside style={styles.farRight}>
          <SessionContext />
          <NewsPanel />
        </aside>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
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
    padding: '6px 16px',
    borderBottom: '1px solid #1a1a2e',
    background: '#0d0d14',
    flexShrink: 0,
    height: 36,
    zIndex: 10,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  logo: {
    fontSize: 16,
    color: '#f0b90b',
  },
  title: {
    fontSize: 14,
    fontWeight: 700,
    color: '#f0b90b',
    letterSpacing: 2,
  },
  subtitle: {
    fontSize: 9,
    color: '#555',
    letterSpacing: 3,
    textTransform: 'uppercase',
  },
  source: {
    fontSize: 8,
    color: '#333',
    letterSpacing: 2,
    padding: '2px 6px',
    border: '1px solid #1a1a2e',
    borderRadius: 3,
  },
  grid: {
    flex: 1,
    display: 'grid',
    gridTemplateColumns: '220px 1fr 280px 200px',
    gridTemplateRows: '1fr 160px',
    gap: 1,
    background: '#1a1a2e',
    overflow: 'hidden',
  },
  leftCol: {
    gridRow: '1 / 3',
    background: '#0d0d14',
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column',
  },
  center: {
    display: 'flex',
    flexDirection: 'column',
    background: '#0a0a0f',
    overflow: 'hidden',
  },
  chartArea: {
    flex: 1,
    minHeight: 0,
    position: 'relative',
  },
  footprintArea: {
    height: 200,
    borderTop: '1px solid #1a1a2e',
    flexShrink: 0,
  },
  rightCol: {
    gridRow: '1 / 3',
    display: 'flex',
    flexDirection: 'column',
    background: '#0d0d14',
    overflow: 'hidden',
  },
  heatmapArea: {
    flex: 1,
    overflow: 'hidden',
    minHeight: 0,
  },
  bubbleArea: {
    height: 260,
    borderTop: '1px solid #1a1a2e',
    overflow: 'auto',
    flexShrink: 0,
  },
  bottom: {
    gridColumn: '2 / 3',
    background: '#0d0d14',
    borderTop: '1px solid #1a1a2e',
    overflow: 'hidden',
  },
  farRight: {
    gridRow: '1 / 3',
    display: 'flex',
    flexDirection: 'column',
    background: '#0d0d14',
    overflow: 'auto',
    borderLeft: '1px solid #1a1a2e',
  },
};
