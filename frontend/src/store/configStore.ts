import { create } from 'zustand'
import { ConfigStatus, HealthResponse } from '@types/api'

interface ConfigState {
  config: ConfigStatus | null
  health: HealthResponse | null
  loading: boolean
  error: string | null
  lastUpdated: string | null

  // Actions
  setConfig: (config: ConfigStatus) => void
  setHealth: (health: HealthResponse) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  updateLastUpdated: () => void
  reset: () => void
  isHealthy: () => boolean
}

const defaultState = {
  config: null,
  health: null,
  loading: false,
  error: null,
  lastUpdated: null
}

export const useConfigStore = create<ConfigState>((set, get) => ({
  ...defaultState,

  setConfig: (config) => {
    set({ config })
    get().updateLastUpdated()
  },

  setHealth: (health) => {
    set({ health })
    get().updateLastUpdated()
  },

  setLoading: (loading) => {
    set({ loading })
  },

  setError: (error) => {
    set({ error })
  },

  updateLastUpdated: () => {
    set({ lastUpdated: new Date().toISOString() })
  },

  reset: () => {
    set(defaultState)
  },

  isHealthy: () => {
    const { health } = get()
    return health?.status === 'ok'
  }
}))
