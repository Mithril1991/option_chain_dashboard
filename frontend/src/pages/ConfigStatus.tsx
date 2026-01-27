import React, { useState, useEffect } from 'react'
import { useHealthCheckIntegration } from '@hooks/useApiIntegration'
import { formatDate, formatRelativeTime, formatUptime } from '@utils/formatters'
import apiClient from '@utils/apiClient'

// Simple logger for error tracking
const logger = {
  error: (msg: string) => console.error(`[ConfigStatus] ${msg}`),
}

interface Watchlist {
  tickers: string[]
  lastUpdated: string
}

// ========================================
// System Status Section Component
// Fetches real data from the /health endpoint
// ========================================
const SystemStatusSection: React.FC = () => {
  const { health, loading, error } = useHealthCheckIntegration()

  if (loading) {
    return (
      <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="ml-3 text-gray-600">Loading system status...</p>
        </div>
      </div>
    )
  }

  if (error || !health) {
    return (
      <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
        <p className="text-red-600">Unable to load system status</p>
      </div>
    )
  }

  return (
    <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
      <h2 className="text-xl font-bold text-gray-900 mb-6">System Status</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border-l-4 border-blue-500 pl-4">
          <p className="text-sm font-medium text-gray-600 mb-1">Last Scan</p>
          <p className="text-lg font-semibold text-gray-900">
            {health.last_scan_time ? formatRelativeTime(health.last_scan_time) : 'Never'}
          </p>
        </div>

        <div className="border-l-4 border-blue-500 pl-4">
          <p className="text-sm font-medium text-gray-600 mb-1">Scan Status</p>
          <p className="text-lg font-semibold text-gray-900 capitalize">
            {health.scan_status || 'unknown'}
          </p>
        </div>

        <div className="border-l-4 border-green-500 pl-4">
          <p className="text-sm font-medium text-gray-600 mb-1">System Uptime</p>
          <p className="text-lg font-semibold text-gray-900">
            {formatUptime(health.uptime_seconds || 0)}
          </p>
        </div>

        <div className="border-l-4 border-purple-500 pl-4">
          <p className="text-sm font-medium text-gray-600 mb-1">API Budget (24h)</p>
          <p className="text-lg font-semibold text-gray-900">
            {health.api_calls_today || 0} / ~2000
          </p>
        </div>
      </div>
    </div>
  )
}

// ========================================
// Data Mode Section Component
// Now uses apiClient for consistent error handling
// ========================================
const DataModeSection: React.FC<{ mode: 'demo' | 'production'; loading: boolean }> = ({ mode, loading }) => {
  const [switching, setSwitching] = useState(false)

  const handleModeToggle = async () => {
    setSwitching(true)
    try {
      const newMode = mode === 'demo' ? 'production' : 'demo'
      await apiClient.post('/config/data-mode', { mode: newMode })
      window.location.reload()
    } catch (err) {
      logger.error(`Failed to switch data mode: ${err instanceof Error ? err.message : 'Unknown error'}`)
      setSwitching(false)
    }
  }

  if (loading) {
    return (
      <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Data Mode</h2>
        <span
          className={`px-3 py-1 rounded-full text-sm font-medium ${
            mode === 'demo'
              ? 'bg-yellow-100 text-yellow-800'
              : 'bg-green-100 text-green-800'
          }`}
        >
          {mode === 'demo' ? 'Demo Mode' : 'Production Mode'}
        </span>
      </div>

      <div className="mb-6 p-4 bg-gray-50 rounded-lg">
        <p className="text-sm text-gray-700 mb-3">
          {mode === 'demo'
            ? 'Running in demo mode with simulated data. No real market data is being fetched.'
            : 'Running in production mode with live market data from Yahoo Finance.'}
        </p>

        <button
          onClick={handleModeToggle}
          disabled={switching}
          className={`w-full py-2 px-4 rounded-lg font-medium transition-all ${
            switching
              ? 'bg-gray-400 text-gray-200 cursor-not-allowed'
              : mode === 'demo'
              ? 'bg-green-600 text-white hover:bg-green-700'
              : 'bg-yellow-600 text-white hover:bg-yellow-700'
          }`}
        >
          {switching ? 'Switching...' : `Switch to ${mode === 'demo' ? 'Production' : 'Demo'} Mode`}
        </button>
      </div>

      <p className="text-xs text-gray-500">
        Note: Switching modes will reload the application.
      </p>
    </div>
  )
}

// ========================================
// Watchlist Section Component
// Now fetches real watchlist data from backend
// ========================================
const WatchlistSection: React.FC = () => {
  const [watchlist, setWatchlist] = useState<Watchlist | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const fetchWatchlist = async () => {
      try {
        setLoading(true)
        // Try to fetch real watchlist from backend
        const response = await apiClient.get('/config/watchlist')
        setWatchlist(response.data)
        setError(null)
      } catch (err) {
        logger.error(`Failed to fetch watchlist: ${err instanceof Error ? err.message : 'Unknown error'}`)
        // Fallback to empty watchlist
        setWatchlist({ tickers: [], lastUpdated: new Date().toISOString() })
        setError('Unable to load watchlist from server')
      } finally {
        setLoading(false)
      }
    }

    fetchWatchlist()
  }, [])

  const handleCopyToClipboard = () => {
    if (watchlist && watchlist.tickers.length > 0) {
      const tickerList = watchlist.tickers.join(', ')
      navigator.clipboard.writeText(tickerList)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (loading) {
    return (
      <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="ml-3 text-gray-600">Loading watchlist...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Watchlist</h2>
        <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
          Monitoring {watchlist?.tickers.length || 0} tickers
        </span>
      </div>

      {error && (
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg mb-4">
          <p className="text-sm text-yellow-800">{error}</p>
        </div>
      )}

      {watchlist && watchlist.tickers.length > 0 ? (
        <>
          {/* Ticker Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {watchlist.tickers.map((ticker, idx) => (
              <div
                key={idx}
                className="px-4 py-3 bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg border border-blue-300 text-center"
              >
                <p className="font-bold text-blue-900 text-lg">{ticker}</p>
              </div>
            ))}
          </div>

          {/* Copy to Clipboard Button */}
          <button
            onClick={handleCopyToClipboard}
            className={`w-full py-2 px-4 rounded-lg font-medium transition-all ${
              copied
                ? 'bg-green-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {copied ? 'Copied to Clipboard!' : 'Copy to Clipboard'}
          </button>

          {/* Last Updated */}
          <p className="text-xs text-gray-500 text-center mt-4">
            Last updated: {formatRelativeTime(new Date(watchlist.lastUpdated))}
          </p>
        </>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <p className="text-lg">No tickers in watchlist</p>
          <p className="text-sm mt-2">Add tickers to monitor market opportunities</p>
        </div>
      )}
    </div>
  )
}

// ========================================
// API Status Section Component
// Uses useHealthCheckIntegration to fetch real health data
// ========================================
const APIStatusSection: React.FC = () => {
  const { health, loading, error, refetch } = useHealthCheckIntegration()
  const [lastRefresh, setLastRefresh] = useState(new Date())
  const [autoRefreshActive, setAutoRefreshActive] = useState(true)

  // Auto-refresh every 30 seconds
  useEffect(() => {
    if (!autoRefreshActive) return

    const interval = setInterval(() => {
      refetch()
      setLastRefresh(new Date())
    }, 30000)

    return () => clearInterval(interval)
  }, [autoRefreshActive, refetch])

  const handleManualRefresh = () => {
    refetch()
    setLastRefresh(new Date())
  }

  return (
    <div className="card p-6 border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">API Status</h2>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={autoRefreshActive}
              onChange={(e) => setAutoRefreshActive(e.target.checked)}
              className="rounded w-4 h-4"
            />
            Auto-refresh
          </label>
          <button
            onClick={handleManualRefresh}
            disabled={loading}
            className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:bg-gray-400"
          >
            {loading ? 'Checking...' : 'Refresh'}
          </button>
        </div>
      </div>

      {loading && !health ? (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="ml-3 text-gray-600">Checking API health...</p>
        </div>
      ) : error ? (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="font-semibold text-red-800 mb-1">Connection Error</p>
          <p className="text-sm text-red-700 mb-3">{error.message}</p>
          <button
            onClick={handleManualRefresh}
            className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      ) : health ? (
        <div className="space-y-4">
          {/* API Server Status */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div>
              <p className="font-semibold text-gray-900">API Server</p>
              <p className="text-sm text-gray-600">Backend connectivity status</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-green-500"></span>
              <span className="font-semibold text-green-700">Connected</span>
            </div>
          </div>

          {/* Response Time */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div>
              <p className="font-semibold text-gray-900">Response Time</p>
              <p className="text-sm text-gray-600">API latency measurement</p>
            </div>
            <p className="text-lg font-semibold text-gray-900">
              {health.components?.database?.latency || 0}ms
            </p>
          </div>

          {/* Components Status */}
          <div className="border-t border-gray-200 pt-4">
            <h3 className="font-semibold text-gray-900 mb-3">Component Status</h3>
            <div className="space-y-3">
              {/* Database */}
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className={`w-3 h-3 rounded-full ${
                    health.components?.database?.status === 'up'
                      ? 'bg-green-500'
                      : 'bg-red-500'
                  }`}></span>
                  <div>
                    <p className="font-medium text-gray-900">Database</p>
                    <p className="text-xs text-gray-500">
                      Latency: {health.components?.database?.latency || 0}ms
                    </p>
                  </div>
                </div>
                <span className={`text-xs font-semibold ${
                  health.components?.database?.status === 'up'
                    ? 'text-green-700'
                    : 'text-red-700'
                }`}>
                  {health.components?.database?.status === 'up' ? 'UP' : 'DOWN'}
                </span>
              </div>

              {/* Data Provider */}
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className={`w-3 h-3 rounded-full ${
                    health.components?.dataProvider?.status === 'up'
                      ? 'bg-green-500'
                      : 'bg-red-500'
                  }`}></span>
                  <div>
                    <p className="font-medium text-gray-900">Data Provider</p>
                    <p className="text-xs text-gray-500">
                      Latency: {health.components?.dataProvider?.latency || 0}ms
                    </p>
                  </div>
                </div>
                <span className={`text-xs font-semibold ${
                  health.components?.dataProvider?.status === 'up'
                    ? 'text-green-700'
                    : 'text-red-700'
                }`}>
                  {health.components?.dataProvider?.status === 'up' ? 'UP' : 'DOWN'}
                </span>
              </div>

              {/* Analytics Engine */}
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className={`w-3 h-3 rounded-full ${
                    health.components?.analyticsEngine?.status === 'up'
                      ? 'bg-green-500'
                      : 'bg-red-500'
                  }`}></span>
                  <div>
                    <p className="font-medium text-gray-900">Analytics Engine</p>
                    <p className="text-xs text-gray-500">
                      Latency: {health.components?.analyticsEngine?.latency || 0}ms
                    </p>
                  </div>
                </div>
                <span className={`text-xs font-semibold ${
                  health.components?.analyticsEngine?.status === 'up'
                    ? 'text-green-700'
                    : 'text-red-700'
                }`}>
                  {health.components?.analyticsEngine?.status === 'up' ? 'UP' : 'DOWN'}
                </span>
              </div>
            </div>
          </div>

          {/* Health Status Summary */}
          <div className={`p-4 rounded-lg border ${
            health.status === 'healthy'
              ? 'bg-green-50 border-green-200'
              : health.status === 'degraded'
              ? 'bg-yellow-50 border-yellow-200'
              : 'bg-red-50 border-red-200'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <p className="font-semibold text-gray-900">Overall Health</p>
              <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${
                health.status === 'healthy'
                  ? 'bg-green-200 text-green-900'
                  : health.status === 'degraded'
                  ? 'bg-yellow-200 text-yellow-900'
                  : 'bg-red-200 text-red-900'
              }`}>
                {health.status}
              </span>
            </div>
            <p className={`text-sm ${
              health.status === 'healthy'
                ? 'text-green-700'
                : health.status === 'degraded'
                ? 'text-yellow-700'
                : 'text-red-700'
            }`}>
              {health.message}
            </p>
          </div>

          {/* Last Check Time */}
          <p className="text-xs text-gray-500 text-right">
            Last checked: {formatRelativeTime(new Date(lastRefresh))}
          </p>
        </div>
      ) : null}
    </div>
  )
}

// ========================================
// Main ConfigStatus Component
// ========================================
export const ConfigStatus: React.FC = () => {
  const [dataMode, setDataMode] = useState<'demo' | 'production'>('demo')
  const [loadingMode, setLoadingMode] = useState(true)

  // Fetch current data mode from backend on component mount
  useEffect(() => {
    const fetchDataMode = async () => {
      try {
        const response = await apiClient.get('/config/data-mode')
        setDataMode(response.data.mode === 'demo' ? 'demo' : 'production')
      } catch (err) {
        logger.error(`Failed to fetch data mode: ${err instanceof Error ? err.message : 'Unknown error'}`)
        // Default to demo if fetch fails
        setDataMode('demo')
      } finally {
        setLoadingMode(false)
      }
    }

    fetchDataMode()
  }, [])

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Configuration & Status</h1>
        <p className="text-gray-600 mt-2">System health monitoring and configuration overview</p>
      </div>

      {/* System Status Section */}
      <SystemStatusSection />

      {/* Data Mode Section */}
      {!loadingMode && <DataModeSection mode={dataMode} loading={loadingMode} />}

      {/* Watchlist Section */}
      <WatchlistSection />

      {/* API Status Section */}
      <APIStatusSection />
    </div>
  )
}

export default ConfigStatus
