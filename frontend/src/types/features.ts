// Feature-specific types

export interface Strategy {
  id: string
  name: string
  description: string
  type: 'spread' | 'straddle' | 'condor' | 'butterfly' | 'collar' | 'custom'
  parameters: StrategyParameter[]
  signals: StrategySignal[]
}

export interface StrategyParameter {
  name: string
  value: number
  unit?: string
  min?: number
  max?: number
}

export interface StrategySignal {
  ticker: string
  signal: 'buy' | 'sell' | 'hold'
  confidence: number
  timestamp: string
  parameters: Record<string, unknown>
}

export interface UIState {
  sidebarOpen: boolean
  selectedTicker?: string
  selectedStrategy?: string
  dateRange?: {
    start: string
    end: string
  }
  viewMode: 'grid' | 'list' | 'detailed'
}

export interface PaginationState {
  page: number
  pageSize: number
  total: number
}
