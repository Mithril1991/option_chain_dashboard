import React, { useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { useConfigStore } from '@store/configStore'
import { useApi } from '@hooks/useApi'

import { Header } from '@components/Header'
import { Navigation } from '@components/Navigation'
import { ErrorBoundary } from '@components/ErrorBoundary'

import Dashboard from '@pages/Dashboard'
import AlertFeed from '@pages/AlertFeed'
import TickerDetail from '@pages/TickerDetail'
import OptionChains from '@pages/OptionChains'
import StrategyExplorer from '@pages/StrategyExplorer'
import ConfigStatus from '@pages/ConfigStatus'

import { HealthResponse } from '@types/api'

import '@styles/tailwind.css'
import '@styles/globals.css'

/**
 * Main App Component
 *
 * Manages:
 * - App-level routing (React Router)
 * - Layout structure (Header + Navigation + Main content)
 * - Health status polling and global state
 * - Error boundaries for error handling
 */
export const App: React.FC = () => {
  const { setHealth } = useConfigStore()
  const { data: health } = useApi<HealthResponse>('/health')

  // Update global health status when API responds
  useEffect(() => {
    if (health) {
      setHealth(health)
    }
  }, [health, setHealth])

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-gray-900">
        {/* Sidebar Navigation */}
        <Navigation />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header with Health Status and Controls */}
          <Header />

          {/* Page Content */}
          <main className="flex-1 overflow-auto bg-gray-900">
            <Routes>
              {/* Dashboard - Main landing page */}
              <Route path="/" element={<Dashboard />} />

              {/* Alert Feed - View all market alerts */}
              <Route path="/alerts" element={<AlertFeed />} />

              {/* Ticker Detail - View single ticker options chain */}
              <Route path="/ticker/:symbol" element={<TickerDetail />} />

              {/* Option Chains - Browse all option chains */}
              <Route path="/options" element={<OptionChains />} />

              {/* Strategy Explorer - Multi-leg strategies */}
              <Route path="/strategies" element={<StrategyExplorer />} />

              {/* Configuration - System settings and status */}
              <Route path="/config" element={<ConfigStatus />} />

              {/* Catch-all route */}
              <Route path="*" element={<Dashboard />} />
            </Routes>
          </main>
        </div>
      </div>
    </ErrorBoundary>
  )
}

export default App
