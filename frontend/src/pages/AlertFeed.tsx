import React, { useState, useMemo, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLatestAlertsSummary } from '@hooks/useApi'
import { formatDate, formatRelativeTime } from '@utils/formatters'
import type { AlertSummaryResponse } from '@types/api'
import { DetectorType } from '@types/alert'

type SortOption = 'score_desc' | 'date_newest' | 'confidence'
type DateRange = '24h' | '7d' | '30d' | 'custom'

interface FilterState {
  tickerSearch: string
  scoreRange: [number, number]
  selectedDetectors: DetectorType[]
  dateRange: DateRange
  customDateStart?: string
  customDateEnd?: string
  sortBy: SortOption
}

// Skeleton loader component
const SkeletonLoader: React.FC = () => (
  <div className="animate-pulse space-y-4">
    {[...Array(5)].map((_, i) => (
      <div key={i} className="h-16 bg-gray-200 rounded" />
    ))}
  </div>
)

// Score color utilities
const getScoreColor = (score: number): string => {
  if (score >= 90) return 'bg-red-100 text-red-900'
  if (score >= 75) return 'bg-orange-100 text-orange-900'
  if (score >= 50) return 'bg-yellow-100 text-yellow-900'
  return 'bg-blue-100 text-blue-900'
}

const getScoreBorderColor = (score: number): string => {
  if (score >= 90) return 'border-l-red-600'
  if (score >= 75) return 'border-l-orange-600'
  if (score >= 50) return 'border-l-yellow-600'
  return 'border-l-blue-600'
}

// Detector type label map
const detectorLabels: Record<DetectorType | string, string> = {
  [DetectorType.LOW_IV]: 'Low IV',
  [DetectorType.RICH_PREMIUM]: 'Rich Premium',
  [DetectorType.EARNINGS_CRUSH]: 'Earnings Crush',
  [DetectorType.TERM_KINK]: 'Term Kink',
  [DetectorType.SKEW_ANOMALY]: 'Skew Anomaly',
  [DetectorType.REGIME_SHIFT]: 'Regime Shift'
}

export const AlertFeed: React.FC = () => {
  const navigate = useNavigate()
  const { data: alertsData, loading, error: apiError, refetch } = useLatestAlertsSummary(50)

  // Local retry and error state for better control
  const [isRetrying, setIsRetrying] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [displayError, setDisplayError] = useState<Error | null>(null)

  // Map to alerts for local use (for backward compatibility with existing render code)
  const alerts = alertsData || []

  // Filter state
  const [filters, setFilters] = useState<FilterState>({
    tickerSearch: '',
    scoreRange: [0, 100],
    selectedDetectors: [],
    dateRange: '24h',
    sortBy: 'score_desc'
  })

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 20

  // Debounce ticker search
  const [debouncedSearch, setDebouncedSearch] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(filters.tickerSearch)
    }, 300)
    return () => clearTimeout(timer)
  }, [filters.tickerSearch])

  // Handle API error state - explicitly clear error when data loads
  useEffect(() => {
    if (alerts.length > 0) {
      // Success: clear all error states
      setRetryCount(0)
      setDisplayError(null)
    } else if (apiError) {
      // Failure: propagate API error to display
      setDisplayError(apiError)
    } else if (loading && retryCount > 0) {
      // Retrying: keep previous error visible
      // No change to displayError
    }
  }, [alerts, apiError, loading, retryCount])

  // Handle retry with exponential backoff
  const handleRetry = useCallback(async () => {
    setIsRetrying(true)
    setRetryCount(prev => prev + 1)
    setDisplayError(null) // Clear error before retrying
    try {
      await refetch()
    } catch (err) {
      // Error will be caught by the hook and set via displayError
      console.error('Refetch failed:', err)
    } finally {
      setIsRetrying(false)
    }
  }, [refetch])

  // Filter and sort alerts
  const filteredAndSortedAlerts = useMemo(() => {
    if (!alerts) return []

    let filtered = alerts

    // Ticker search filter
    if (debouncedSearch) {
      const search = debouncedSearch.toUpperCase()
      filtered = filtered.filter(a => a.ticker.toUpperCase().includes(search))
    }

    // Score range filter
    filtered = filtered.filter(a => a.score >= filters.scoreRange[0] && a.score <= filters.scoreRange[1])

    // Detector type filter
    if (filters.selectedDetectors.length > 0) {
      filtered = filtered.filter(a =>
        filters.selectedDetectors.some(detector =>
          a.detector_name === detector || a.detector_name.includes(detector as string)
        )
      )
    }

    // Date range filter
    const now = new Date()
    let filterDate = new Date()
    switch (filters.dateRange) {
      case '24h':
        filterDate.setDate(filterDate.getDate() - 1)
        break
      case '7d':
        filterDate.setDate(filterDate.getDate() - 7)
        break
      case '30d':
        filterDate.setDate(filterDate.getDate() - 30)
        break
      case 'custom':
        if (filters.customDateStart) {
          filterDate = new Date(filters.customDateStart)
        }
        break
    }
    filtered = filtered.filter(a => new Date(a.created_at) >= filterDate)

    if (filters.dateRange === 'custom' && filters.customDateEnd) {
      const endDate = new Date(filters.customDateEnd)
      endDate.setHours(23, 59, 59, 999)
      filtered = filtered.filter(a => new Date(a.created_at) <= endDate)
    }

    // Sorting
    const sorted = [...filtered]
    switch (filters.sortBy) {
      case 'score_desc':
        sorted.sort((a, b) => b.score - a.score)
        break
      case 'date_newest':
        sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        break
      case 'confidence':
        // Assuming score is confidence metric; if there's a separate confidence field, use that
        sorted.sort((a, b) => b.score - a.score)
        break
    }

    return sorted
  }, [alerts, debouncedSearch, filters])

  // Pagination
  const totalPages = Math.ceil(filteredAndSortedAlerts.length / itemsPerPage)
  const paginatedAlerts = useMemo(() => {
    const startIdx = (currentPage - 1) * itemsPerPage
    return filteredAndSortedAlerts.slice(startIdx, startIdx + itemsPerPage)
  }, [filteredAndSortedAlerts, currentPage])

  // Reset pagination when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [debouncedSearch, filters.scoreRange, filters.selectedDetectors, filters.dateRange, filters.sortBy])

  // Handle detector toggle
  const toggleDetector = useCallback((detector: DetectorType) => {
    setFilters(prev => ({
      ...prev,
      selectedDetectors: prev.selectedDetectors.includes(detector)
        ? prev.selectedDetectors.filter(d => d !== detector)
        : [...prev.selectedDetectors, detector]
    }))
  }, [])

  // Handle export to CSV
  const handleExportCSV = useCallback(() => {
    if (filteredAndSortedAlerts.length === 0) {
      alert('No alerts to export')
      return
    }

    const headers = ['Ticker', 'Detector', 'Score', 'Timestamp']
    const rows = filteredAndSortedAlerts.map(alert => [
      alert.ticker,
      alert.detector_name,
      alert.score.toFixed(2),
      formatDate(alert.created_at, 'long')
    ])

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `alerts-${new Date().toISOString().split('T')[0]}.csv`
    link.click()
  }, [filteredAndSortedAlerts])

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900">Alert Feed</h1>
        <p className="text-gray-600 mt-2">Browse and filter alerts from all detectors</p>
      </div>

      {/* Error State */}
      {displayError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-800">
          <p className="font-semibold">Failed to Load Alerts</p>
          <p className="text-sm mb-3">
            {displayError.message.includes('timeout') ?
              'The request took too long. This might indicate the server is busy.' :
              displayError.message.includes('network') ?
              'Network connection error. Please check your internet connection and try again.' :
              'An error occurred while loading alerts. Please try again.'}
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleRetry}
              disabled={isRetrying || loading}
              className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:bg-gray-400 transition-colors disabled:cursor-not-allowed"
            >
              {isRetrying ? 'Retrying...' : retryCount > 0 ? `Retry (Attempt ${retryCount + 1})` : 'Retry'}
            </button>
            {retryCount > 2 && (
              <p className="text-xs text-red-700 self-center">
                Multiple failures. Server may be unavailable.
              </p>
            )}
          </div>
        </div>
      )}

      {/* Filter Section */}
      <div className="card mb-8 p-6 border border-gray-200 rounded-lg">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Filters</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Ticker Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Search Ticker
            </label>
            <input
              type="text"
              placeholder="Enter ticker symbol (e.g., AAPL)"
              value={filters.tickerSearch}
              onChange={(e) => setFilters(prev => ({ ...prev, tickerSearch: e.target.value }))}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
          </div>

          {/* Date Range */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Date Range
            </label>
            <select
              value={filters.dateRange}
              onChange={(e) => setFilters(prev => ({
                ...prev,
                dateRange: e.target.value as DateRange
              }))}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none bg-white text-gray-900"
            >
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
              <option value="custom">Custom Range</option>
            </select>
          </div>
        </div>

        {/* Custom Date Range */}
        {filters.dateRange === 'custom' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Start Date
              </label>
              <input
                type="date"
                value={filters.customDateStart || ''}
                onChange={(e) => setFilters(prev => ({
                  ...prev,
                  customDateStart: e.target.value
                }))}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-gray-900"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                End Date
              </label>
              <input
                type="date"
                value={filters.customDateEnd || ''}
                onChange={(e) => setFilters(prev => ({
                  ...prev,
                  customDateEnd: e.target.value
                }))}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-gray-900"
              />
            </div>
          </div>
        )}

        {/* Score Range Slider */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Score Range: {filters.scoreRange[0]} - {filters.scoreRange[1]}
          </label>
          <div className="flex gap-4">
            <input
              type="range"
              min="0"
              max="100"
              value={filters.scoreRange[0]}
              onChange={(e) => {
                const newMin = Math.min(Number(e.target.value), filters.scoreRange[1])
                setFilters(prev => ({
                  ...prev,
                  scoreRange: [newMin, prev.scoreRange[1]]
                }))
              }}
              className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
            <input
              type="range"
              min="0"
              max="100"
              value={filters.scoreRange[1]}
              onChange={(e) => {
                const newMax = Math.max(Number(e.target.value), filters.scoreRange[0])
                setFilters(prev => ({
                  ...prev,
                  scoreRange: [prev.scoreRange[0], newMax]
                }))
              }}
              className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
            />
          </div>
        </div>

        {/* Detector Types */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Detector Types
          </label>
          <div className="flex flex-wrap gap-2">
            {Object.values(DetectorType).map(detector => (
              <button
                key={detector}
                onClick={() => toggleDetector(detector)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  filters.selectedDetectors.includes(detector)
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                {detectorLabels[detector]}
              </button>
            ))}
          </div>
        </div>

        {/* Sort */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Sort By
            </label>
            <select
              value={filters.sortBy}
              onChange={(e) => setFilters(prev => ({
                ...prev,
                sortBy: e.target.value as SortOption
              }))}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none bg-white text-gray-900"
            >
              <option value="score_desc">Score (High to Low)</option>
              <option value="date_newest">Date (Newest)</option>
              <option value="confidence">Confidence</option>
            </select>
          </div>

          {/* Export Button */}
          <div className="flex items-end">
            <button
              onClick={handleExportCSV}
              className="w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
            >
              Export as CSV
            </button>
          </div>
        </div>
      </div>

      {/* Results Summary */}
      <div className="mb-6 text-sm text-gray-600">
        Showing {paginatedAlerts.length} of {filteredAndSortedAlerts.length} alerts
        {debouncedSearch && ` (filtered by: ${debouncedSearch})`}
      </div>

      {/* Desktop Table View */}
      {loading ? (
        <SkeletonLoader />
      ) : filteredAndSortedAlerts.length === 0 ? (
        <div className="card p-12 border border-gray-200 rounded-lg text-center">
          <p className="text-gray-500 text-lg">No alerts matching filters</p>
          <p className="text-gray-400 text-sm mt-2">Try adjusting your filter criteria</p>
        </div>
      ) : (
        <>
          {/* Desktop Table */}
          <div className="hidden md:block card border border-gray-200 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Ticker
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Detector
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Score
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Confidence
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Timestamp
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {paginatedAlerts.map(alert => (
                  <tr
                    key={alert.id}
                    onClick={() => navigate(`/ticker/${alert.ticker}`)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                      {alert.ticker}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                      {detectorLabels[alert.detector_name] || alert.detector_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getScoreColor(alert.score)}`}>
                        {alert.score.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                      {(alert.score > 75 ? 'High' : alert.score > 50 ? 'Medium' : 'Low')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                      {formatRelativeTime(alert.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Card View */}
          <div className="md:hidden space-y-4">
            {paginatedAlerts.map(alert => (
              <div
                key={alert.id}
                onClick={() => navigate(`/ticker/${alert.ticker}`)}
                className={`card p-4 border-l-4 ${getScoreBorderColor(alert.score)} cursor-pointer hover:shadow-md transition-shadow`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-bold text-lg text-gray-900">{alert.ticker}</h3>
                    <p className="text-sm text-gray-600">
                      {detectorLabels[alert.detector_name] || alert.detector_name}
                    </p>
                  </div>
                  <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getScoreColor(alert.score)}`}>
                    {alert.score.toFixed(1)}
                  </span>
                </div>

                <div className="space-y-2 text-sm">
                  <div>
                    <p className="text-gray-600">
                      <strong>Confidence:</strong> {alert.score > 75 ? 'High' : alert.score > 50 ? 'Medium' : 'Low'}
                    </p>
                  </div>
                  <p className="text-gray-500 text-xs">
                    {formatDate(alert.created_at, 'long')}
                  </p>
                  <p className="text-xs text-blue-600 mt-2">Click to view full details</p>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-8 flex items-center justify-between">
              <button
                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                disabled={currentPage === 1}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Previous
              </button>

              <div className="flex items-center gap-2">
                {[...Array(totalPages)].map((_, idx) => {
                  const page = idx + 1
                  // Show current page and 2 pages around it
                  if (
                    page === currentPage ||
                    (page >= currentPage - 1 && page <= currentPage + 1) ||
                    page === 1 ||
                    page === totalPages
                  ) {
                    return (
                      <button
                        key={page}
                        onClick={() => setCurrentPage(page)}
                        className={`px-3 py-2 rounded-lg transition-colors ${
                          page === currentPage
                            ? 'bg-blue-600 text-white'
                            : 'border border-gray-300 text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        {page}
                      </button>
                    )
                  }
                  if (page === currentPage - 2 || page === currentPage + 2) {
                    return (
                      <span key={page} className="text-gray-500">
                        ...
                      </span>
                    )
                  }
                  return null
                })}
              </div>

              <button
                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                disabled={currentPage === totalPages}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default AlertFeed
