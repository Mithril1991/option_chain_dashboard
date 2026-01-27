import { create } from 'zustand'
import type {
  HealthResponse,
  ScanResponse,
  AlertResponse,
  ChainSnapshot,
  FeatureResponse
} from '@types/api'
import type { AlertWithScore } from '@types/alert'

/**
 * State for API data management
 * Handles caching and state for all API responses
 */
interface ApiState {
  // Data
  health: HealthResponse | null
  latestAlerts: AlertResponse[]
  alertsByTicker: Record<string, AlertResponse[]>
  optionChains: Record<string, ChainSnapshot>
  features: Record<string, FeatureResponse>
  scans: Record<number, ScanResponse>

  // Loading states
  healthLoading: boolean
  alertsLoading: boolean
  chainsLoading: boolean
  featuresLoading: boolean
  scansLoading: Record<number, boolean>

  // Error states
  healthError: Error | null
  alertsError: Error | null
  chainsError: Record<string, Error | null>
  featuresError: Record<string, Error | null>
  scansError: Record<number, Error | null>

  // Actions - Health
  setHealth: (health: HealthResponse | null) => void
  setHealthLoading: (loading: boolean) => void
  setHealthError: (error: Error | null) => void

  // Actions - Alerts
  setLatestAlerts: (alerts: AlertResponse[]) => void
  setAlertsByTicker: (ticker: string, alerts: AlertResponse[]) => void
  addAlert: (alert: AlertResponse) => void
  setAlertsLoading: (loading: boolean) => void
  setAlertsError: (error: Error | null) => void
  clearAlerts: () => void

  // Actions - Option Chains
  setOptionChain: (ticker: string, chain: ChainSnapshot) => void
  setChainLoading: (ticker: string, loading: boolean) => void
  setChainError: (ticker: string, error: Error | null) => void
  clearChains: () => void

  // Actions - Features
  setFeatures: (ticker: string, features: FeatureResponse) => void
  setFeaturesLoading: (ticker: string, loading: boolean) => void
  setFeaturesError: (ticker: string, error: Error | null) => void
  clearFeatures: () => void

  // Actions - Scans
  setScan: (scanId: number, scan: ScanResponse) => void
  setScanLoading: (scanId: number, loading: boolean) => void
  setScanError: (scanId: number, error: Error | null) => void
  clearScan: (scanId: number) => void
  clearAllScans: () => void

  // Utility
  getAlertForTicker: (ticker: string) => AlertWithScore[]
  getOptionChain: (ticker: string) => ChainSnapshot | null
  getFeatures: (ticker: string) => FeatureResponse | null
  getScan: (scanId: number) => ScanResponse | null
  reset: () => void
}

const defaultState = {
  health: null,
  latestAlerts: [],
  alertsByTicker: {},
  optionChains: {},
  features: {},
  scans: {},
  healthLoading: false,
  alertsLoading: false,
  chainsLoading: false,
  featuresLoading: false,
  scansLoading: {},
  healthError: null,
  alertsError: null,
  chainsError: {},
  featuresError: {},
  scansError: {}
}

export const useApiStore = create<ApiState>((set, get) => ({
  ...defaultState,

  // Health actions
  setHealth: (health) => set({ health }),
  setHealthLoading: (loading) => set({ healthLoading: loading }),
  setHealthError: (error) => set({ healthError: error }),

  // Alerts actions
  setLatestAlerts: (alerts) => set({ latestAlerts: alerts }),
  setAlertsByTicker: (ticker, alerts) =>
    set((state) => ({
      alertsByTicker: { ...state.alertsByTicker, [ticker]: alerts }
    })),
  addAlert: (alert) =>
    set((state) => ({
      latestAlerts: [alert, ...state.latestAlerts]
    })),
  setAlertsLoading: (loading) => set({ alertsLoading: loading }),
  setAlertsError: (error) => set({ alertsError: error }),
  clearAlerts: () => set({ latestAlerts: [], alertsByTicker: {} }),

  // Option Chains actions
  setOptionChain: (ticker, chain) =>
    set((state) => ({
      optionChains: { ...state.optionChains, [ticker]: chain }
    })),
  setChainLoading: (ticker, loading) =>
    set((state) => ({
      chainsLoading: state.chainsLoading || loading
    })),
  setChainError: (ticker, error) =>
    set((state) => ({
      chainsError: { ...state.chainsError, [ticker]: error }
    })),
  clearChains: () => set({ optionChains: {}, chainsError: {} }),

  // Features actions
  setFeatures: (ticker, features) =>
    set((state) => ({
      features: { ...state.features, [ticker]: features }
    })),
  setFeaturesLoading: (ticker, loading) =>
    set((state) => ({
      featuresLoading: state.featuresLoading || loading
    })),
  setFeaturesError: (ticker, error) =>
    set((state) => ({
      featuresError: { ...state.featuresError, [ticker]: error }
    })),
  clearFeatures: () => set({ features: {}, featuresError: {} }),

  // Scans actions
  setScan: (scanId, scan) =>
    set((state) => ({
      scans: { ...state.scans, [scanId]: scan }
    })),
  setScanLoading: (scanId, loading) =>
    set((state) => ({
      scansLoading: { ...state.scansLoading, [scanId]: loading }
    })),
  setScanError: (scanId, error) =>
    set((state) => ({
      scansError: { ...state.scansError, [scanId]: error }
    })),
  clearScan: (scanId) =>
    set((state) => {
      const { [scanId]: _, ...remainingScans } = state.scans
      const { [scanId]: __, ...remainingErrors } = state.scansError
      return {
        scans: remainingScans,
        scansError: remainingErrors
      }
    }),
  clearAllScans: () => set({ scans: {}, scansError: {} }),

  // Utility actions
  getAlertForTicker: (ticker) => {
    const { alertsByTicker } = get()
    const alerts = alertsByTicker[ticker] || []
    return alerts.map((alert) => ({
      ...alert,
      severityLevel: calculateSeverity(alert.score),
      displayScore: Math.round(alert.score * 100)
    }))
  },

  getOptionChain: (ticker) => {
    const { optionChains } = get()
    return optionChains[ticker] || null
  },

  getFeatures: (ticker) => {
    const { features } = get()
    return features[ticker] || null
  },

  getScan: (scanId) => {
    const { scans } = get()
    return scans[scanId] || null
  },

  reset: () => set(defaultState)
}))

/**
 * Helper function to calculate severity level from score
 */
function calculateSeverity(
  score: number
): 'low' | 'medium' | 'high' | 'critical' {
  if (score >= 0.8) return 'critical'
  if (score >= 0.6) return 'high'
  if (score >= 0.4) return 'medium'
  return 'low'
}
