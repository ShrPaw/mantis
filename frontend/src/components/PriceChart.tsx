// MANTIS Dashboard — Price Chart with lightweight-charts
import { useEffect, useRef } from 'react';
import { createChart, CrosshairMode, type IChartApi, type ISeriesApi, type CandlestickData } from 'lightweight-charts';
import { useStore } from '../store';
import { theme } from '../styles/theme';

export function PriceChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersRef = useRef<any[]>([]);
  const loadedRef = useRef(false);
  const candleRef = useRef({ time: 0, open: 0, high: 0, low: Infinity, close: 0 });

  const candles = useStore(s => s.candles);
  const largeTrades = useStore(s => s.largeTrades);
  const flow = useStore(s => s.flow);

  // Init chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: theme.bg },
        textColor: '#444',
        fontSize: 10,
        fontFamily: theme.font,
      },
      grid: {
        vertLines: { color: '#111118' },
        horzLines: { color: '#111118' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#333', labelBackgroundColor: '#1a1a2e', width: 1 },
        horzLine: { color: '#333', labelBackgroundColor: '#1a1a2e', width: 1 },
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
      handleScroll: true,
      handleScale: true,
    });

    const series = chart.addCandlestickSeries({
      upColor: '#00c853',
      downColor: '#ff1744',
      borderUpColor: '#00c853',
      borderDownColor: '#ff1744',
      wickUpColor: '#00c85380',
      wickDownColor: '#ff174480',
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Load historical candles
  useEffect(() => {
    if (!seriesRef.current || !candles.length || loadedRef.current) return;
    loadedRef.current = true;

    const formatted: CandlestickData[] = candles.map(c => ({
      time: c.time as any,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    seriesRef.current.setData(formatted);

    const last = candles[candles.length - 1];
    candleRef.current = {
      time: last.time,
      open: last.open,
      high: last.high,
      low: last.low,
      close: last.close,
    };

    chartRef.current?.timeScale().scrollToRealTime();
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  // Update live candle from flow changes
  useEffect(() => {
    if (!seriesRef.current || flow.last_price <= 0) return;

    const now = Math.floor(Date.now() / 1000);
    const candleOpen = Math.floor(now / 60) * 60;
    const c = candleRef.current;
    const price = flow.last_price;

    if (candleOpen !== c.time) {
      if (c.time > 0 && c.open > 0) {
        seriesRef.current.update({
          time: c.time as any,
          open: c.open,
          high: c.high,
          low: c.low === Infinity ? c.open : c.low,
          close: c.close,
        });
      }
      c.time = candleOpen;
      c.open = price;
      c.high = price;
      c.low = price;
      c.close = price;
    } else {
      c.high = Math.max(c.high, price);
      c.low = Math.min(c.low, price);
      c.close = price;
    }

    seriesRef.current.update({
      time: c.time as any,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    });
  }, [flow.last_price]);

  // Add large trade markers
  useEffect(() => {
    if (!seriesRef.current || largeTrades.length === 0) return;

    // Only add the newest marker
    const trade = largeTrades[0];
    if (!trade || trade.qty < 0.5) return;

    const marker = {
      time: Math.floor(trade.timestamp / 60) * 60 as any,
      position: trade.side === 'buy' ? 'belowBar' as const : 'aboveBar' as const,
      color: trade.side === 'buy' ? '#00e676' : '#ff1744',
      shape: trade.side === 'buy' ? 'arrowUp' as const : 'arrowDown' as const,
      text: `${trade.qty.toFixed(2)} BTC`,
      size: trade.qty > 2 ? 3 : trade.qty > 1 ? 2 : 1,
    };

    markersRef.current.push(marker);
    if (markersRef.current.length > 300) {
      markersRef.current = markersRef.current.slice(-300);
    }

    // Sort by time
    markersRef.current.sort((a, b) => (a.time as number) - (b.time as number));
    seriesRef.current.setMarkers(markersRef.current);
  }, [largeTrades]);

  return (
    <div style={styles.wrapper}>
      {/* Overlay info */}
      <div style={styles.overlay}>
        <div style={styles.overlayLabel}>1m CANDLES</div>
      </div>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    width: '100%',
    height: '100%',
    position: 'relative',
  },
  overlay: {
    position: 'absolute',
    top: 8,
    left: 12,
    zIndex: 5,
    pointerEvents: 'none',
  },
  overlayLabel: {
    fontSize: 9,
    color: '#333',
    letterSpacing: 2,
  },
};
