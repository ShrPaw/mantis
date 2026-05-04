"""
MANTIS SPE — Event Engine Integration

Shows how to wire SPE into the existing MANTIS EventManager.
This is a patch file — apply these changes to the existing codebase.
"""

# ============================================================
# STEP 1: Add to event_engine/__init__.py
# ============================================================
# Add these imports:
#
#   from .spe import SPEOrchestrator, SPEConfig
#
# Add to __all__:
#   "SPEOrchestrator", "SPEConfig",

# ============================================================
# STEP 2: Add to event_engine/manager.py
# ============================================================
# In EventManager.__init__():
#
#   # SPE Module (feature-flagged)
#   self.spe_enabled = os.environ.get("SPE_ENABLED", "true").lower() in ("true", "1", "yes")
#   self.spe = None
#   if self.spe_enabled:
#       try:
#           from .spe import SPEOrchestrator
#           self.spe = SPEOrchestrator(self.ctx)
#           logger.info("SPE Module: ENABLED")
#       except Exception as e:
#           logger.warning(f"SPE Module: FAILED TO LOAD — {e}")
#
# In EventManager.on_trade():
#
#   # After existing detector loop, add SPE hook:
#   if self.spe is not None:
#       try:
#           spe_events = self.spe.on_trade(price, qty, delta, timestamp)
#           for evt_dict in spe_events:
#               # SPE events are already dicts, wrap as MicrostructureEvent-compatible
#               new_events.append(evt_dict)
#       except Exception as e:
#           logger.debug(f"SPE error (non-fatal): {e}")
#
# In EventManager.get_event_stats():
#
#   # Add SPE stats:
#   if self.spe is not None:
#       result["spe"] = self.spe.get_stats()

# ============================================================
# STEP 3: Add to backend/main.py
# ============================================================
# In on_trade() handler, after event_mgr hook:
#
#   # SPE hook is handled inside EventManager.on_trade()
#   # No additional code needed in main.py
#
# In metrics_broadcaster(), add SPE stats:
#
#   if event_mgr is not None and event_mgr.spe is not None:
#       try:
#           await broadcast({
#               "type": "spe_stats",
#               "data": event_mgr.spe.get_stats(),
#           })
#       except Exception:
#           pass

# ============================================================
# STEP 4: Add SPE types to frontend/src/types.ts
# ============================================================
SPE_TYPES_TS = """
// SPE — Structural Pressure Execution
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
}

export interface SPEStats {
  enabled: boolean;
  signals_evaluated: number;
  events_emitted: number;
  layer_failures: Record<string, number>;
  state: string;
}
"""

# ============================================================
# STEP 5: Add to frontend/src/store.ts
# ============================================================
SPE_STORE_TS = """
// Add to DashboardState interface:
  speEvents: SPEEvent[];
  speStats: SPEStats;

// Add to default state:
  speEvents: [],
  speStats: { enabled: false, signals_evaluated: 0, events_emitted: 0, layer_failures: {}, state: 'IDLE' },

// Add to setInitData:
  speEvents: d.spe_events || [],
  speStats: d.spe_stats || defaultSpeStats,

// Add actions:
  addSPEEvents: (evts) => set(s => ({
    speEvents: [...evts, ...s.speEvents].slice(0, 100),
  })),
  setSPEStats: (stats) => set({ speStats: stats }),
"""

# ============================================================
# STEP 6: Environment variable
# ============================================================
# Set SPE_ENABLED=true (default) or SPE_ENABLED=false to disable
# No code changes needed for the feature flag — it reads from env.

print("SPE Integration instructions loaded.")
print("Apply the patches above to the existing MANTIS codebase.")
print("SPE is feature-flagged via SPE_ENABLED env var (default: true).")
