import React, { useState, useMemo } from 'react'
import { useOptionChainIntegration, useLatestAlertsIntegration } from '@hooks/useApiIntegration'
import { useOptionExpirations } from '@hooks/useApi'
import { useUIStore } from '@store/uiStore'
import { formatRelativeTime, formatPrice, formatPercent, formatVolume } from '@utils/formatters'
import type { OptionContract } from '@types/api'

type SortField = 'strike' | 'bid' | 'ask' | 'iv' | 'delta' | 'gamma' | 'vega' | 'theta' | 'volume' | 'oi'
type SortDirection = 'asc' | 'desc'

export const OptionChains: React.FC = () => {
  const { setSelectedTicker } = useUIStore()
  const { alerts } = useLatestAlertsIntegration(50)

  // Get unique recent tickers from alerts
  const recentTickers = useMemo(() => {
    if (!alerts) return []
    const seen = new Set<string>()
    return alerts
      .map((a) => a.ticker)
      .filter((t) => {
        if (seen.has(t)) return false
        seen.add(t)
        return true
      })
      .slice(0, 10)
  }, [alerts])

  // Initialize ticker
  const defaultTicker = recentTickers[0] || 'SPY'
  const [ticker, setTicker] = useState(defaultTicker)
  const [tickerSearch, setTickerSearch] = useState('')
  const [selectedExpiration, setSelectedExpiration] = useState<string | null>(null)
  const [callsSortBy, setCallsSortBy] = useState<SortField>('strike')
  const [callsSortDir, setCallsSortDir] = useState<SortDirection>('asc')
  const [putsSortBy, setPutsSortBy] = useState<SortField>('strike')
  const [putsSortDir, setPutsSortDir] = useState<SortDirection>('asc')

  // Fetch option chain
  const { chain, loading, error, refetch } = useOptionChainIntegration(ticker)

  // Fetch available expirations for ticker
  const { data: expirationsList = [] } = useOptionExpirations(ticker)

  // Set default expiration on expirations load
  React.useEffect(() => {
    if (expirationsList && expirationsList.length > 0 && !selectedExpiration) {
      setSelectedExpiration(expirationsList[0])
    }
  }, [expirationsList, selectedExpiration])

  // Calculate DTE (Days To Expiration)
  const calculateDTE = (expirationDate: string): number => {
    const exp = new Date(expirationDate)
    const today = new Date()
    const diffTime = exp.getTime() - today.getTime()
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24))
  }

  // Determine IV color
  const getIVColor = (iv: number): string => {
    const ivPercent = iv * 100
    if (ivPercent > 50) return 'bg-red-50 text-red-700'
    if (ivPercent > 30) return 'bg-yellow-50 text-yellow-700'
    return 'bg-green-50 text-green-700'
  }

  // Sort function
  const sortContracts = (contracts: OptionContract[], sortBy: SortField, sortDir: SortDirection) => {
    return [...contracts].sort((a, b) => {
      let aVal: number
      let bVal: number

      switch (sortBy) {
        case 'strike':
          aVal = a.strike
          bVal = b.strike
          break
        case 'bid':
          aVal = a.bid
          bVal = b.bid
          break
        case 'ask':
          aVal = a.ask
          bVal = b.ask
          break
        case 'iv':
          aVal = a.impliedVolatility
          bVal = b.impliedVolatility
          break
        case 'delta':
          aVal = a.delta
          bVal = b.delta
          break
        case 'gamma':
          aVal = a.gamma
          bVal = b.gamma
          break
        case 'vega':
          aVal = a.vega
          bVal = b.vega
          break
        case 'theta':
          aVal = a.theta
          bVal = b.theta
          break
        case 'volume':
          aVal = a.volume
          bVal = b.volume
          break
        case 'oi':
          aVal = a.openInterest
          bVal = b.openInterest
          break
        default:
          return 0
      }

      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    })
  }

  // Sort calls and puts
  const sortedCalls = chain ? sortContracts(chain.calls, callsSortBy, callsSortDir) : []
  const sortedPuts = chain ? sortContracts(chain.puts, putsSortBy, putsSortDir) : []

  // Handle ticker selection
  const handleTickerSelect = (selectedTicker: string) => {
    setTicker(selectedTicker.toUpperCase())
    setTickerSearch('')
    setSelectedTicker(selectedTicker.toUpperCase())
    setSelectedExpiration(null)
  }

  // Handle ticker search
  const handleTickerSearch = (value: string) => {
    setTickerSearch(value.toUpperCase())
  }

  // Filter tickers based on search
  const filteredTickers = useMemo(() => {
    const searchQuery = tickerSearch.trim()
    if (!searchQuery) return recentTickers
    return recentTickers.filter((t) => t.includes(searchQuery))
  }, [recentTickers, tickerSearch])

  // Render skeleton loader
  const SkeletonLoader = () => (
    <div className="card p-6 mb-6">
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-8 bg-gray-200 rounded animate-pulse" />
        ))}
      </div>
    </div>
  )

  // Render table cell with tooltip for bid-ask spread
  const TableCell = ({ value }: { value: string }) => {
    return <td className="py-3 px-4 text-gray-900">{value}</td>
  }

  // Render sort button
  const SortButton = (props: { label: string; field: SortField; isCalls: boolean }) => {
    const { label, field, isCalls } = props
    const isActive = isCalls ? callsSortBy === field : putsSortBy === field
    const sortDir = isCalls ? callsSortDir : putsSortDir

    return (
      <th
        onClick={() => {
          if (isCalls) {
            if (callsSortBy === field) {
              setCallsSortDir(callsSortDir === 'asc' ? 'desc' : 'asc')
            } else {
              setCallsSortBy(field)
              setCallsSortDir('asc')
            }
          } else {
            if (putsSortBy === field) {
              setPutsSortDir(putsSortDir === 'asc' ? 'desc' : 'asc')
            } else {
              setPutsSortBy(field)
              setPutsSortDir('asc')
            }
          }
        }}
        className={`text-left py-3 px-4 text-sm font-semibold cursor-pointer transition-colors ${
          isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-700 hover:bg-gray-50'
        }`}
      >
        {label}
        {isActive && (
          <span className="ml-1">
            {sortDir === 'asc' ? '↑' : '↓'}
          </span>
        )}
      </th>
    )
  }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl md:text-4xl font-bold text-gray-900">Option Chains Explorer</h1>
        <p className="text-gray-600 mt-2">View live option chains with Greeks and implied volatility data</p>
      </div>

      {/* Selectors */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {/* Ticker Selector */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">Ticker</label>
          <div className="relative">
            <input
              type="text"
              value={tickerSearch || ticker}
              onChange={(e) => handleTickerSearch(e.target.value)}
              onFocus={() => setTickerSearch(ticker)}
              placeholder="Search or select ticker..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {tickerSearch && filteredTickers.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                {filteredTickers.map((t) => (
                  <button
                    key={t}
                    onClick={() => handleTickerSelect(t)}
                    className="w-full text-left px-4 py-2 hover:bg-blue-50 text-gray-900 transition-colors"
                  >
                    {t}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Expiration Selector */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">Expiration</label>
          <select
            value={selectedExpiration || ''}
            onChange={(e) => setSelectedExpiration(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
          >
            {expirationsList && expirationsList.length > 0 ? (
              expirationsList.map((exp: string) => (
                <option key={exp} value={exp}>
                  {exp} (DTE: {calculateDTE(exp)})
                </option>
              ))
            ) : (
              <option value="">No expirations available</option>
            )}
          </select>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800 font-semibold">Error loading option chain</p>
          <p className="text-red-700 text-sm">{error.message}</p>
          <button
            onClick={() => refetch()}
            className="mt-2 px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 text-sm"
          >
            Retry
          </button>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <>
          <SkeletonLoader />
          <SkeletonLoader />
        </>
      ) : chain ? (
        <>
          {/* Underlying Info */}
          <div className="card mb-6 p-4 md:p-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-gray-600">Ticker</p>
                <p className="text-xl md:text-2xl font-bold text-gray-900">{chain.ticker}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Price</p>
                <p className="text-xl md:text-2xl font-bold text-gray-900">${formatPrice(chain.ticker === chain.ticker ? 100 : 100)}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Data Updated</p>
                <p className="text-sm text-gray-900">{formatRelativeTime(chain.expiration)}</p>
              </div>
              <div>
                <button
                  onClick={() => refetch()}
                  disabled={loading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors text-sm font-medium"
                >
                  {loading ? 'Refreshing...' : 'Refresh'}
                </button>
              </div>
            </div>
          </div>

          {/* Calls and Puts Tables - Side by side on desktop, stacked on mobile */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Calls Table */}
            <div className="card overflow-hidden">
              <div className="p-4 md:p-6 border-b border-gray-200">
                <h3 className="text-lg font-bold text-gray-900">Calls</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs md:text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <SortButton label="Strike" field="strike" isCalls />
                      <SortButton label="Bid" field="bid" isCalls />
                      <SortButton label="Ask" field="ask" isCalls />
                      <SortButton label="IV" field="iv" isCalls />
                      <SortButton label="Δ" field="delta" isCalls />
                      <SortButton label="Γ" field="gamma" isCalls />
                      <SortButton label="V" field="vega" isCalls />
                      <SortButton label="Θ" field="theta" isCalls />
                      <SortButton label="Vol" field="volume" isCalls />
                      <SortButton label="OI" field="oi" isCalls />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {sortedCalls.slice(0, 20).map((call) => {
                      const bidAskSpread = call.ask > 0 ? ((call.ask - call.bid) / call.ask * 100).toFixed(2) : '0'
                      return (
                        <tr
                          key={call.strike}
                          className="hover:bg-gray-50 transition-colors group relative"
                          title={`Spread: ${bidAskSpread}%`}
                        >
                          <TableCell value={`$${call.strike.toFixed(2)}`} />
                          <TableCell value={`$${call.bid.toFixed(2)}`} />
                          <TableCell value={`$${call.ask.toFixed(2)}`} />
                          <td className={`py-3 px-4 font-medium ${getIVColor(call.impliedVolatility)}`}>
                            {(call.impliedVolatility * 100).toFixed(2)}%
                          </td>
                          <TableCell value={call.delta.toFixed(4)} />
                          <TableCell value={call.gamma.toFixed(4)} />
                          <TableCell value={call.vega.toFixed(4)} />
                          <TableCell value={call.theta.toFixed(4)} />
                          <TableCell value={formatVolume(call.volume)} />
                          <TableCell value={formatVolume(call.openInterest)} />
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {sortedCalls.length === 0 && (
                <div className="p-6 text-center text-gray-500">
                  <p>No calls available</p>
                </div>
              )}
            </div>

            {/* Puts Table */}
            <div className="card overflow-hidden">
              <div className="p-4 md:p-6 border-b border-gray-200">
                <h3 className="text-lg font-bold text-gray-900">Puts</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs md:text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <SortButton label="Strike" field="strike" isCalls={false} />
                      <SortButton label="Bid" field="bid" isCalls={false} />
                      <SortButton label="Ask" field="ask" isCalls={false} />
                      <SortButton label="IV" field="iv" isCalls={false} />
                      <SortButton label="Δ" field="delta" isCalls={false} />
                      <SortButton label="Γ" field="gamma" isCalls={false} />
                      <SortButton label="V" field="vega" isCalls={false} />
                      <SortButton label="Θ" field="theta" isCalls={false} />
                      <SortButton label="Vol" field="volume" isCalls={false} />
                      <SortButton label="OI" field="oi" isCalls={false} />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {sortedPuts.slice(0, 20).map((put) => {
                      const bidAskSpread = put.ask > 0 ? ((put.ask - put.bid) / put.ask * 100).toFixed(2) : '0'
                      return (
                        <tr
                          key={put.strike}
                          className="hover:bg-gray-50 transition-colors group relative"
                          title={`Spread: ${bidAskSpread}%`}
                        >
                          <TableCell value={`$${put.strike.toFixed(2)}`} />
                          <TableCell value={`$${put.bid.toFixed(2)}`} />
                          <TableCell value={`$${put.ask.toFixed(2)}`} />
                          <td className={`py-3 px-4 font-medium ${getIVColor(put.impliedVolatility)}`}>
                            {(put.impliedVolatility * 100).toFixed(2)}%
                          </td>
                          <TableCell value={put.delta.toFixed(4)} />
                          <TableCell value={put.gamma.toFixed(4)} />
                          <TableCell value={put.vega.toFixed(4)} />
                          <TableCell value={put.theta.toFixed(4)} />
                          <TableCell value={formatVolume(put.volume)} />
                          <TableCell value={formatVolume(put.openInterest)} />
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {sortedPuts.length === 0 && (
                <div className="p-6 text-center text-gray-500">
                  <p>No puts available</p>
                </div>
              )}
            </div>
          </div>
        </>
      ) : (
        <div className="card p-12 text-center">
          <p className="text-gray-500 text-lg">
            {ticker ? 'No option chains available for this ticker' : 'Select a ticker to view option chains'}
          </p>
        </div>
      )}
    </div>
  )
}

export default OptionChains
