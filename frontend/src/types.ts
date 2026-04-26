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
  events: MarketEvent[];
  event_stats: EventStats;
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

// ============================================================
// Event Engine Types
// ============================================================

export interface ForwardOutcome {
  price_at_10s: number;
  price_at_30s: number;
  price_at_60s: number;
  price_at_120s: number;
  price_at_300s: number;
  max_favorable_excursion: number;
  max_adverse_excursion: number;
  pnl_at_10s_bps: number;
  pnl_at_30s_bps: number;
  pnl_at_60s_bps: number;
  pnl_at_120s_bps: number;
  pnl_at_300s_bps: number;
  fees_assumed_bps: number;
  net_pnl_at_60s_bps: number;
  measured: boolean;
}

export interface AbsorptionEvent {
  event_type: 'absorption';
  event_id: string;
  side: 'buy_absorption' | 'sell_absorption';
  timestamp: number;
  symbol: string;
  price_level: number;
  window_seconds: number;
  aggressive_volume: number;
  signed_delta: number;
  price_change_after_aggression: number;
  max_adverse_excursion: number;
  max_favorable_excursion: number;
  absorption_strength_score: number;
  local_volume_percentile: number;
  delta_percentile: number;
  book_liquidity_context: number;
  vwap_distance: number;
  spread_context: number;
  regime_context: string;
  forward: ForwardOutcome;
}

export interface ExhaustionEvent {
  event_type: 'exhaustion';
  event_id: string;
  side: 'buy_exhaustion' | 'sell_exhaustion';
  timestamp: number;
  price: number;
  aggressive_volume: number;
  delta: number;
  bubble_count: number;
  price_impact_per_volume: number;
  continuation_failure_score: number;
  local_extreme_context: string;
  cvd_divergence_context: number;
  exhaustion_strength_score: number;
  forward: ForwardOutcome;
}

export interface LiquiditySweepEvent {
  event_type: 'liquidity_sweep';
  event_id: string;
  side: 'high_sweep' | 'low_sweep';
  timestamp: number;
  swept_level: number;
  sweep_distance: number;
  sweep_volume: number;
  sweep_delta: number;
  reclaim_status: boolean;
  reversal_confirmation: boolean;
  time_to_reclaim: number;
  sweep_strength_score: number;
  forward: ForwardOutcome;
}

export interface DeltaDivergenceEvent {
  event_type: 'delta_divergence';
  event_id: string;
  side: 'bearish_divergence' | 'bullish_divergence';
  timestamp: number;
  price_structure: string;
  cvd_structure: string;
  divergence_window: number;
  divergence_strength_score: number;
  local_trend_context: string;
  price_at_detection: number;
  cvd_at_detection: number;
  forward: ForwardOutcome;
}

export interface ImbalanceEvent {
  event_type: 'imbalance';
  event_id: string;
  side: 'buy_imbalance' | 'sell_imbalance';
  timestamp: number;
  volume_buy: number;
  volume_sell: number;
  delta: number;
  imbalance_ratio: number;
  price_response: number;
  continuation_score: number;
  failure_score: number;
  classification: 'continuation' | 'absorption' | 'exhaustion';
  forward: ForwardOutcome;
}

export type MarketEvent =
  | AbsorptionEvent
  | ExhaustionEvent
  | LiquiditySweepEvent
  | DeltaDivergenceEvent
  | ImbalanceEvent;

export interface EventStats {
  total: number;
  by_type: Record<string, number>;
  by_side: Record<string, number>;
  avg_strength: number;
  measured_count: number;
  unmeasured_count: number;
}

export interface EventEngineState {
  events: MarketEvent[];
  eventStats: EventStats;
  recentEvents: MarketEvent[];  // last 20 for display
  filter: EventFilter | null;
}

export interface EventFilter {
  event_type?: string;
  side?: string;
  min_strength?: number;
}
