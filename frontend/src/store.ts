// MANTIS Dashboard — Global State (Zustand)
import { create } from 'zustand';
import type {
  FlowMetrics, HeatmapData, FootprintCandle, LargeTrade,
  AbsorptionZone, Candle, MicrostructureState,
  MarketEvent, EventStats, EventFilter,
  SPEEvent, SPEStats,
} from './types';

export interface LivePrice {
  price: number;
  timestamp: number;
  side: string;
  qty: number;
  lastUpdate: number; // browser timestamp of last update
}

interface DashboardState {
  // Connection
  connected: boolean;
  setConnected: (v: boolean) => void;

  // Live price (ultra-fast, every trade)
  livePrice: LivePrice;
  setLivePrice: (p: LivePrice) => void;

  // Core data
  flow: FlowMetrics;
  heatmap: HeatmapData;
  footprints: FootprintCandle[];
  largeTrades: LargeTrade[];
  absorption: AbsorptionZone[];
  candles: Candle[];

  // Live trade tape
  tradeTape: LargeTrade[];

  // Microstructure analysis
  micro: MicrostructureState;

  // Event Engine
  events: MarketEvent[];
  eventStats: EventStats;
  eventFilter: EventFilter | null;

  // SPE Module (observation-only)
  speEvents: SPEEvent[];
  speStats: SPEStats;

  // Actions
  setFlow: (f: FlowMetrics) => void;
  setHeatmap: (h: HeatmapData) => void;
  setFootprints: (f: FootprintCandle[]) => void;
  setAbsorption: (a: AbsorptionZone[]) => void;
  setCandles: (c: Candle[]) => void;
  addLargeTrade: (t: LargeTrade) => void;
  addTradeTape: (t: LargeTrade) => void;
  setInitData: (d: any) => void;
  updateMicro: (flow: FlowMetrics, absorption: AbsorptionZone[], heatmap: HeatmapData) => void;

  // Event actions
  addEvents: (evts: MarketEvent[]) => void;
  setEventStats: (s: EventStats) => void;
  setEventFilter: (f: EventFilter | null) => void;

  // SPE actions
  addSPEEvents: (evts: SPEEvent[]) => void;
  setSPEStats: (s: SPEStats) => void;
}

const defaultFlow: FlowMetrics = {
  taker_buy_vol: 0, taker_sell_vol: 0, delta: 0, cum_delta: 0,
  trade_count: 0, trade_frequency: 0, imbalance: 0, vwap: 0,
  last_price: 0, session_high: 0, session_low: Infinity,
};

const defaultMicro: MicrostructureState = {
  deltaImbalance: { status: 'neutral', strength: 0, description: 'Insufficient data' },
  absorptionProxy: [],
  liquidityPulls: [],
  breakoutStrength: { detected: false, direction: null, volume_confirmed: false, price: 0, delta: 0 },
};

const defaultEventStats: EventStats = {
  total: 0, by_type: {}, by_side: {},
  avg_strength: 0, avg_confidence: 0,
  measured_count: 0, unmeasured_count: 0,
  fired: 0, deduped: 0, pending_outcomes: 0,
};

const defaultSPEStats: SPEStats = {
  enabled: false,
  signals_evaluated: 0,
  events_emitted: 0,
  layer_stats: {},
  state: 'IDLE',
  observation_only: true,
};

// Track previous heatmap for liquidity pull detection
let prevBidsMap = new Map<number, number>();
let prevAsksMap = new Map<number, number>();

function computeMicro(
  flow: FlowMetrics,
  absorption: AbsorptionZone[],
  heatmap: HeatmapData,
): MicrostructureState {
  // 1. Delta Imbalance Detection
  const totalVol = flow.taker_buy_vol + flow.taker_sell_vol;
  let deltaImbalance: { status: 'strong_buy' | 'strong_sell' | 'neutral'; strength: number; description: string } = { status: 'neutral', strength: 0, description: 'Balanced flow' };

  if (totalVol > 0.5) {
    const ratio = flow.delta / totalVol;
    const absRatio = Math.abs(ratio);
    if (absRatio > 0.3) {
      deltaImbalance = {
        status: ratio > 0 ? 'strong_buy' : 'strong_sell',
        strength: Math.min(absRatio / 0.5, 1),
        description: ratio > 0
          ? `Strong buying pressure (${(absRatio * 100).toFixed(0)}% dominance)`
          : `Strong selling pressure (${(absRatio * 100).toFixed(0)}% dominance)`,
      };
    }
  }

  // 2. Absorption Proxy (from backend data)
  const absorptionProxy = absorption.slice(0, 5).map(a => ({
    detected: true,
    price: a.price,
    volume: a.volume,
    delta: a.delta,
  }));

  // 3. Liquidity Pull Detection
  const liquidityPulls: MicrostructureState['liquidityPulls'] = [];
  const currentBidsMap = new Map(heatmap.bids.map(b => [b.price, b.qty]));
  const currentAsksMap = new Map(heatmap.asks.map(a => [a.price, a.qty]));

  // Check for disappeared bids (large walls that vanished)
  prevBidsMap.forEach((qty, price) => {
    if (qty > 0.5 && !currentBidsMap.has(price)) {
      liquidityPulls.push({
        detected: true, side: 'bid', price,
        removed_qty: qty, timestamp: Date.now() / 1000,
      });
    }
  });

  // Check for disappeared asks
  prevAsksMap.forEach((qty, price) => {
    if (qty > 0.5 && !currentAsksMap.has(price)) {
      liquidityPulls.push({
        detected: true, side: 'ask', price,
        removed_qty: qty, timestamp: Date.now() / 1000,
      });
    }
  });

  prevBidsMap = currentBidsMap;
  prevAsksMap = currentAsksMap;

  // 4. Breakout Strength
  let breakoutStrength: MicrostructureState['breakoutStrength'] = {
    detected: false, direction: null, volume_confirmed: false, price: 0, delta: 0,
  };

  if (flow.last_price > 0 && flow.session_high > 0 && flow.session_low < Infinity) {
    const range = flow.session_high - flow.session_low;
    if (range > 0) {
      const pricePos = (flow.last_price - flow.session_low) / range;
      const highVol = flow.trade_frequency > 2;

      // Near session high breakout
      if (pricePos > 0.95 && flow.delta > 0 && highVol) {
        breakoutStrength = {
          detected: true, direction: 'up', volume_confirmed: true,
          price: flow.last_price, delta: flow.delta,
        };
      }
      // Near session low breakout
      else if (pricePos < 0.05 && flow.delta < 0 && highVol) {
        breakoutStrength = {
          detected: true, direction: 'down', volume_confirmed: true,
          price: flow.last_price, delta: flow.delta,
        };
      }
      // Breakout without volume confirmation
      else if (pricePos > 0.95 && flow.delta <= 0) {
        breakoutStrength = {
          detected: true, direction: 'up', volume_confirmed: false,
          price: flow.last_price, delta: flow.delta,
        };
      } else if (pricePos < 0.05 && flow.delta >= 0) {
        breakoutStrength = {
          detected: true, direction: 'down', volume_confirmed: false,
          price: flow.last_price, delta: flow.delta,
        };
      }
    }
  }

  return { deltaImbalance, absorptionProxy, liquidityPulls, breakoutStrength };
}

export const useStore = create<DashboardState>((set, get) => ({
  connected: false,
  setConnected: (v) => set({ connected: v }),

  livePrice: { price: 0, timestamp: 0, side: '', qty: 0, lastUpdate: 0 },
  setLivePrice: (p) => set({ livePrice: p }),

  flow: defaultFlow,
  heatmap: { bids: [], asks: [], mid: 0 },
  footprints: [],
  largeTrades: [],
  absorption: [],
  candles: [],
  tradeTape: [],
  micro: defaultMicro,

  // Event Engine state
  events: [],
  eventStats: defaultEventStats,
  eventFilter: null,

  // SPE state
  speEvents: [],
  speStats: defaultSPEStats,

  setFlow: (f) => set({ flow: f }),
  setHeatmap: (h) => set({ heatmap: h }),
  setFootprints: (f) => set({ footprints: f }),
  setAbsorption: (a) => set({ absorption: a }),
  setCandles: (c) => set({ candles: c }),

  addLargeTrade: (t) => set(s => ({
    largeTrades: [t, ...s.largeTrades].slice(0, 200),
  })),

  addTradeTape: (t) => set(s => ({
    tradeTape: [t, ...s.tradeTape].slice(0, 80),
  })),

  setInitData: (d) => {
    set({
      flow: d.flow || defaultFlow,
      heatmap: d.heatmap || { bids: [], asks: [], mid: 0 },
      footprints: d.footprints || [],
      largeTrades: d.large_trades || [],
      absorption: d.absorption || [],
      candles: d.candles || [],
      events: d.events || [],
      eventStats: d.event_stats || defaultEventStats,
      speEvents: d.spe_events || [],
      speStats: d.spe_stats || defaultSPEStats,
    });
  },

  updateMicro: (flow, absorption, heatmap) => {
    set({ micro: computeMicro(flow, absorption, heatmap) });
  },

  // Event actions
  addEvents: (evts) => set(s => ({
    events: [...evts, ...s.events].slice(0, 500),
  })),
  setEventStats: (stats) => set({ eventStats: stats }),
  setEventFilter: (filter) => set({ eventFilter: filter }),

  // SPE actions
  addSPEEvents: (evts) => set(s => ({
    speEvents: [...evts, ...s.speEvents].slice(0, 200),
  })),
  setSPEStats: (stats) => set({ speStats: stats }),
}));
