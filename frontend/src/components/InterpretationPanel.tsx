// MANTIS Operator Dashboard — Current Interpretation
// Natural language summary: what is happening right now
import React from 'react';
import { useOperatorStore } from '../store/operatorStore';
import { T } from '../styles/operatorTheme';

function buildInterpretation(
  market: any,
  spe: any,
  backend: any,
  connected: boolean,
): string {
  if (!connected || !backend) {
    return 'System is offline. No data feed available. Check backend status.';
  }

  const lc = spe?.layer_counts ?? {};
  const raw = spe?.raw_evaluations ?? 0;
  const full8 = spe?.full_8_layer_passes ?? 0;
  const emitted = spe?.emitted_events ?? 0;
  const currentState = spe?.current_state ?? 'IDLE';
  const freq = market?.trade_frequency ?? 0;
  const price = market?.last_price;
  const priceStr = price ? `$${price.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—';

  // Determine volume descriptor
  let volumeDesc = 'NORMAL_VOLUME';
  if (freq > 5) volumeDesc = 'HIGH_VOLUME';
  else if (freq < 1) volumeDesc = 'LOW_VOLUME';

  // Find blocking layer
  let blockLayer = 'L1';
  let blockReason = 'no CASCADE/UNWIND context';
  const layerOrder = [
    { key: 'L1_context_gate', name: 'L1', reason: 'no CASCADE/UNWIND context' },
    { key: 'L2_pressure', name: 'L2', reason: 'no positioning pressure' },
    { key: 'L3_displacement', name: 'L3', reason: 'no displacement' },
    { key: 'L4_sweep', name: 'L4', reason: 'no sweep' },
    { key: 'L5_trap', name: 'L5', reason: 'no trap/rejection' },
    { key: 'L6_execution_filter', name: 'L6', reason: 'execution quality not acceptable' },
    { key: 'L7_entry_zone', name: 'L7', reason: 'no valid entry zone' },
    { key: 'L8_exit_model', name: 'L8', reason: 'exit/RR model rejected' },
    { key: 'confidence_gate', name: 'Confidence', reason: 'below confidence threshold' },
  ];

  if (raw > 0) {
    for (const layer of layerOrder) {
      const c = lc[layer.key];
      if (c && c.fail > 0 && c.pass === 0) {
        blockLayer = layer.name;
        blockReason = layer.reason;
        break;
      }
    }
  }

  // Build sentence
  const parts: string[] = [];

  // Price + state
  parts.push(`BTC is at ${priceStr}`);

  // Volume + state
  if (currentState === 'CASCADE' || currentState === 'UNWIND') {
    parts.push(`in ${currentState} with ${volumeDesc}`);
  } else {
    parts.push(`currently ${volumeDesc} and IDLE`);
  }

  // SPE status
  if (raw === 0) {
    parts.push('SPE has not evaluated any signals yet — system silent by design');
  } else if (full8 > 0) {
    parts.push(`SPE passed all 8 layers — ${emitted} SHORT_STRESS candidate(s) emitted`);
  } else {
    parts.push(`SPE is blocked at ${blockLayer} because ${blockReason}`);
  }

  // SHORT_STRESS status
  if (full8 > 0 && (currentState === 'CASCADE' || currentState === 'UNWIND')) {
    parts.push('SHORT_STRESS is active — review candidate manually');
  } else {
    parts.push('SHORT_STRESS is inactive');
  }

  // Final state
  if (currentState === 'IDLE' && raw === 0) {
    parts.push('This is a no-context observation state');
  } else if (currentState === 'IDLE') {
    parts.push('This is an observation-only state');
  }

  return parts.join('. ') + '.';
}

export const InterpretationPanel: React.FC = () => {
  const connected = useOperatorStore(s => s.connected);
  const status = useOperatorStore(s => s.status);
  const market = status?.market;
  const spe = status?.spe;
  const backend = status?.backend;

  const interpretation = buildInterpretation(market, spe, backend, connected);

  return (
    <div style={S.panel}>
      <div style={S.title}>CURRENT INTERPRETATION</div>
      <div style={S.text}>{interpretation}</div>
    </div>
  );
};

const S: Record<string, React.CSSProperties> = {
  panel: {
    background: `linear-gradient(135deg, rgba(0,229,200,0.04) 0%, ${T.bg.panel} 40%, ${T.bg.surface} 100%)`,
    border: `1px solid ${T.border.mid}`,
    borderRadius: 6,
    padding: '8px 12px',
    flexShrink: 0,
    boxShadow: `inset 0 1px 0 rgba(57,255,136,0.03)`,
  },
  title: {
    fontSize: 8,
    fontWeight: 700,
    color: T.accent.cyan,
    letterSpacing: 2,
    marginBottom: 4,
    textShadow: `0 0 8px rgba(0,229,200,0.2)`,
  },
  text: {
    fontSize: 10,
    color: T.text.mid,
    lineHeight: 1.5,
    letterSpacing: 0.2,
  },
};
