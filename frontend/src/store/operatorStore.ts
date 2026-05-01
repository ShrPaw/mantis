// MANTIS Operator Dashboard — Zustand Store
import { create } from 'zustand';
import type { OperatorStatus, SPEMetricSnapshot } from '../types/operator';

interface OperatorState {
  connected: boolean;
  error: string | null;
  status: OperatorStatus | null;
  metricHistory: SPEMetricSnapshot[];
  // actions
  setConnected: (v: boolean) => void;
  setError: (e: string | null) => void;
  setOperatorStatus: (s: OperatorStatus) => void;
  addMetricSnapshot: (s: SPEMetricSnapshot) => void;
}

export const useOperatorStore = create<OperatorState>((set, get) => ({
  connected: false,
  error: null,
  status: null,
  metricHistory: [],

  setConnected: (v) => set({ connected: v }),
  setError: (e) => set({ error: e }),
  setOperatorStatus: (s) => set({ status: s }),
  addMetricSnapshot: (snap) => set(state => ({
    metricHistory: [...state.metricHistory, snap].slice(-200),
  })),
}));
