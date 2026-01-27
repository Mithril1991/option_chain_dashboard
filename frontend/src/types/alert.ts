// Alert-specific types and enums

/**
 * Types of alerts based on market conditions
 */
export type AlertType = 'unusual_volume' | 'iv_spike' | 'price_movement' | 'strategy_signal'

/**
 * Alert severity levels
 */
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical'

/**
 * Detector types that generate alerts
 */
export enum DetectorType {
  LOW_IV = 'low_iv',
  RICH_PREMIUM = 'rich_premium',
  EARNINGS_CRUSH = 'earnings_crush',
  TERM_KINK = 'term_kink',
  SKEW_ANOMALY = 'skew_anomaly',
  REGIME_SHIFT = 'regime_shift'
}

/**
 * Types of options strategies
 */
export enum StrategyType {
  WHEEL = 'wheel',
  CSP = 'csp',
  COVERED_CALL = 'covered_call',
  BULL_CALL_SPREAD = 'bull_call_spread',
  BEAR_CALL_SPREAD = 'bear_call_spread',
  BULL_PUT_SPREAD = 'bull_put_spread',
  BEAR_PUT_SPREAD = 'bear_put_spread',
  IRON_CONDOR = 'iron_condor',
  BUTTERFLY = 'butterfly',
  STRADDLE = 'straddle',
  STRANGLE = 'strangle',
  COLLAR = 'collar'
}

/**
 * Alert with calculated fields
 */
export interface AlertWithScore {
  id: number
  ticker: string
  detector_name: DetectorType | string
  score: number
  metrics: Record<string, unknown>
  explanation: Record<string, unknown>
  strategies: StrategyType[] | string[]
  created_at: string
  // Calculated fields
  severityLevel: AlertSeverity
  displayScore: number
}

/**
 * Filter for alert queries
 */
export interface AlertFilter {
  types?: AlertType[]
  severities?: AlertSeverity[]
  tickers?: string[]
  resolved?: boolean
  detectorTypes?: (DetectorType | string)[]
}

/**
 * Alert statistics
 */
export interface AlertStats {
  total: number
  critical: number
  high: number
  medium: number
  low: number
  unresolved: number
}

/**
 * Real-time alert notification
 */
export interface AlertNotification {
  id: string
  message: string
  severity: AlertSeverity
  timestamp: string
}

/**
 * Grouped alerts by ticker
 */
export interface AlertsByTicker {
  ticker: string
  count: number
  severity: AlertSeverity
  alerts: AlertWithScore[]
}
