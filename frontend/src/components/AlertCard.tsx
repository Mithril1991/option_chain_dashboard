import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertResponse } from '@types/api'
import { formatRelativeTime } from '@utils/formatters'
import { getSeverityColor } from '@utils/formatters'

/**
 * Props for AlertCard component
 */
interface AlertCardProps {
  /** Alert data from API */
  alert: AlertResponse
  /** Optional callback when resolving alert */
  onResolve?: (id: number) => void | Promise<void>
  /** Optional callback when dismissing alert */
  onDismiss?: (id: number) => void | Promise<void>
  /** Optional callback when clicking card (for expansion) */
  onClick?: (alertId: number) => void
  /** Optional: show full explanation data */
  showDetails?: boolean
  /** Optional: custom CSS class */
  className?: string
}

/**
 * Alert Card Component - Displays single market alert
 *
 * Features:
 * - Color-coded severity indicator (critical/high/medium/low)
 * - Alert type badge (unusual_volume, iv_spike, etc.)
 * - Clickable to navigate to ticker detail page
 * - Score display with color gradient
 * - Strategy badges showing recommended strategies
 * - Timestamp in relative format (e.g., "5m ago")
 * - Optional action buttons (resolve/dismiss)
 * - Expandable for detailed metrics
 * - Loading states for async operations
 *
 * Design:
 * - Left border color matches severity
 * - Card hover effect for interactivity
 * - Responsive grid for data display
 * - Semantic HTML structure
 *
 * Accessibility:
 * - Proper aria-labels on action buttons
 * - Keyboard navigable buttons
 * - Clear visual feedback
 *
 * @component
 * @example
 * ```tsx
 * <AlertCard
 *   alert={alert}
 *   onResolve={handleResolve}
 *   showDetails={true}
 * />
 * ```
 */
export const AlertCard: React.FC<AlertCardProps> = ({
  alert,
  onResolve,
  onDismiss,
  onClick,
  showDetails = false,
  className = ''
}) => {
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(showDetails)
  const [resolving, setResolving] = useState(false)
  const [dismissing, setDismissing] = useState(false)

  /**
   * Map detector name to human-readable format
   */
  const detectorLabel = alert.detector_name
    ? alert.detector_name.replace(/_/g, ' ').toUpperCase()
    : 'Unknown'

  /**
   * Get color classes for score-based styling
   */
  const getScoreColor = (score: number): string => {
    if (score >= 90) return 'bg-red-600 text-white'
    if (score >= 75) return 'bg-orange-600 text-white'
    if (score >= 50) return 'bg-yellow-600 text-white'
    return 'bg-blue-600 text-white'
  }

  /**
   * Get severity border color
   */
  const getSeverityBorder = (score: number): string => {
    if (score >= 90) return 'border-l-red-600'
    if (score >= 75) return 'border-l-orange-600'
    if (score >= 50) return 'border-l-yellow-600'
    return 'border-l-blue-600'
  }

  /**
   * Handle resolve button click
   */
  const handleResolve = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!onResolve) return

    try {
      setResolving(true)
      await onResolve(alert.id)
    } catch (error) {
      console.error('Failed to resolve alert:', error)
    } finally {
      setResolving(false)
    }
  }

  /**
   * Handle dismiss button click
   */
  const handleDismiss = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!onDismiss) return

    try {
      setDismissing(true)
      await onDismiss(alert.id)
    } catch (error) {
      console.error('Failed to dismiss alert:', error)
    } finally {
      setDismissing(false)
    }
  }

  /**
   * Handle card click - navigate to ticker
   */
  const handleCardClick = () => {
    if (onClick) {
      onClick(alert.id)
    } else {
      navigate(`/ticker/${alert.ticker}`)
    }
  }

  /**
   * Format metric value for display
   */
  const formatMetricValue = (value: unknown): string => {
    if (typeof value === 'number') {
      return value.toFixed(2)
    }
    return String(value)
  }

  return (
    <div
      className={`card border-l-4 transition-all duration-200 ${getSeverityBorder(
        alert.score
      )} ${className}`}
      role="article"
      aria-label={`Alert for ${alert.ticker}: ${detectorLabel}`}
    >
      <div
        className="cursor-pointer hover:bg-gray-50 p-4 rounded transition-colors"
        onClick={handleCardClick}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Header with Ticker and Detector */}
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <h3 className="text-lg font-bold text-gray-900">{alert.ticker}</h3>
              <span className="text-xs sm:text-sm font-medium text-gray-600 bg-gray-100 px-2 py-1 rounded">
                {detectorLabel}
              </span>
            </div>

            {/* Score Badge */}
            <div className="flex items-center gap-3 mb-3">
              <span
                className={`inline-block px-3 py-1 rounded-full text-sm font-bold ${getScoreColor(
                  alert.score
                )}`}
              >
                Score: {alert.score.toFixed(0)}
              </span>
              <span className="text-xs text-gray-500">
                {formatRelativeTime(alert.created_at)}
              </span>
            </div>

            {/* Strategies Badges */}
            {alert.strategies && alert.strategies.length > 0 && (
              <div className="flex gap-2 flex-wrap mb-3">
                {alert.strategies.slice(0, 3).map((strategy, idx) => (
                  <span
                    key={idx}
                    className="badge inline-block px-2 py-1 bg-blue-100 text-blue-800 text-xs font-medium rounded"
                    title={`Strategy: ${strategy}`}
                  >
                    {strategy}
                  </span>
                ))}
                {alert.strategies.length > 3 && (
                  <span className="text-xs text-gray-500 px-2 py-1">
                    +{alert.strategies.length - 3} more
                  </span>
                )}
              </div>
            )}

            {/* Expandable Details Section */}
            {Object.keys(alert.metrics).length > 0 && (
              <div className="mt-3">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setExpanded(!expanded)
                  }}
                  className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                  aria-expanded={expanded}
                >
                  {expanded ? 'Hide' : 'Show'} Metrics
                </button>

                {expanded && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                      {Object.entries(alert.metrics)
                        .slice(0, 6)
                        .map(([key, value]) => (
                          <div key={key} className="text-gray-600">
                            <span className="font-medium capitalize">
                              {key.replace(/_/g, ' ')}:
                            </span>{' '}
                            <span className="text-gray-900 font-semibold">
                              {formatMetricValue(value)}
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Action Buttons */}
          {(onResolve || onDismiss) && (
            <div
              className="flex items-center gap-2 ml-4 flex-shrink-0"
              onClick={(e) => e.stopPropagation()}
            >
              {onResolve && (
                <button
                  onClick={handleResolve}
                  disabled={resolving || dismissing}
                  className="p-2 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded-lg transition-colors disabled:opacity-50"
                  title="Mark alert as resolved"
                  aria-label="Resolve alert"
                >
                  <svg
                    className={`w-5 h-5 ${resolving ? 'animate-spin' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </button>
              )}

              {onDismiss && (
                <button
                  onClick={handleDismiss}
                  disabled={resolving || dismissing}
                  className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                  title="Dismiss alert"
                  aria-label="Dismiss alert"
                >
                  <svg
                    className={`w-5 h-5 ${dismissing ? 'animate-spin' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AlertCard
