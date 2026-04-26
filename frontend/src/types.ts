// MANTIS Dashboard — Type Definitions

export interface FlowMetrics {
  taker_buy_vol: number;
  taker_sell_vol: number;
  delta: number;
  cum_delta: number;
  trade_count: number;
  trade_frequency: number;
  imbalance: number;
  vwap: number;
  last_price: number;
  session_high: number;
  session_low: number;
}

export interface HeatmapLevel {
  price: number;
  qty: number;
}

export interface HeatmapData {
  bids: HeatmapLevel[];
  asks: HeatmapLevel[];
  mid: number;
}

export interface FootprintLevel {
  price: number;
  bid_vol: number;
  ask_vol: number;
  delta: number;
  imbalance: number;
  trades: number;
}

export interface FootprintCandle {
  open_time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  total_vol: number;
  total_delta: number;
  levels: FootprintLevel[];
}

export interface LargeTrade {
  price: number;
  qty: number;
  side: 'buy' | 'sell';
  timestamp: number;
  value_usd: number;
}

export interface AbsorptionZone {
  price: number;
  volume: number;
  delta: number;
  candle_time: number;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface InitData {
  flow: FlowMetrics;
  heatmap: HeatmapData;
  footprints: FootprintCandle[];
  large_trades: LargeTrade[];
  absorption: AbsorptionZone[];
  candles: Candle[];
}

export interface SessionLevel {
  name: string;
  high: number;
  low: number;
  color: string;
}

export interface NewsEvent {
  title: string;
  time: number;
  impact: 'high' | 'medium';
  countdown?: string;
}

export interface DeltaImbalance {
  status: 'strong_buy' | 'strong_sell' | 'neutral';
  strength: number; // 0-1
  description: string;
}

export interface AbsorptionProxy {
  detected: boolean;
  price: number;
  volume: number;
  delta: number;
}

export interface LiquidityPull {
  detected: boolean;
  side: 'bid' | 'ask';
  price: number;
  removed_qty: number;
  timestamp: number;
}

export interface BreakoutStrength {
  detected: boolean;
  direction: 'up' | 'down' | null;
  volume_confirmed: boolean;
  price: number;
  delta: number;
}

export interface MicrostructureState {
  deltaImbalance: DeltaImbalance;
  absorptionProxy: AbsorptionProxy[];
  liquidityPulls: LiquidityPull[];
  breakoutStrength: BreakoutStrength;
}
