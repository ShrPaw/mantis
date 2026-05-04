// MANTIS Dashboard — Price Chart with lightweight-charts
import { useEffect, useRef } from 'react';
import { createChart, CrosshairMode, type IChartApi, type ISeriesApi, type CandlestickData, type LineData } from 'lightweight-charts';
import { useStore } from '../store';
import { theme } from '../styles/theme';

export function PriceChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const vwapRef = useRef<ISeriesApi<'Line'> | null>(null);
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
        textColor: '#555',
        fontSize: 10,
        fontFamily: theme.font,
      },
      grid: {
        vertLines: { color: '#151520' },
        horzLines: { color: '#151520' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#f0b90b40', labelBackgroundColor: '#1a1a2e', width: 1, style: 2 },
        horzLine: { color: '#f0b90b40', labelBackgroundColor: '#1a1a2e', width: 1, style: 2 },
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
      handleScroll: { vertTouchDrag: false },
      handleScale: {
        axisPressedMouseMove: { price: false, time: true },
        mouseWheel: true,
        pinch: true,
      },
    });

    // Candlestick series — high contrast
    const series = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderVisible: true,
      wickVisible: true,
    });

    // VWAP line
    const vwapSeries = chart.addLineSeries({
      color: '#f0b90b60',
      lineWidth: 1,
      lineStyle: 2, // Dashed
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    chartRef.current = chart;
    seriesRef.current = series;
    vwapRef.current = vwapSeries;

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
      vwapRef.current = null;
    };
  }, []);

  // Load historical candles + VWAP
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

    // Build VWAP line from candle data
    let cumVol = 0;
    let cumVolPrice = 0;
    const vwapData: LineData[] = [];
    for (const c of candles) {
      const typical = (c.high + c.low + c.close) / 3;
      cumVolPrice += typical * c.volume;
      cumVol += c.volume;
      if (cumVol > 0) {
        vwapData.push({ time: c.time as any, value: cumVolPrice / cumVol });
      }
    }
    vwapRef.current?.setData(vwapData);

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

    const trade = largeTrades[0];
    if (!trade || trade.qty < 0.5) return;

    const marker = {
      time: Math.floor(trade.timestamp / 60) * 60 as any,
      position: trade.side === 'buy' ? 'belowBar' as const : 'aboveBar' as const,
      color: trade.side === 'buy' ? '#26a69a' : '#ef5350',
      shape: trade.side === 'buy' ? 'arrowUp' as const : 'arrowDown' as const,
      text: `${trade.qty.toFixed(2)}`,
      size: trade.qty > 2 ? 3 : trade.qty > 1 ? 2 : 1,
    };

    markersRef.current.push(marker);
    if (markersRef.current.length > 300) {
      markersRef.current = markersRef.current.slice(-300);
    }

    markersRef.current.sort((a, b) => (a.time as number) - (b.time as number));
    seriesRef.current.setMarkers(markersRef.current);
  }, [largeTrades]);

  return (
    <div style={styles.wrapper}>
      {/* Legend overlay */}
      <div style={styles.legend}>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendDot, background: '#26a69a' }} />
          <span>Bullish</span>
        </span>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendDot, background: '#ef5350' }} />
          <span>Bearish</span>
        </span>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendDot, background: '#f0b90b', height: 1, borderRadius: 0, width: 10 }} />
          <span>VWAP</span>
        </span>
        <span style={styles.legendItem}>
          <span style={{ ...styles.legendDot, background: '#f0b90b' }} />
          <span style={{ fontSize: 8 }}>Large trade</span>
        </span>
      </div>
      <div style={styles.label}>1m CANDLES · SCROLL TO ZOOM</div>
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
  legend: {
    position: 'absolute',
    top: 6,
    left: 10,
    zIndex: 5,
    pointerEvents: 'none',
    display: 'flex',
    gap: 12,
    alignItems: 'center',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    fontSize: 8,
    color: '#555',
  },
  legendDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    display: 'inline-block',
  },
  label: {
    position: 'absolute',
    top: 6,
    right: 10,
    zIndex: 5,
    pointerEvents: 'none',
    fontSize: 8,
    color: '#333',
    letterSpacing: 1,
  },
};
