// MANTIS Dashboard — WebSocket connection with auto-reconnect
import { useEffect, useRef, useCallback } from 'react';
import { useStore } from '../store';
import type { LargeTrade, MarketEvent, SPEEvent } from '../types';

const RECONNECT_DELAY = 1000;
const PING_INTERVAL = 15000;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const pingInterval = useRef<ReturnType<typeof setInterval>>();

  const {
    setConnected, setLivePrice, setFlow, setHeatmap, setFootprints,
    setAbsorption, setCandles, addLargeTrade, addTradeTape, setInitData, updateMicro,
    addEvents, setEventStats,
    addSPEEvents, setSPEStats,
  } = useStore();

  const connect = useCallback(() => {
    const wsUrl = `ws://${window.location.hostname}:8000/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      pingInterval.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, PING_INTERVAL);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case 'init':
            setInitData(msg.data);
            break;
          case 'flow_metrics': {
            setFlow(msg.data);
            const s = useStore.getState();
            updateMicro(msg.data, s.absorption, s.heatmap);
            break;
          }
          case 'heatmap': {
            setHeatmap(msg.data);
            const s = useStore.getState();
            updateMicro(s.flow, s.absorption, msg.data);
            break;
          }
          case 'footprints':
            setFootprints(msg.data);
            break;
          case 'absorption': {
            setAbsorption(msg.data);
            const s = useStore.getState();
            updateMicro(s.flow, msg.data, s.heatmap);
            break;
          }
          case 'large_trade': {
            const trade = msg.data as LargeTrade;
            addLargeTrade(trade);
            addTradeTape(trade);
            break;
          }
          case 'event_detected': {
            const evts = Array.isArray(msg.data) ? msg.data : [msg.data];
            addEvents(evts as MarketEvent[]);
            break;
          }
          case 'event_stats': {
            setEventStats(msg.data);
            break;
          }
          case 'spe_detected': {
            const evts = Array.isArray(msg.data) ? msg.data : [msg.data];
            addSPEEvents(evts as SPEEvent[]);
            break;
          }
          case 'spe_stats': {
            setSPEStats(msg.data);
            break;
          }
          case 'latest_price': {
            const d = msg.data;
            setLivePrice({
              price: d.price,
              timestamp: d.timestamp,
              side: d.side,
              qty: d.qty,
              lastUpdate: Date.now(),
            });
            break;
          }
          case 'pong':
            break;
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setConnected(false);
      clearInterval(pingInterval.current);
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    };

    ws.onerror = () => ws.close();
  }, [setConnected, setLivePrice, setFlow, setHeatmap, setFootprints, setAbsorption, setCandles, addLargeTrade, addTradeTape, setInitData, updateMicro, addEvents, setEventStats, addSPEEvents, setSPEStats]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      clearInterval(pingInterval.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return wsRef;
}
