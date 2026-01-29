import React, { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useApi } from '@hooks/useApi'
import { ChainSnapshot } from '@types/api'

export const TickerDetail: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()

  // Fetch options chain - includes underlying price
  const { data: optionChain, loading: chainLoading, error: chainError } = useApi<ChainSnapshot>(
    symbol ? `/options/${symbol}/snapshot` : ''
  )

  useEffect(() => {
    if (!symbol) {
      navigate('/')
    }
  }, [symbol, navigate])

  if (!symbol) {
    return null
  }

  if (chainError) {
    return (
      <div className="p-6">
        <div className="card bg-red-900/20 border-red-700">
          <h2 className="text-lg font-semibold text-red-400">Error Loading Ticker</h2>
          <p className="text-red-300 mt-2">
            {chainError instanceof Error ? chainError.message : String(chainError)}
          </p>
          <button
            onClick={() => navigate('/')}
            className="btn-primary mt-4"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate('/')}
          className="text-blue-400 hover:text-blue-300 mb-4 flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>

        {chainLoading ? (
          <div className="text-gray-400">Loading ticker data...</div>
        ) : optionChain ? (
          <div>
            <h1 className="text-4xl font-bold text-white mb-4">{optionChain.ticker}</h1>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="card">
                <p className="text-gray-400 text-sm">Underlying Price</p>
                <p className="text-2xl font-bold text-white mt-2">${optionChain.underlyingPrice?.toFixed(2) || 'N/A'}</p>
              </div>
              <div className="card">
                <p className="text-gray-400 text-sm">Expiration</p>
                <p className="text-2xl font-bold text-white mt-2">{optionChain.expiration}</p>
              </div>
              <div className="card">
                <p className="text-gray-400 text-sm">Calls</p>
                <p className="text-2xl font-bold text-white mt-2">{optionChain.calls?.length || 0}</p>
              </div>
              <div className="card">
                <p className="text-gray-400 text-sm">Puts</p>
                <p className="text-2xl font-bold text-white mt-2">{optionChain.puts?.length || 0}</p>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Options Chain */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-6">Options Chain</h2>

        {chainLoading ? (
          <div className="card">
            <p className="text-gray-400 text-center py-8">Loading options data...</p>
          </div>
        ) : optionChain ? (
          <div className="space-y-6">
            {/* Calls Table */}
            <div>
              <h3 className="text-lg font-semibold text-white mb-4">Call Options</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left py-3 px-4 text-gray-400 font-medium">Strike</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-medium">Bid</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-medium">Ask</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-medium">IV</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-medium">Delta</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-medium">Volume</th>
                    </tr>
                  </thead>
                  <tbody>
                    {optionChain.calls && optionChain.calls.slice(0, 10).map((option, idx) => (
                      <tr key={idx} className="border-b border-gray-800 hover:bg-gray-800/50 transition">
                        <td className="py-3 px-4 text-white font-medium">${option.strike.toFixed(2)}</td>
                        <td className="text-right py-3 px-4 text-gray-300">${option.bid.toFixed(3)}</td>
                        <td className="text-right py-3 px-4 text-gray-300">${option.ask.toFixed(3)}</td>
                        <td className="text-right py-3 px-4 text-gray-300">
                          {(option.impliedVolatility * 100).toFixed(1)}%
                        </td>
                        <td className="text-right py-3 px-4 text-gray-300">
                          {option.delta?.toFixed(3) || 'N/A'}
                        </td>
                        <td className="text-right py-3 px-4 text-gray-300">{option.volume || 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Puts Table */}
            <div>
              <h3 className="text-lg font-semibold text-white mb-4">Put Options</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left py-3 px-4 text-gray-400 font-medium">Strike</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-medium">Bid</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-medium">Ask</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-medium">IV</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-medium">Delta</th>
                      <th className="text-right py-3 px-4 text-gray-400 font-medium">Volume</th>
                    </tr>
                  </thead>
                  <tbody>
                    {optionChain.puts && optionChain.puts.slice(0, 10).map((option, idx) => (
                      <tr key={idx} className="border-b border-gray-800 hover:bg-gray-800/50 transition">
                        <td className="py-3 px-4 text-white font-medium">${option.strike.toFixed(2)}</td>
                        <td className="text-right py-3 px-4 text-gray-300">${option.bid.toFixed(3)}</td>
                        <td className="text-right py-3 px-4 text-gray-300">${option.ask.toFixed(3)}</td>
                        <td className="text-right py-3 px-4 text-gray-300">
                          {(option.impliedVolatility * 100).toFixed(1)}%
                        </td>
                        <td className="text-right py-3 px-4 text-gray-300">
                          {option.delta?.toFixed(3) || 'N/A'}
                        </td>
                        <td className="text-right py-3 px-4 text-gray-300">{option.volume || 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : (
          <div className="card">
            <p className="text-gray-400 text-center py-8">No options data available</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default TickerDetail
