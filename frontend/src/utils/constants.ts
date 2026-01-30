// Application constants

// Build WebSocket URL dynamically:
// 1. Use VITE_WS_URL env var if available
// 2. Otherwise construct from current window location
const getWebSocketUrl = (): string => {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL
  }
  // Fallback: construct from current host
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  const port = import.meta.env.VITE_API_PORT || '8061'
  return `${protocol}//${host}:${port}/ws`
}

export const API_ENDPOINTS = {
  HEALTH: '/api/health',
  CONFIG: '/api/config',
  ALERTS: '/api/alerts',
  TICKERS: '/api/tickers',
  OPTION_CHAIN: '/api/options/chain',
  STRATEGIES: '/api/strategies',
  WEBSOCKET: getWebSocketUrl()
}

export const ALERT_TYPES = {
  UNUSUAL_VOLUME: 'unusual_volume',
  IV_SPIKE: 'iv_spike',
  PRICE_MOVEMENT: 'price_movement',
  STRATEGY_SIGNAL: 'strategy_signal'
} as const

export const ALERT_SEVERITIES = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical'
} as const

export const SEVERITY_COLORS = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#eab308',
  low: '#2563eb'
}

export const SEVERITY_BADGES = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low'
}

export const STRATEGY_TYPES = {
  SPREAD: 'spread',
  STRADDLE: 'straddle',
  CONDOR: 'condor',
  BUTTERFLY: 'butterfly',
  COLLAR: 'collar',
  CUSTOM: 'custom'
} as const

export const DEFAULT_PAGE_SIZE = 20
export const DEFAULT_REFRESH_INTERVAL = 5000 // 5 seconds
export const WEBSOCKET_RECONNECT_DELAY = 3000 // 3 seconds
export const WEBSOCKET_MAX_RETRIES = 5

export const COMMON_TICKERS = ['SPY', 'QQQ', 'IWM', 'GLD', 'TLT', 'XLE', 'XLF']

export const DATE_FORMATS = {
  SHORT: 'MM/DD/YYYY',
  LONG: 'MMMM D, YYYY',
  TIME_SHORT: 'HH:mm',
  TIME_LONG: 'HH:mm:ss',
  FULL: 'MMMM D, YYYY HH:mm:ss'
}

export const EXPIRATION_DATES = {
  WEEKLY: '0 DTE - 7 DTE',
  BIWEEKLY: '7 DTE - 14 DTE',
  MONTHLY: '14 DTE - 45 DTE',
  QUARTERLY: '45 DTE - 90 DTE',
  LONG_TERM: '90+ DTE'
}

export const VIEW_MODES = {
  GRID: 'grid',
  LIST: 'list',
  DETAILED: 'detailed'
} as const

export const HTTP_STATUS = {
  OK: 200,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  INTERNAL_SERVER_ERROR: 500,
  SERVICE_UNAVAILABLE: 503
}

export const CACHE_KEYS = {
  ALERTS: 'alerts_cache',
  TICKERS: 'tickers_cache',
  OPTION_CHAIN: 'option_chain_cache',
  CONFIG: 'config_cache'
}

export const CACHE_DURATION = {
  SHORT: 60 * 1000, // 1 minute
  MEDIUM: 5 * 60 * 1000, // 5 minutes
  LONG: 30 * 60 * 1000 // 30 minutes
}
