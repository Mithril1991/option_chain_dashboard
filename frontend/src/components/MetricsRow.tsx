import React from 'react'

/**
 * Individual metric configuration
 */
interface Metric {
  /** Metric label/title */
  label: string
  /** Metric value (number or string) */
  value: string | number
  /** Optional: percent change indicator */
  change?: number
  /** Optional: unit suffix (e.g., "%", "$", "alerts") */
  unit?: string
  /** Optional: icon component */
  icon?: React.ReactNode
  /** Optional: click handler for interactivity */
  onClick?: () => void
  /** Optional: tooltip text */
  tooltip?: string
}

/**
 * Props for MetricsRow component
 */
interface MetricsRowProps {
  /** Array of metrics to display */
  metrics: Metric[]
  /** Optional: custom CSS class */
  className?: string
  /** Optional: number of columns on desktop (1-4, default: 3) */
  columns?: 1 | 2 | 3 | 4
  /** Optional: gap between cards */
  gap?: 'small' | 'medium' | 'large'
}

/**
 * Get grid column classes based on columns prop
 */
const getGridColsClass = (columns: number): string => {
  switch (columns) {
    case 1:
      return 'grid-cols-1'
    case 2:
      return 'md:grid-cols-2'
    case 4:
      return 'md:grid-cols-2 lg:grid-cols-4'
    case 3:
    default:
      return 'md:grid-cols-3'
  }
}

/**
 * Get gap size classes
 */
const getGapClass = (gap: string): string => {
  switch (gap) {
    case 'small':
      return 'gap-2 sm:gap-3'
    case 'large':
      return 'gap-6 sm:gap-8'
    case 'medium':
    default:
      return 'gap-4 sm:gap-6'
  }
}

/**
 * Metrics Row Component - Responsive metrics display grid
 *
 * Features:
 * - Responsive grid: 1 col mobile, 3 cols desktop (configurable)
 * - Each metric in a card with icon, label, and value
 * - Color-coded change indicator (green for positive, red for negative)
 * - Optional unit suffix (e.g., "%", "$")
 * - Customizable icon with opacity effect
 * - Hover effect with optional click handler
 * - Accessible with semantic HTML
 * - Proper typography hierarchy
 *
 * Design:
 * - Tailwind CSS card styling
 * - Responsive padding and spacing
 * - Large bold value for emphasis
 * - Subtle icon background
 * - Clean visual hierarchy
 *
 * Usage:
 * - Dashboard key metrics
 * - Portfolio summary stats
 * - Real-time trading data
 * - Alert statistics
 *
 * @component
 * @example
 * ```tsx
 * const metrics = [
 *   {
 *     label: 'Total Alerts Today',
 *     value: 42,
 *     unit: 'Alerts',
 *     icon: <BellIcon />
 *   },
 *   {
 *     label: 'Average Score',
 *     value: 75.5,
 *     unit: '%',
 *     change: 5.2,
 *     onClick: () => navigate('/alerts')
 *   },
 *   {
 *     label: 'System Health',
 *     value: 'Healthy',
 *     icon: <CheckCircleIcon />
 *   }
 * ]
 *
 * <MetricsRow metrics={metrics} columns={3} gap="medium" />
 * ```
 */
export const MetricsRow: React.FC<MetricsRowProps> = ({
  metrics,
  className = '',
  columns = 3,
  gap = 'medium'
}) => {
  /**
   * Format metric value with proper type handling
   */
  const formatValue = (value: string | number): string => {
    if (typeof value === 'number') {
      return value.toLocaleString('en-US', {
        maximumFractionDigits: 2,
        minimumFractionDigits: 0
      })
    }
    return value
  }

  /**
   * Get change text with sign
   */
  const getChangeText = (change: number): string => {
    return `${change > 0 ? '+' : ''}${change}%`
  }

  /**
   * Get change color based on value
   */
  const getChangeColor = (change: number): string => {
    if (change > 0) return 'text-green-600'
    if (change < 0) return 'text-red-600'
    return 'text-gray-600'
  }

  return (
    <div
      className={`grid grid-cols-1 ${getGridColsClass(columns)} ${getGapClass(gap)} ${className}`}
      role="region"
      aria-label="Metrics display"
    >
      {metrics.map((metric, index) => (
        <div
          key={index}
          onClick={metric.onClick}
          className={`card p-4 sm:p-6 transition-all duration-200 ${
            metric.onClick
              ? 'cursor-pointer hover:shadow-lg hover:scale-105'
              : ''
          }`}
          role="article"
          aria-label={`${metric.label}: ${metric.value}${metric.unit ? ' ' + metric.unit : ''}`}
          title={metric.tooltip}
        >
          <div className="flex items-start justify-between">
            {/* Left Content */}
            <div className="flex-1 min-w-0">
              {/* Label */}
              <p className="text-xs sm:text-sm font-medium text-gray-600 mb-2 truncate">
                {metric.label}
              </p>

              {/* Value with Unit and Change */}
              <div className="flex items-baseline gap-2 flex-wrap">
                <p className="text-2xl sm:text-3xl font-bold text-gray-900">
                  {formatValue(metric.value)}
                  {metric.unit && (
                    <span className="text-base sm:text-lg text-gray-600 ml-1 font-normal">
                      {metric.unit}
                    </span>
                  )}
                </p>

                {/* Change Indicator */}
                {metric.change !== undefined && (
                  <span
                    className={`text-xs sm:text-sm font-semibold inline-block ${getChangeColor(
                      metric.change
                    )}`}
                  >
                    {getChangeText(metric.change)}
                  </span>
                )}
              </div>
            </div>

            {/* Right Icon */}
            {metric.icon && (
              <div className="flex-shrink-0 ml-3 text-blue-600 opacity-20 text-3xl sm:text-4xl">
                {metric.icon}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export default MetricsRow
