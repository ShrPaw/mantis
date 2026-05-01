// MANTIS — Main Price Chart with event overlays and annotations
// Central cockpit chart: candlestick + VWAP + session H/L + event markers
import { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, CrosshairMode, type IChartApi, type ISeriesApi, type CandlestickData, type LineData, type Time } from 'lightweight-charts';
import { useStore } from '../store';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

export function MainPriceChart() {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const vwapRef = useRef<ISeriesApi<'Line'> | null>(null);
  const sessionHighRef = useRef<ISeriesApi<'Line'> | null>(null);
  const sessionLowRef = useRef<ISeriesApi<'Line'> | null>(null);
  const markersRef = useRef<any[]>([]);
  const loadedRef = useRef(false);
  const candleRef = useRef({ time: 0, open: 0, high: 0, low: Infinity, close: 0 });
  const [hoveredPrice, setHoveredPrice] = useState<number | null>(null);

  const candles = useStore(s => s.candles);
  const largeTrades = useStore(s => s.largeTrades);
  const events = useStore(s => s.events);
  const flow = useStore(s => s.flow);
  const opStatus = useOperatorStore(s => s.status);
  const opConnected = useOperatorStore(s => s.connected);

  const spe = opStatus?.spe;
  const market = opStatus?.market;

  // Init chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: T.bg.base },
        textColor: T.text.muted,
        fontSize: 10,
        fontFamily: "'JetBrains Mono', monospace",
      },
      grid: {
        vertLines: { color: '#0a1510' },
        horzLines: { color: '#0a1510' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: '#39ff8820', labelBackgroundColor: T.bg.elevated, width: 1, style: 2 },
        horzLine: { color: '#39ff8820', labelBackgroundColor: T.bg.elevated, width: 1, style: 2 },
      },
      rightPriceScale: {
        borderColor: T.border.mid,
        scaleMargins: { top: 0.03, bottom: 0.03 },
      },
      timeScale: {
        borderColor: T.border.mid,
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    });

    // Candlestick series
    const series = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderUpColor: '#26a69a',
      borderDownColor: '#ef5350',
      wickUpColor: '#26a69a80',
      wickDownColor: '#ef535080',
      borderVisible: true,
      wickVisible: true,
    });

    // VWAP line
    const vwapSeries = chart.addLineSeries({
      color: '#f0b90b50',
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // Session High line
    const shSeries = chart.addLineSeries({
      color: '#39ff8820',
      lineWidth: 1,
      lineStyle: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    // Session Low line
    const slSeries = chart.addLineSeries({
      color: '#ff5f5f20',
      lineWidth: 1,
      lineStyle: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    chartRef.current = chart;
    seriesRef.current = series;
    vwapRef.current = vwapSeries;
    sessionHighRef.current = shSeries;
    sessionLowRef.current = slSeries;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight,
        });
      }
    });
    ro.observe(containerRef.current);

    // Track crosshair price
    chart.subscribeCrosshairMove((param) => {
      if (param.seriesData) {
        const d = param.seriesData.get(series);
        if (d && 'close' in d) setHoveredPrice(d.close as number);
      }
    });

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      vwapRef.current = null;
      sessionHighRef.current = null;
      sessionLowRef.current = null;
    };
  }, []);

  // Load historical candles + VWAP + session lines
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

    // VWAP
    let cumVol = 0, cumVolPrice = 0;
    const vwapData: LineData[] = [];
    for (const c of candles) {
      const typical = (c.high + c.low + c.close) / 3;
      cumVolPrice += typical * c.volume;
      cumVol += c.volume;
      if (cumVol > 0) vwapData.push({ time: c.time as any, value: cumVolPrice / cumVol });
    }
    vwapRef.current?.setData(vwapData);

    // Session H/L from last candle range
    const last = candles[candles.length - 1];
    const sessionH = Math.max(...candles.map(c => c.high));
    const sessionL = Math.min(...candles.map(c => c.low));
    if (sessionH > 0) sessionHighRef.current?.setData(candles.map(c => ({ time: c.time as any, value: sessionH })));
    if (sessionL < Infinity) sessionLowRef.current?.setData(candles.map(c => ({ time: c.time as any, value: sessionL })));

    candleRef.current = { time: last.time, open: last.open, high: last.high, low: last.low, close: last.close };
    chartRef.current?.timeScale().scrollToRealTime();
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  // Update live candle from flow
  useEffect(() => {
    if (!seriesRef.current || flow.last_price <= 0) return;
    const now = Math.floor(Date.now() / 1000);
    const candleOpen = Math.floor(now / 60) * 60;
    const c = candleRef.current;
    const price = flow.last_price;

    if (candleOpen !== c.time) {
      if (c.time > 0 && c.open > 0) {
        seriesRef.current.update({ time: c.time as any, open: c.open, high: c.high, low: c.low === Infinity ? c.open : c.low, close: c.close });
      }
      c.time = candleOpen; c.open = price; c.high = price; c.low = price; c.close = price;
    } else {
      c.high = Math.max(c.high, price);
      c.low = Math.min(c.low, price);
      c.close = price;
    }
    seriesRef.current.update({ time: c.time as any, open: c.open, high: c.high, low: c.low, close: c.close });

    // Update session H/L live
    const sh = market?.session_high ?? flow.session_high;
    const sl = market?.session_low ?? flow.session_low;
    if (sh > 0) sessionHighRef.current?.setData([{ time: c.time as any, value: sh }]);
    if (sl < Infinity) sessionLowRef.current?.setData([{ time: c.time as any, value: sl }]);
  }, [flow.last_price, market?.session_high, market?.session_low]);

  // Build markers from events + large trades + SPE state
  useEffect(() => {
    if (!seriesRef.current) return;
    const markers: any[] = [];

    // Large trade markers
    for (const trade of largeTrades.slice(0, 50)) {
      if (trade.qty < 0.3) continue;
      markers.push({
        time: Math.floor(trade.timestamp / 60) * 60 as any,
        position: trade.side === 'buy' ? 'belowBar' as const : 'aboveBar' as const,
        color: trade.side === 'buy' ? '#26a69a' : '#ef5350',
        shape: trade.side === 'buy' ? 'arrowUp' as const : 'arrowDown' as const,
        text: `${trade.qty.toFixed(2)} BTC`,
        size: trade.qty > 2 ? 3 : trade.qty > 1 ? 2 : 1,
      });
    }

    // Event engine markers
    for (const evt of events.slice(0, 30)) {
      const color = evt.event_type === 'absorption' ? '#00e5c8'
        : evt.event_type === 'exhaustion' ? '#ffcc66'
        : evt.event_type === 'liquidity_sweep' ? '#ff5f5f'
        : evt.event_type === 'delta_divergence' ? '#66d9ff'
        : evt.event_type === 'imbalance' ? '#9c27b0'
        : evt.event_type === 'range_break' ? '#ff9800'
        : '#39ff88';
      const shape = evt.side === 'buy' ? 'circle' as const : 'square' as const;
      markers.push({
        time: Math.floor(evt.timestamp / 60) * 60 as any,
        position: evt.side === 'buy' ? 'belowBar' as const : 'aboveBar' as const,
        color,
        shape,
        text: evt.event_type.substring(0, 8),
        size: 1,
      });
    }

    // SPE state markers
    if (spe?.current_state === 'CASCADE' || spe?.current_state === 'UNWIND') {
      markers.push({
        time: Math.floor(Date.now() / 1000 / 60) * 60 as any,
        position: 'aboveBar' as const,
        color: spe.current_state === 'CASCADE' ? '#ff5f5f' : '#ffcc66',
        shape: 'circle' as const,
        text: spe.current_state,
        size: 3,
      });
    }

    markers.sort((a, b) => (a.time as number) - (b.time as number));
    markersRef.current = markers;
    seriesRef.current.setMarkers(markers);
  }, [largeTrades, events, spe?.current_state]);

  const currentPrice = flow.last_price || market?.last_price || 0;
  const priceChange = candles.length >= 2 ? currentPrice - candles[candles.length - 2]?.close : 0;
  const priceChangePct = candles.length >= 2 && candles[candles.length - 2]?.close > 0
    ? (priceChange / candles[candles.length - 2].close * 100) : 0;

  return (
    <div style={S.wrapper}>
      {/* Top bar overlay */}
      <div style={S.topBar}>
        <div style={S.priceBlock}>
          <span style={S.symbol}>BTC/USD</span>
          <span style={S.price}>
            {currentPrice > 0 ? `$${currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—'}
          </span>
          <span style={{
            ...S.change,
            color: priceChange >= 0 ? T.green.primary : T.status.danger,
          }}>
            {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)} ({priceChangePct >= 0 ? '+' : ''}{priceChangePct.toFixed(2)}%)
          </span>
        </div>
        <div style={S.metaBlock}>
          <MetaChip label="H" value={market?.session_high ? `$${market.session_high.toLocaleString()}` : '—'} color={T.green.primary} />
          <MetaChip label="L" value={market?.session_low ? `$${market.session_low.toLocaleString()}` : '—'} color={T.status.danger} />
          <MetaChip label="VWAP" value={market?.vwap ? `$${market.vwap.toLocaleString()}` : '—'} color={T.accent.gold} />
          <MetaChip label="VOL" value={market?.trade_frequency ? `${market.trade_frequency.toFixed(1)}/s` : '—'} color={T.text.mid} />
        </div>
        <div style={S.legendBlock}>
          <LegendDot color="#26a69a" label="Bull" />
          <LegendDot color="#ef5350" label="Bear" />
          <LegendDot color="#f0b90b" label="VWAP" />
          <LegendDot color="#00e5c8" label="Events" />
        </div>
      </div>

      {/* SPE state badge overlay */}
      {spe && (
        <div style={S.stateBadge}>
          <span style={{
            ...S.stateLabel,
            color: spe.current_state === 'IDLE' ? T.text.muted :
                   spe.current_state === 'CASCADE' ? T.status.danger : T.status.warning,
          }}>
            {spe.current_state}
          </span>
          {spe.emitted_events > 0 && (
            <span style={S.candidateChip}>● {spe.emitted_events} CANDIDATE{spe.emitted_events > 1 ? 'S' : ''}</span>
          )}
        </div>
      )}

      {/* Chart */}
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Bottom info */}
      <div style={S.bottomBar}>
        <span style={S.bottomText}>1m CANDLES · SCROLL TO ZOOM · {markersRef.current.length} MARKERS</span>
        {hoveredPrice && <span style={S.bottomText}>${hoveredPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>}
      </div>
    </div>
  );
}

const MetaChip: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
    <span style={{ fontSize: 7, color: T.text.muted, letterSpacing: 1 }}>{label}</span>
    <span style={{ fontSize: 9, color, fontWeight: 600 }}>{value}</span>
  </span>
);

const LegendDot: React.FC<{ color: string; label: string }> = ({ color, label }) => (
  <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 7, color: T.text.muted }}>
    <span style={{ width: 5, height: 5, borderRadius: '50%', background: color, display: 'inline-block' }} />
    {label}
  </span>
);

const S: Record<string, React.CSSProperties> = {
  wrapper: { width: '100%', height: '100%', position: 'relative', display: 'flex', flexDirection: 'column' },
  topBar: {
    position: 'absolute', top: 0, left: 0, right: 0, zIndex: 10,
    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
    padding: '6px 10px', pointerEvents: 'none',
    background: 'linear-gradient(180deg, rgba(5,7,11,0.85) 0%, transparent 100%)',
  },
  priceBlock: { display: 'flex', alignItems: 'baseline', gap: 8 },
  symbol: { fontSize: 9, color: T.text.muted, letterSpacing: 2, fontWeight: 700 },
  price: { fontSize: 16, fontWeight: 700, color: T.text.bright, textShadow: `0 0 12px ${T.green.glow}` },
  change: { fontSize: 10, fontWeight: 600 },
  metaBlock: { display: 'flex', gap: 10, alignItems: 'center' },
  legendBlock: { display: 'flex', gap: 8, alignItems: 'center' },
  stateBadge: {
    position: 'absolute', top: 36, right: 10, zIndex: 10,
    display: 'flex', alignItems: 'center', gap: 6, pointerEvents: 'none',
  },
  stateLabel: { fontSize: 10, fontWeight: 700, letterSpacing: 1 },
  candidateChip: {
    fontSize: 8, fontWeight: 700, color: T.green.primary,
    padding: '2px 6px', borderRadius: 3,
    background: T.green.glow, border: `1px solid ${T.green.primary}30`,
    textShadow: `0 0 6px ${T.green.glow}`,
  },
  bottomBar: {
    position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 10,
    display: 'flex', justifyContent: 'space-between', padding: '4px 10px',
    pointerEvents: 'none',
    background: 'linear-gradient(0deg, rgba(5,7,11,0.7) 0%, transparent 100%)',
  },
  bottomText: { fontSize: 7, color: T.text.faint, letterSpacing: 1 },
};
