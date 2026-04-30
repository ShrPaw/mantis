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

export interface ScoreBreakdown {
  strength_components: Record<string, number>;
  confidence_components: Record<string, number>;
  noise_components: Record<string, number>;
  regime_score: number;
  strength_score: number;
  confidence_score: number;
  noise_score: number;
  composite_score: number;
}

export interface ForwardOutcome {
  future_return_10s: number | null;
  future_return_30s: number | null;
  future_return_60s: number | null;
  future_return_120s: number | null;
  future_return_300s: number | null;
  max_favorable_excursion_30s: number | null;
  max_adverse_excursion_30s: number | null;
  max_favorable_excursion_120s: number | null;
  max_adverse_excursion_120s: number | null;
  hit_tp_0_10pct: boolean | null;
  hit_tp_0_20pct: boolean | null;
  hit_sl_0_10pct: boolean | null;
  hit_sl_0_20pct: boolean | null;
  time_to_max_favorable: number | null;
  time_to_max_adverse: number | null;
  is_complete: boolean;
}

export interface BaseEvent {
  event_id: string;
  timestamp: number;
  symbol: string;
  exchange: string;
  event_type: string;
  side: string;
  price: number;
  scores: ScoreBreakdown;
  raw_metrics: Record<string, number>;
  context_metrics: Record<string, any>;
  forward: ForwardOutcome;
  validation_tags: string[];
  explanation: string;
  is_active: boolean;
  merged_into: string | null;
}

export interface AbsorptionEvent extends BaseEvent {
  event_type: 'absorption';
  window_seconds: number;
  aggressive_volume: number;
  signed_delta: number;
  price_change_after_aggression: number;
  local_volume_percentile: number;
  delta_percentile: number;
  book_liquidity_context: number;
  vwap_distance: number;
  spread_context: number;
  regime_context: string;
  repeated_tests: number;
}

export interface ExhaustionEvent extends BaseEvent {
  event_type: 'exhaustion';
  aggressive_volume: number;
  delta: number;
  bubble_count: number;
  price_impact_per_volume: number;
  continuation_failure_score: number;
  local_extreme_context: string;
  cvd_divergence_context: number;
}

export interface LiquiditySweepEvent extends BaseEvent {
  event_type: 'liquidity_sweep';
  swept_level: number;
  sweep_distance: number;
  sweep_volume: number;
  sweep_delta: number;
  reclaim_status: boolean;
  reversal_confirmation: boolean;
  time_to_reclaim: number;
  prior_touches: number;
}

export interface DeltaDivergenceEvent extends BaseEvent {
  event_type: 'delta_divergence';
  price_structure: string;
  cvd_structure: string;
  divergence_window: number;
  price_at_detection: number;
  cvd_at_detection: number;
  local_trend_context: string;
}

export interface ImbalanceEvent extends BaseEvent {
  event_type: 'imbalance';
  volume_buy: number;
  volume_sell: number;
  delta: number;
  imbalance_ratio: number;
  price_response: number;
  continuation_score: number;
  failure_score: number;
  classification: string;
}

export interface LargeTradeClusterEvent extends BaseEvent {
  event_type: 'large_trade_cluster';
  total_cluster_volume: number;
  number_of_large_trades: number;
  average_trade_size: number;
  max_trade_size: number;
  local_percentile_rank: number;
  price_response_after_cluster: number;
  continuation_or_failure_label: string;
}

export interface RangeBreakEvent extends BaseEvent {
  event_type: 'range_break';
  range_high: number;
  range_low: number;
  break_distance: number;
  break_volume: number;
  break_delta: number;
  continuation_after_break: number;
  failed_break_status: boolean;
  reclaim_time: number;
  range_context_score: number;
}

export interface VWAPReactionEvent extends BaseEvent {
  event_type: 'vwap_reaction';
  vwap: number;
  distance_to_vwap: number;
  reaction_type: string;
  delta_context: number;
  volume_context: number;
  follow_through: number;
}

export type MarketEvent =
  | AbsorptionEvent
  | ExhaustionEvent
  | LiquiditySweepEvent
  | DeltaDivergenceEvent
  | ImbalanceEvent
  | LargeTradeClusterEvent
  | RangeBreakEvent
  | VWAPReactionEvent;

export interface EventStats {
  total: number;
  by_type: Record<string, number>;
  by_side: Record<string, number>;
  avg_strength: number;
  avg_confidence: number;
  measured_count: number;
  unmeasured_count: number;
  fired: number;
  deduped: number;
  pending_outcomes: number;
}

export interface EventFilter {
  event_type?: string;
  side?: string;
  min_strength?: number;
}

// ============================================================
// SPE — Structural Pressure Execution (Observation-Only)
// ============================================================

export interface SPEEvent {
  event_id: string;
  timestamp: number;
  symbol: string;
  exchange: string;
  event_type: 'structural_pressure_execution';
  direction: 'LONG' | 'SHORT';
  mantis_state: 'CASCADE' | 'UNWIND';
  imbalance_score: number;
  execution_quality: number;
  risk_score: number;
  crowd_direction: 'LONG_CROWD' | 'SHORT_CROWD';
  displacement_strength: number;
  trap_detected: boolean;
  entry_price: number;
  stop_loss: number;
  tp_levels: number[];
  confidence_score: number;
  pressure_strength: number;
  funding_z: number;
  sweep_detected: boolean;
  sweep_direction: string;
  spread_bps: number;
  displacement_origin: number;
  displacement_end: number;
  displacement_body_bps: number;
  validation_tags: string[];
  explanation: string;
  observation_only: boolean;
}

export interface SPELayerStat {
  pass: number;
  fail: number;
  not_evaluated: number;
}

export interface SPELayerStats {
  layer_pass_fail: Record<string, SPELayerStat>;
  raw_evaluations: number;
  full_8_layer_passes: number;
  emitted_events: number;
  suppressed_duplicates: number;
  cooldown_hits: number;
  current_state: string;
  observation_only: boolean;
}

export interface SPEStats {
  enabled: boolean;
  signals_evaluated: number;
  events_emitted: number;
  layer_stats: Record<string, SPELayerStat>;
  state: string;
  observation_only: boolean;
}
