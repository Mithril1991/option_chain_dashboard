import React, { useState, useEffect } from 'react'
import { useHealthCheckIntegration } from '@hooks/useApiIntegration'
import { formatDate, formatRelativeTime } from '@utils/formatters'

// Simple logger for error tracking
const logger = {
  error: (msg: string) => console.error(`[ConfigStatus] ${msg}`),
}

// Mock data for configuration - replace with real API calls as needed
interface SystemConfig {
  riskFreeRate: number
  maxAlertsPerDay: number
  alertCooldownHours: number
  marginRequirementPercent: number
  maxConcentrationPercent: number
  lastScanTime?: string
  nextScanTime?: string
  uptime: string
}

interface Watchlist {
  tickers: string[]
  lastUpdated: string
}

// System Status Section Component
const SystemStatusSection: React.FC<{ config: SystemConfig }> = ({ config }) => {
  const getRelativeTime = (timestamp?: string): string => {
    if (!timestamp) return 'Not available'
    return formatRelativeTime(new Date(timestamp))
  }

  return (
    <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
      <h2 className="text-xl font-bold text-gray-900 mb-6">System Status</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border-l-4 border-blue-500 pl-4">
          <p className="text-sm font-medium text-gray-600 mb-1">Last Scan</p>
          <p className="text-lg font-semibold text-gray-900">
            {getRelativeTime(config.lastScanTime)}
          </p>
        </div>

        <div className="border-l-4 border-blue-500 pl-4">
          <p className="text-sm font-medium text-gray-600 mb-1">Next Scheduled Scan</p>
          <p className="text-lg font-semibold text-gray-900">
            {config.nextScanTime ? formatDate(config.nextScanTime, 'long') : 'Not scheduled'}
          </p>
        </div>

        <div className="border-l-4 border-green-500 pl-4">
          <p className="text-sm font-medium text-gray-600 mb-1">System Uptime</p>
          <p className="text-lg font-semibold text-gray-900">{config.uptime}</p>
        </div>

        <div className="border-l-4 border-purple-500 pl-4">
          <p className="text-sm font-medium text-gray-600 mb-1">Current Scan Status</p>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-green-500"></span>
            <p className="text-lg font-semibold text-gray-900">Idle</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// Data Mode Section Component
const DataModeSection: React.FC<{ mode: 'demo' | 'production' }> = ({ mode }) => {
  const [currentMode, setCurrentMode] = useState<'demo' | 'production'>(mode)
  const [isChanging, setIsChanging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  /**
   * Handle mode toggle - sends POST request to backend to update data mode.
   *
   * WHY THIS DESIGN:
   * - Changes take effect immediately (no restart required)
   * - Safe for testing: switch to demo, test, switch to production
   * - Audit trail logged on backend with timestamps
   * - User-friendly loading/error states
   */
  const handleModeToggle = async (newMode: 'demo' | 'production') => {
    // Prevent duplicate requests while one is in flight
    if (isChanging) return

    setIsChanging(true)
    setError(null)
    setSuccess(null)

    try {
      // Call backend endpoint to update data mode
      const response = await fetch('http://192.168.1.16:8061/config/data-mode', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ mode: newMode }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(
          errorData.detail ||
          errorData.message ||
          `Failed to update mode: ${response.status}`
        )
      }

      const data = await response.json()

      // Update local state to match backend
      setCurrentMode(newMode)
      setSuccess(`Successfully switched to ${newMode} mode`)

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMessage)
      logger.error(`Mode toggle failed: ${errorMessage}`)
    } finally {
      setIsChanging(false)
    }
  }

  return (
    <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Data Mode</h2>

      <div className="space-y-6">
        {/* Current Mode Indicator */}
        <div className="flex items-center gap-4 p-4 rounded-lg bg-gray-50">
          <div className={`w-4 h-4 rounded-full transition-colors ${
            currentMode === 'demo' ? 'bg-blue-500' : 'bg-green-500'
          }`}></div>
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-600">Current Mode</p>
            <p className="text-lg font-bold text-gray-900 capitalize">{currentMode}</p>
          </div>
          <p className="text-xs text-gray-500">
            {currentMode === 'demo' ? 'Synthetic data' : 'Live market data'}
          </p>
        </div>

        {/* Mode Explanation */}
        <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
          <p className="text-sm text-blue-800">
            {currentMode === 'demo'
              ? 'Demo Mode: Using synthetic market data for testing and development. Perfect for learning the platform without API costs.'
              : 'Production Mode: Using live market data from data providers. Ensures real-time analysis with actual market conditions.'}
          </p>
        </div>

        {/* Toggle Buttons */}
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => handleModeToggle('demo')}
            disabled={isChanging}
            className={`py-2 px-4 rounded-lg font-medium transition-all ${
              currentMode === 'demo'
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            } disabled:opacity-50`}
          >
            {isChanging && currentMode === 'demo' ? 'Switching...' : 'Switch to Demo'}
          </button>
          <button
            onClick={() => handleModeToggle('production')}
            disabled={isChanging}
            className={`py-2 px-4 rounded-lg font-medium transition-all ${
              currentMode === 'production'
                ? 'bg-green-600 text-white shadow-md'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            } disabled:opacity-50`}
          >
            {isChanging && currentMode === 'production' ? 'Switching...' : 'Switch to Production'}
          </button>
        </div>

        {/* Success Message */}
        {success && (
          <div className="p-3 bg-green-50 rounded-lg border border-green-200">
            <p className="text-sm font-semibold text-green-800">{success}</p>
            <p className="text-xs text-green-700 mt-1">
              Changes take effect immediately for subsequent API calls.
            </p>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="p-3 bg-red-50 rounded-lg border border-red-200">
            <p className="text-sm font-semibold text-red-800 mb-1">Error</p>
            <p className="text-xs text-red-700">{error}</p>
          </div>
        )}

        {/* Info Note */}
        <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
          <p className="text-xs font-semibold text-blue-800 mb-1">How it works:</p>
          <p className="text-xs text-blue-700">
            Mode changes take effect immediately on the backend (no restart needed).
            Subsequent API calls will use the new data source (demo or production).
          </p>
        </div>
      </div>
    </div>
  )
}

// Configuration Summary Section Component
const ConfigurationSummarySection: React.FC<{ config: SystemConfig }> = ({ config }) => {
  const configItems = [
    { label: 'Risk-Free Rate', value: `${(config.riskFreeRate * 100).toFixed(2)}%` },
    { label: 'Max Alerts per Day', value: config.maxAlertsPerDay.toString() },
    { label: 'Alert Cooldown', value: `${config.alertCooldownHours} hours` },
    { label: 'Margin Requirement', value: `${config.marginRequirementPercent}%` },
    { label: 'Max Concentration', value: `${config.maxConcentrationPercent}%` }
  ]

  return (
    <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
      <h2 className="text-xl font-bold text-gray-900 mb-6">Configuration Summary</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {configItems.map((item, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200"
          >
            <span className="text-sm font-medium text-gray-600">{item.label}</span>
            <span className="text-lg font-semibold text-gray-900">{item.value}</span>
          </div>
        ))}
      </div>

      <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
        <p className="text-xs text-gray-500">
          All configuration values are read-only. Modify settings in the backend configuration files.
        </p>
      </div>
    </div>
  )
}

// Watchlist Section Component
const WatchlistSection: React.FC<{ watchlist: Watchlist }> = ({ watchlist }) => {
  const [copied, setCopied] = useState(false)

  const handleCopyToClipboard = () => {
    const tickerList = watchlist.tickers.join(', ')
    navigator.clipboard.writeText(tickerList)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Watchlist</h2>
        <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
          Monitoring {watchlist.tickers.length} tickers
        </span>
      </div>

      {watchlist.tickers.length > 0 ? (
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

// API Status Section Component
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

// Main ConfigStatus Component
export const ConfigStatus: React.FC = () => {
  const [dataMode, setDataMode] = useState<'demo' | 'production'>('demo')
  const [loadingMode, setLoadingMode] = useState(true)

  // Fetch current data mode from backend on component mount
  useEffect(() => {
    const fetchDataMode = async () => {
      try {
        const response = await fetch('http://192.168.1.16:8061/config/data-mode')
        if (response.ok) {
          const data = await response.json()
          setDataMode(data.mode === 'demo' ? 'demo' : 'production')
        }
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

  // Mock configuration data
  const mockConfig: SystemConfig = {
    riskFreeRate: 0.045,
    maxAlertsPerDay: 50,
    alertCooldownHours: 2,
    marginRequirementPercent: 25,
    maxConcentrationPercent: 5,
    lastScanTime: new Date(Date.now() - 15 * 60000).toISOString(), // 15 minutes ago
    nextScanTime: new Date(Date.now() + 45 * 60000).toISOString(), // 45 minutes from now
    uptime: '7 days 14 hours'
  }

  // Mock watchlist data
  const mockWatchlist: Watchlist = {
    tickers: ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN', 'META', 'NVDA', 'AMD'],
    lastUpdated: new Date().toISOString()
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Configuration & Status</h1>
        <p className="text-gray-600 mt-2">System health monitoring and configuration overview</p>
      </div>

      {/* System Status Section */}
      <SystemStatusSection config={mockConfig} />

      {/* Data Mode Section */}
      {!loadingMode && <DataModeSection mode={dataMode} />}

      {/* Configuration Summary Section */}
      <ConfigurationSummarySection config={mockConfig} />

      {/* Watchlist Section */}
      <WatchlistSection watchlist={mockWatchlist} />

      {/* API Status Section */}
      <APIStatusSection />
    </div>
  )
}

export default ConfigStatus
