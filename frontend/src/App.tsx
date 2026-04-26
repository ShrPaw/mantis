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
import { EventPanel } from './components/EventPanel';

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

      {/* Main Content Area */}
      <div style={styles.main}>
        {/* Left Column: Flow + Micro */}
        <div style={styles.leftCol}>
          <FlowPanel />
          <MicroPanel />
        </div>

        {/* Center Column: Chart + Footprint + Tape */}
        <div style={styles.centerCol}>
          <div style={styles.chartWrap}>
            <PriceChart />
          </div>
          <div style={styles.footprintWrap}>
            <Footprint />
          </div>
          <div style={styles.tapeWrap}>
            <TradeTape />
          </div>
        </div>

        {/* Right Column: Heatmap + Bubbles */}
        <div style={styles.rightCol}>
          <div style={styles.heatmapWrap}>
            <Heatmap />
          </div>
          <div style={styles.bubbleWrap}>
            <BubbleTape />
          </div>
        </div>

        {/* Event Engine Column */}
        <div style={styles.eventCol}>
          <EventPanel />
        </div>

        {/* Far Right Column: Sessions + News */}
        <div style={styles.farRightCol}>
          <SessionContext />
          <NewsPanel />
        </div>
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
    textTransform: 'uppercase' as const,
  },
  source: {
    fontSize: 8,
    color: '#333',
    letterSpacing: 2,
    padding: '2px 6px',
    border: '1px solid #1a1a2e',
    borderRadius: 3,
  },
  // 5-column horizontal layout
  main: {
    flex: 1,
    display: 'flex',
    flexDirection: 'row',
    overflow: 'hidden',
    minHeight: 0,
  },
  leftCol: {
    width: 230,
    flexShrink: 0,
    background: '#0d0d14',
    borderRight: '1px solid #1a1a2e',
    overflow: 'auto',
    display: 'flex',
    flexDirection: 'column',
  },
  centerCol: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    background: '#0a0a0f',
    overflow: 'hidden',
    minWidth: 0,
  },
  chartWrap: {
    flex: 1,
    minHeight: 200,
    position: 'relative',
  },
  footprintWrap: {
    height: 200,
    flexShrink: 0,
    borderTop: '1px solid #1a1a2e',
  },
  tapeWrap: {
    height: 160,
    flexShrink: 0,
    borderTop: '1px solid #1a1a2e',
    background: '#0d0d14',
  },
  rightCol: {
    width: 280,
    flexShrink: 0,
    background: '#0d0d14',
    borderLeft: '1px solid #1a1a2e',
    borderRight: '1px solid #1a1a2e',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  heatmapWrap: {
    flex: 1,
    minHeight: 0,
    overflow: 'hidden',
  },
  bubbleWrap: {
    height: 280,
    flexShrink: 0,
    borderTop: '1px solid #1a1a2e',
    overflow: 'auto',
  },
  eventCol: {
    width: 300,
    flexShrink: 0,
    background: '#0a0a0f',
    borderRight: '1px solid #1a1a2e',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  },
  farRightCol: {
    width: 200,
    flexShrink: 0,
    background: '#0d0d14',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'auto',
  },
};
