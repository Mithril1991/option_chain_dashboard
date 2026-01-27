import { create } from 'zustand'
import { Alert, AlertFilter, AlertStats } from '@types/alert'

interface AlertState {
  alerts: Alert[]
  filter: AlertFilter
  stats: AlertStats
  loading: boolean
  error: string | null

  // Actions
  setAlerts: (alerts: Alert[]) => void
  addAlert: (alert: Alert) => void
  removeAlert: (id: string) => void
  updateAlert: (id: string, alert: Partial<Alert>) => void
  resolveAlert: (id: string) => void
  setFilter: (filter: AlertFilter) => void
  clearFilter: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  computeStats: () => void
  getFilteredAlerts: () => Alert[]
}

const defaultStats: AlertStats = {
  total: 0,
  critical: 0,
  high: 0,
  medium: 0,
  low: 0,
  unresolved: 0
}

const defaultFilter: AlertFilter = {
  resolved: false
}

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  filter: defaultFilter,
  stats: defaultStats,
  loading: false,
  error: null,

  setAlerts: (alerts) => {
    set({ alerts })
    get().computeStats()
  },

  addAlert: (alert) => {
    set((state) => ({
      alerts: [alert, ...state.alerts]
    }))
    get().computeStats()
  },

  removeAlert: (id) => {
    set((state) => ({
      alerts: state.alerts.filter((a) => a.id !== id)
    }))
    get().computeStats()
  },

  updateAlert: (id, updates) => {
    set((state) => ({
      alerts: state.alerts.map((a) => (a.id === id ? { ...a, ...updates } : a))
    }))
    get().computeStats()
  },

  resolveAlert: (id) => {
    get().updateAlert(id, { resolved: true })
  },

  setFilter: (filter) => {
    set({ filter })
  },

  clearFilter: () => {
    set({ filter: defaultFilter })
  },

  setLoading: (loading) => {
    set({ loading })
  },

  setError: (error) => {
    set({ error })
  },

  computeStats: () => {
    const { alerts } = get()
    const stats: AlertStats = {
      total: alerts.length,
      critical: alerts.filter((a) => a.severity === 'critical').length,
      high: alerts.filter((a) => a.severity === 'high').length,
      medium: alerts.filter((a) => a.severity === 'medium').length,
      low: alerts.filter((a) => a.severity === 'low').length,
      unresolved: alerts.filter((a) => !a.resolved).length
    }
    set({ stats })
  },

  getFilteredAlerts: () => {
    const { alerts, filter } = get()
    let filtered = alerts

    if (filter.types && filter.types.length > 0) {
      filtered = filtered.filter((a) => filter.types!.includes(a.type))
    }

    if (filter.severities && filter.severities.length > 0) {
      filtered = filtered.filter((a) => filter.severities!.includes(a.severity))
    }

    if (filter.tickers && filter.tickers.length > 0) {
      filtered = filtered.filter((a) => filter.tickers!.includes(a.ticker))
    }

    if (filter.resolved !== undefined) {
      filtered = filtered.filter((a) => a.resolved === filter.resolved)
    }

    return filtered
  }
}))
