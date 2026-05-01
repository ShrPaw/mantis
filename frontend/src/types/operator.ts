// MANTIS Operator Dashboard — Type Definitions
// Extended types for the operator monitoring view

export interface OperatorBackend {
  status: string;
  source: string;
  uptime: number;
  trade_count: number;
  candles_loaded: number;
  clients: number;
}

export interface OperatorMarket {
  last_price: number;
  vwap: number;
  session_high: number;
  session_low: number;
  delta: number;
  cum_delta: number;
  taker_buy_vol: number;
  taker_sell_vol: number;
  trade_frequency: number;
  imbalance: number;
}

export interface OperatorEventEngine {
  enabled: boolean;
  status: string;
  total?: number;
  fired?: number;
  deduped?: number;
  pending_outcomes?: number;
  watchlisted?: number;
  blacklisted?: number;
}

export interface OperatorSPE {
  enabled: boolean;
  observation_only: boolean;
  current_state: string;
  raw_evaluations: number;
  full_8_layer_passes: number;
  emitted_events: number;
  accounting_valid: boolean;
  accounting_errors: string[];
  layer_counts: Record<string, { pass: number; fail: number; not_evaluated: number }>;
}

export interface ObsFileStatus {
  exists: boolean;
  size?: number;
  modified?: number;
}

export interface OperatorObservationLogger {
  detected: boolean;
  health_file: ObsFileStatus | null;
  metrics_file: ObsFileStatus | null;
  events_file: ObsFileStatus | null;
  summary_file: ObsFileStatus | null;
  last_health_ts: number | null;
  last_metrics_ts: number | null;
  last_event_ts: number | null;
  unique_events: number;
  accounting_violations: number;
  observation_only_violations: number;
}

export interface OperatorStatus {
  timestamp: number;
  backend: OperatorBackend;
  market: OperatorMarket;
  event_engine: OperatorEventEngine;
  spe: OperatorSPE;
  observation_logger: OperatorObservationLogger;
}

// SPE history tracking for charts
export interface SPEMetricSnapshot {
  ts: number;
  raw_evaluations: number;
  emitted_events: number;
  full_8_layer_passes: number;
  current_state: string;
  layer_counts: Record<string, { pass: number; fail: number; not_evaluated: number }>;
}

// Layer definition
export interface LayerDef {
  key: string;
  name: string;
  shortName: string;
}
