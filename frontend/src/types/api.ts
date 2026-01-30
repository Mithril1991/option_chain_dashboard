// API Response Types

/**
 * Generic API response wrapper
 */
export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
  timestamp: string
}

/**
 * Health check response with complete system status
 */
export interface HealthResponse {
  status: string  // 'ok' or 'error'
  timestamp: string
  message?: string
  last_scan_time?: string  // ISO 8601 timestamp of last completed scan
  uptime_seconds?: number
  data_mode?: string  // 'demo' or 'production'
  scan_status?: string  // 'idle', 'running', 'completed', 'error'
  api_calls_today?: number
  components?: {
    database: { status: string; latency: number }
    dataProvider: { status: string; latency: number }
    analyticsEngine: { status: string; latency: number }
  }
}

/**
 * Scan execution response
 */
export interface ScanResponse {
  scan_id: number
  status: string
  ticker_count: number
  alert_count: number
}

/**
 * Individual alert from detector
 */
export interface AlertResponse {
  id: number
  ticker: string
  detector_name: string
  score: number
  metrics: Record<string, unknown>
  explanation: Record<string, unknown>
  strategies: string[]
  created_at: string
}

/**
 * Lightweight alert summary for dashboard (no heavy metrics)
 */
export interface AlertSummaryResponse {
  id: number
  ticker: string
  detector_name: string
  score: number
  created_at: string
}

export interface AlertsSummaryResponse {
  alerts: AlertSummaryResponse[]
  total_count: number
  timestamp: string
}

/**
 * Option contract in a chain snapshot
 */
export interface OptionContract {
  strike: number
  bid: number
  ask: number
  lastPrice: number
  volume: number
  openInterest: number
  impliedVolatility: number
  delta: number
  gamma: number
  theta: number
  vega: number
  rho?: number
  expirationDate: string
}

/**
 * Snapshot of options chain for a specific expiration
 */
export interface ChainSnapshot {
  ticker: string
  expiration: string
  underlyingPrice: number
  calls: OptionContract[]
  puts: OptionContract[]
}

/**
 * Feature data for a ticker including technicals and volatility metrics
 */
export interface FeatureResponse {
  ticker: string
  timestamp: string
  price: number
  technicals: Record<string, unknown>
  volatility: Record<string, unknown>
  [key: string]: unknown
}

/**
 * Ticker market data
 */
export interface TickerData {
  ticker: string
  price: number
  change: number
  changePercent: number
  volume: number
  lastUpdate: string
}

/**
 * Full options chain with underlying data
 */
export interface OptionChain {
  ticker: string
  expirationDate: string
  calls: OptionContract[]
  puts: OptionContract[]
  underlying: TickerData
}

/**
 * Alert for UI display
 */
export interface Alert {
  id: string
  ticker: string
  type: 'unusual_volume' | 'iv_spike' | 'price_movement' | 'strategy_signal'
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  description: string
  timestamp: string
  data: Record<string, unknown>
  resolved: boolean
}

/**
 * System health status
 */
export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy'
  message: string
  components: {
    database: ComponentStatus
    dataProvider: ComponentStatus
    analyticsEngine: ComponentStatus
  }
  timestamp: string
}

/**
 * Individual component status
 */
export interface ComponentStatus {
  status: 'up' | 'down'
  latency: number
  lastCheck: string
}

/**
 * Configuration status
 */
export interface ConfigStatus {
  configured: boolean
  provider: string
  dataPoints: number
  lastSync: string
  issues: string[]
}
