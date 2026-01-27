import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useHealthCheckIntegration, useLatestAlertsIntegration, useTriggerScanIntegration } from '@hooks/useApiIntegration'
import { MetricsRow } from '@components/MetricsRow'
import { AlertCard } from '@components/AlertCard'
import { formatDate, formatRelativeTime } from '@utils/formatters'
import type { AlertResponse } from '@types/api'

export const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [displayAlerts, setDisplayAlerts] = useState<AlertResponse[]>([])

  // API Integration Hooks
  const { health, loading: healthLoading, error: healthError } = useHealthCheckIntegration()
  const { alerts, loading: alertsLoading, error: alertsError } = useLatestAlertsIntegration(20)
  const { triggerScan, loading: scanLoading, error: scanError } = useTriggerScanIntegration()

  // Update display alerts when fresh data arrives
  useEffect(() => {
    if (alerts && alerts.length > 0) {
      setDisplayAlerts(alerts.slice(0, 10))
    }
  }, [alerts])

  // Calculate metrics
  const totalAlertsToday = alerts?.length || 0
  const highScoreAlerts = alerts?.filter((a) => a.score > 75).length || 0
  const systemHealthy = health?.status === 'ok'
  const isApiConnected = !healthError && health?.status === 'ok'

  // Handle scan trigger
  const handleTriggerScan = async () => {
    try {
      await triggerScan()
    } catch (err) {
      console.error('Failed to trigger scan:', err)
    }
  }

  // Metric boxes configuration
  const metrics = [
    {
      label: 'Total Alerts Today',
      value: totalAlertsToday,
      unit: 'Alerts',
      icon: '🔔'
    },
    {
      label: 'High Score Alerts',
      value: highScoreAlerts,
      unit: 'Score >75',
      icon: '⚡'
    },
    {
      label: 'System Status',
      value: systemHealthy ? 'Healthy' : 'Check Status',
      icon: systemHealthy ? '✓' : '⚠'
    }
  ]

  // Skeleton loader component
  const SkeletonLoader: React.FC = () => (
    <div className="animate-pulse">
      <div className="h-12 bg-gray-200 rounded mb-4" />
      <div className="h-12 bg-gray-200 rounded mb-4" />
      <div className="h-12 bg-gray-200 rounded" />
    </div>
  )

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Option Chain Dashboard</h1>
        <p className="text-gray-600 mt-2">Overview</p>
      </div>

      {/* Error Messages */}
      {healthError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
          <p className="font-semibold">Health Check Error</p>
          <p className="text-sm">{healthError.message}</p>
        </div>
      )}
      {scanError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
          <p className="font-semibold">Scan Error</p>
          <p className="text-sm">{scanError.message}</p>
        </div>
      )}

      {/* Metrics Section */}
      <section className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Key Metrics</h2>
        {healthLoading ? (
          <SkeletonLoader />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {metrics.map((metric, idx) => (
              <div key={idx} className="card p-6 border border-gray-200 rounded-lg">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-600 mb-2">
                      {metric.label}
                    </p>
                    <div className="flex items-baseline gap-2">
                      <p className="text-3xl font-bold text-gray-900">
                        {metric.value}
                      </p>
                      {metric.unit && (
                        <span className="text-sm text-gray-500">
                          {metric.unit}
                        </span>
                      )}
                    </div>
                  </div>
                  {metric.icon && (
                    <span className="text-3xl opacity-60">
                      {metric.icon}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Recent Alerts Section */}
      <section className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-gray-900">Recent Alerts</h2>
          <button
            onClick={() => navigate('/alerts')}
            className="btn-primary px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
          >
            View All Alerts
          </button>
        </div>

        {alertsError && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
            <p className="font-semibold">Failed to load alerts</p>
            <p className="text-sm">{alertsError.message}</p>
          </div>
        )}

        {alertsLoading ? (
          <SkeletonLoader />
        ) : displayAlerts.length > 0 ? (
          <div className="space-y-3">
            {displayAlerts.map((alert) => (
              <div
                key={alert.id}
                onClick={() => navigate(`/ticker/${alert.ticker}`)}
                className="card p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2 flex-wrap">
                      <h3 className="text-lg font-bold text-gray-900">
                        {alert.ticker}
                      </h3>
                      <span className="text-sm font-medium text-gray-600">
                        {alert.detector_name}
                      </span>
                    </div>

                    {/* Score with color coding */}
                    <div className="flex items-center gap-2 mb-2">
                      <div className="flex items-center">
                        <span
                          className={`inline-block px-3 py-1 rounded-full text-sm font-bold text-white ${
                            alert.score >= 90
                              ? 'bg-red-600'
                              : alert.score >= 75
                              ? 'bg-orange-600'
                              : alert.score >= 50
                              ? 'bg-yellow-600'
                              : 'bg-blue-600'
                          }`}
                        >
                          {alert.score.toFixed(0)}
                        </span>
                      </div>
                    </div>

                    {/* Strategies as badges */}
                    {alert.strategies && alert.strategies.length > 0 && (
                      <div className="flex gap-2 flex-wrap">
                        {alert.strategies.map((strategy, idx) => (
                          <span
                            key={idx}
                            className="badge inline-block px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded"
                          >
                            {strategy}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Timestamp */}
                  <div className="flex-shrink-0 text-right">
                    <p className="text-sm text-gray-500">
                      {formatRelativeTime(alert.created_at)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12 text-gray-500">
            <p className="text-lg">No alerts at this time</p>
            <p className="text-sm mt-1">
              Run a scan or check back soon for new market opportunities
            </p>
          </div>
        )}
      </section>

      {/* System Status Section */}
      <section className="card p-6 border border-gray-200 rounded-lg">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">System Status</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          {/* Last Scan */}
          <div>
            <p className="text-sm font-medium text-gray-600 mb-2">Last Scan</p>
            <p className="text-lg text-gray-900">
              {health?.last_scan_time
                ? formatRelativeTime(health.last_scan_time)
                : 'Never'}
            </p>
            {health?.scan_status && health.scan_status !== 'idle' && (
              <p className="text-xs text-gray-500 mt-1">
                Status: {health.scan_status}
              </p>
            )}
          </div>

          {/* Data Mode */}
          <div>
            <p className="text-sm font-medium text-gray-600 mb-2">Data Mode</p>
            <p className="text-lg font-semibold text-blue-600">
              {health?.data_mode ? (health.data_mode === 'demo' ? 'Demo' : 'Production') : 'Unknown'}
            </p>
          </div>

          {/* API Health */}
          <div>
            <p className="text-sm font-medium text-gray-600 mb-2">API Health</p>
            <div className="flex items-center gap-2">
              <div
                className={`w-3 h-3 rounded-full ${
                  isApiConnected ? 'bg-green-500' : 'bg-red-500'
                }`}
              />
              <p className="text-lg text-gray-900">
                {isApiConnected ? 'Connected' : 'Disconnected'}
              </p>
            </div>
            {health?.api_calls_today !== undefined && (
              <p className="text-xs text-gray-500 mt-1">
                API calls today: {health.api_calls_today}
              </p>
            )}
          </div>
        </div>

        {/* Trigger Scan Button */}
        <div className="flex flex-col gap-2">
          <button
            onClick={handleTriggerScan}
            disabled={scanLoading}
            className="btn-primary w-full px-4 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
          >
            {scanLoading ? 'Triggering Scan...' : 'Trigger New Scan'}
          </button>
          {scanError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
              <p className="font-semibold">Scan Trigger Failed</p>
              <p>{scanError.message}</p>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

export default Dashboard
