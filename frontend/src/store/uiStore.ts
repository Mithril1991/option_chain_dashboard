import { create } from 'zustand'
import { UIState } from '@types/features'
import { VIEW_MODES } from '@utils/constants'

interface UIStoreState extends UIState {
  // Actions
  setSidebarOpen: (open: boolean) => void
  toggleSidebar: () => void
  setSelectedTicker: (ticker: string | undefined) => void
  setSelectedStrategy: (strategy: string | undefined) => void
  setDateRange: (range: { start: string; end: string } | undefined) => void
  setViewMode: (mode: 'grid' | 'list' | 'detailed') => void
  reset: () => void
}

const defaultState: UIState = {
  sidebarOpen: true,
  selectedTicker: undefined,
  selectedStrategy: undefined,
  dateRange: undefined,
  viewMode: 'grid'
}

export const useUIStore = create<UIStoreState>((set) => ({
  ...defaultState,

  setSidebarOpen: (open) => {
    set({ sidebarOpen: open })
  },

  toggleSidebar: () => {
    set((state) => ({ sidebarOpen: !state.sidebarOpen }))
  },

  setSelectedTicker: (ticker) => {
    set({ selectedTicker: ticker })
  },

  setSelectedStrategy: (strategy) => {
    set({ selectedStrategy: strategy })
  },

  setDateRange: (range) => {
    set({ dateRange: range })
  },

  setViewMode: (mode) => {
    set({ viewMode: mode })
  },

  reset: () => {
    set(defaultState)
  }
}))
