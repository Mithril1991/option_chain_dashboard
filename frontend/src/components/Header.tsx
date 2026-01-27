import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useUIStore } from '@store/uiStore'
import { useConfigStore } from '@store/configStore'
import { formatTime } from '@utils/formatters'

/**
 * Header Component - Application top navigation bar
 *
 * Displays comprehensive app status and controls:
 * - App logo/title: "Option Chain Dashboard"
 * - Health status indicator with animated pulse (green/red)
 * - Data mode display (Demo/Production)
 * - Last scan timestamp (hidden on small screens)
 * - Settings button navigation
 * - Responsive design: collapses on mobile devices
 *
 * Layout:
 * - Left: Menu toggle + App title
 * - Right: Status indicators + Settings button
 *
 * @component
 */
export const Header: React.FC = () => {
  const navigate = useNavigate()
  const { toggleSidebar } = useUIStore()
  const { health, isHealthy, config } = useConfigStore()

  /**
   * Format ISO timestamp to readable time format
   * @param timestamp - ISO timestamp string
   * @returns Formatted time or 'Never' if null
   */
  const formatTimestamp = (timestamp: string | null): string => {
    if (!timestamp) return 'Never'
    try {
      return formatTime(timestamp)
    } catch {
      return 'N/A'
    }
  }

  /**
   * Navigate to settings page
   */
  const handleSettingsClick = () => {
    navigate('/config')
  }

  const isConnected = isHealthy()

  return (
    <header className="bg-gray-800 border-b border-gray-700 px-4 sm:px-6 py-3 sm:py-4 shadow-lg">
      <div className="flex items-center justify-between">
        {/* Left Section: Menu Toggle + Title */}
        <div className="flex items-center gap-3 sm:gap-4 min-w-0">
          {/* Menu Toggle Button */}
          <button
            onClick={toggleSidebar}
            className="flex-shrink-0 p-2 hover:bg-gray-700 rounded-lg transition-colors text-white"
            aria-label="Toggle sidebar"
            title="Toggle sidebar menu"
          >
            <svg
              className="w-5 h-5 sm:w-6 sm:h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>

          {/* App Title */}
          <div className="min-w-0">
            <h1 className="text-lg sm:text-2xl font-bold text-white truncate">
              Option Chain Dashboard
            </h1>
            <p className="text-xs text-gray-400 hidden sm:block mt-1">
              Financial analytics and options tracking
            </p>
          </div>
        </div>

        {/* Right Section: Status Indicators + Settings */}
        <div className="flex items-center gap-3 sm:gap-6 ml-4">
          {/* Health Status Indicator */}
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 sm:w-3 sm:h-3 rounded-full animate-pulse flex-shrink-0 ${
                isConnected ? 'bg-green-500' : 'bg-red-500'
              }`}
              title={isConnected ? 'Connected' : 'Disconnected'}
              aria-label={isConnected ? 'System connected' : 'System disconnected'}
            />
            <div className="hidden xs:block">
              <p className="text-xs text-gray-400">Status</p>
              <p
                className={`text-xs sm:text-sm font-medium ${
                  isConnected ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {health?.status || 'unknown'}
              </p>
            </div>
          </div>

          {/* Data Mode Indicator (Hidden on extra small) */}
          <div className="hidden sm:block">
            <p className="text-xs text-gray-400">Data Mode</p>
            <p
              className={`text-xs sm:text-sm font-medium ${
                config?.provider === 'demo' ? 'text-yellow-400' : 'text-blue-400'
              }`}
            >
              {config?.provider === 'demo' ? 'Demo' : 'Production'}
            </p>
          </div>

          {/* Last Scan Time (Hidden on small screens) */}
          <div className="hidden lg:block">
            <p className="text-xs text-gray-400">Last Scan</p>
            <p className="text-xs sm:text-sm font-medium text-gray-300">
              {formatTimestamp(config?.lastSync || null)}
            </p>
          </div>

          {/* Settings Button */}
          <button
            onClick={handleSettingsClick}
            className="flex-shrink-0 p-2 hover:bg-gray-700 rounded-lg transition-colors text-white"
            aria-label="Settings"
            title="Open configuration settings"
          >
            <svg
              className="w-5 h-5 sm:w-6 sm:h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        </div>
      </div>
    </header>
  )
}

export default Header
