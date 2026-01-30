import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useApi } from '@hooks/useApi'
import { ChainSnapshot, ThesisResponse } from '@types/api'

export const TickerDetail: React.FC = () => {
  const { symbol } = useParams<{ symbol: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'chain' | 'thesis' | 'risks' | 'notes'>('chain')

  // Fetch options chain - includes underlying price
  const { data: optionChain, loading: chainLoading, error: chainError } = useApi<ChainSnapshot>(
    symbol ? `/options/${symbol}/snapshot` : ''
  )

  // Fetch knowledge base data
  const { data: thesis, loading: thesisLoading } = useApi<ThesisResponse>(
    symbol ? `/tickers/${symbol}/thesis` : ''
  )
  const { data: risks, loading: risksLoading } = useApi<ThesisResponse>(
    symbol ? `/tickers/${symbol}/risks` : ''
  )
  const { data: notes, loading: notesLoading } = useApi<ThesisResponse>(
    symbol ? `/tickers/${symbol}/notes` : ''
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
        <div className="card bg-red-50 border border-red-200">
          <h2 className="text-lg font-semibold text-red-600">Error Loading Ticker</h2>
          <p className="text-red-500 mt-2">
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
          className="text-blue-600 hover:text-blue-500 mb-4 flex items-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back
        </button>

        {chainLoading ? (
          <div className="text-gray-600">Loading ticker data...</div>
        ) : optionChain ? (
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-4">{optionChain.ticker}</h1>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="card">
                <p className="text-gray-600 text-sm">Underlying Price</p>
                <p className="text-2xl font-bold text-gray-900 mt-2">${optionChain.underlyingPrice?.toFixed(2) || 'N/A'}</p>
              </div>
              <div className="card">
                <p className="text-gray-600 text-sm">Expiration</p>
                <p className="text-2xl font-bold text-gray-900 mt-2">{optionChain.expiration}</p>
              </div>
              <div className="card">
                <p className="text-gray-600 text-sm">Calls</p>
                <p className="text-2xl font-bold text-gray-900 mt-2">{optionChain.calls?.length || 0}</p>
              </div>
              <div className="card">
                <p className="text-gray-600 text-sm">Puts</p>
                <p className="text-2xl font-bold text-gray-900 mt-2">{optionChain.puts?.length || 0}</p>
              </div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Tab Navigation */}
      <div className="mb-6">
        <div className="flex gap-2 border-b border-gray-200">
          <button
            onClick={() => setActiveTab('chain')}
            className={`px-4 py-2 font-medium transition ${
              activeTab === 'chain'
                ? 'text-blue-600 border-b-2 border-blue-400'
                : 'text-gray-600 hover:text-gray-700'
            }`}
          >
            Options Chain
          </button>
          <button
            onClick={() => setActiveTab('thesis')}
            className={`px-4 py-2 font-medium transition flex items-center gap-2 ${
              activeTab === 'thesis'
                ? 'text-blue-600 border-b-2 border-blue-400'
                : 'text-gray-600 hover:text-gray-700'
            }`}
          >
            Investment Thesis
            {thesis && <span className="w-2 h-2 bg-green-500 rounded-full"></span>}
          </button>
          <button
            onClick={() => setActiveTab('risks')}
            className={`px-4 py-2 font-medium transition flex items-center gap-2 ${
              activeTab === 'risks'
                ? 'text-blue-600 border-b-2 border-blue-400'
                : 'text-gray-600 hover:text-gray-700'
            }`}
          >
            Risk Factors
            {risks && <span className="w-2 h-2 bg-yellow-500 rounded-full"></span>}
          </button>
          <button
            onClick={() => setActiveTab('notes')}
            className={`px-4 py-2 font-medium transition flex items-center gap-2 ${
              activeTab === 'notes'
                ? 'text-blue-600 border-b-2 border-blue-400'
                : 'text-gray-600 hover:text-gray-700'
            }`}
          >
            Notes
            {notes && <span className="w-2 h-2 bg-blue-500 rounded-full"></span>}
          </button>
        </div>
      </div>

      {/* Options Chain Tab */}
      {activeTab === 'chain' && (
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Options Chain</h2>

          {chainLoading ? (
          <div className="card">
            <p className="text-gray-600 text-center py-8">Loading options data...</p>
          </div>
        ) : optionChain ? (
          <div className="space-y-6">
            {/* Calls Table */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Call Options</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 text-gray-600 font-medium">Strike</th>
                      <th className="text-right py-3 px-4 text-gray-600 font-medium">Bid</th>
                      <th className="text-right py-3 px-4 text-gray-600 font-medium">Ask</th>
                      <th className="text-right py-3 px-4 text-gray-600 font-medium">IV</th>
                      <th className="text-right py-3 px-4 text-gray-600 font-medium">Delta</th>
                      <th className="text-right py-3 px-4 text-gray-600 font-medium">Volume</th>
                    </tr>
                  </thead>
                  <tbody>
                    {optionChain.calls && optionChain.calls.slice(0, 10).map((option, idx) => (
                      <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50 transition">
                        <td className="py-3 px-4 text-gray-900 font-medium">${option.strike.toFixed(2)}</td>
                        <td className="text-right py-3 px-4 text-gray-700">${option.bid.toFixed(3)}</td>
                        <td className="text-right py-3 px-4 text-gray-700">${option.ask.toFixed(3)}</td>
                        <td className="text-right py-3 px-4 text-gray-700">
                          {(option.impliedVolatility * 100).toFixed(1)}%
                        </td>
                        <td className="text-right py-3 px-4 text-gray-700">
                          {option.delta?.toFixed(3) || 'N/A'}
                        </td>
                        <td className="text-right py-3 px-4 text-gray-700">{option.volume || 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Puts Table */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Put Options</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-3 px-4 text-gray-600 font-medium">Strike</th>
                      <th className="text-right py-3 px-4 text-gray-600 font-medium">Bid</th>
                      <th className="text-right py-3 px-4 text-gray-600 font-medium">Ask</th>
                      <th className="text-right py-3 px-4 text-gray-600 font-medium">IV</th>
                      <th className="text-right py-3 px-4 text-gray-600 font-medium">Delta</th>
                      <th className="text-right py-3 px-4 text-gray-600 font-medium">Volume</th>
                    </tr>
                  </thead>
                  <tbody>
                    {optionChain.puts && optionChain.puts.slice(0, 10).map((option, idx) => (
                      <tr key={idx} className="border-b border-gray-200 hover:bg-gray-50 transition">
                        <td className="py-3 px-4 text-gray-900 font-medium">${option.strike.toFixed(2)}</td>
                        <td className="text-right py-3 px-4 text-gray-700">${option.bid.toFixed(3)}</td>
                        <td className="text-right py-3 px-4 text-gray-700">${option.ask.toFixed(3)}</td>
                        <td className="text-right py-3 px-4 text-gray-700">
                          {(option.impliedVolatility * 100).toFixed(1)}%
                        </td>
                        <td className="text-right py-3 px-4 text-gray-700">
                          {option.delta?.toFixed(3) || 'N/A'}
                        </td>
                        <td className="text-right py-3 px-4 text-gray-700">{option.volume || 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : (
          <div className="card">
            <p className="text-gray-600 text-center py-8">No options data available</p>
          </div>
        )}
        </div>
      )}

      {/* Investment Thesis Tab */}
      {activeTab === 'thesis' && (
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Investment Thesis</h2>
          {thesisLoading ? (
            <div className="card">
              <p className="text-gray-600 text-center py-8">Loading thesis...</p>
            </div>
          ) : thesis ? (
            <div className="card">
              <div className="prose prose-gray max-w-none">
                <pre className="whitespace-pre-wrap text-gray-700 font-sans text-sm leading-relaxed">
                  {thesis.content}
                </pre>
              </div>
              {thesis.last_updated && (
                <p className="text-gray-500 text-xs mt-4">
                  Last updated: {new Date(thesis.last_updated).toLocaleString()}
                </p>
              )}
            </div>
          ) : (
            <div className="card bg-gray-100">
              <p className="text-gray-600 text-center py-8">
                No investment thesis available for {symbol}.
              </p>
              <p className="text-gray-500 text-center text-sm">
                Create <code className="bg-gray-200 px-1 rounded">tickers/{symbol}/theses.md</code> to add one.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Risk Factors Tab */}
      {activeTab === 'risks' && (
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Risk Factors</h2>
          {risksLoading ? (
            <div className="card">
              <p className="text-gray-600 text-center py-8">Loading risks...</p>
            </div>
          ) : risks ? (
            <div className="card border border-yellow-200">
              <div className="prose prose-gray max-w-none">
                <pre className="whitespace-pre-wrap text-gray-700 font-sans text-sm leading-relaxed">
                  {risks.content}
                </pre>
              </div>
              {risks.last_updated && (
                <p className="text-gray-500 text-xs mt-4">
                  Last updated: {new Date(risks.last_updated).toLocaleString()}
                </p>
              )}
            </div>
          ) : (
            <div className="card bg-gray-100">
              <p className="text-gray-600 text-center py-8">
                No risk factors documented for {symbol}.
              </p>
              <p className="text-gray-500 text-center text-sm">
                Create <code className="bg-gray-200 px-1 rounded">tickers/{symbol}/risks.md</code> to add them.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Notes Tab */}
      {activeTab === 'notes' && (
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Trading Notes</h2>
          {notesLoading ? (
            <div className="card">
              <p className="text-gray-600 text-center py-8">Loading notes...</p>
            </div>
          ) : notes ? (
            <div className="card">
              <div className="prose prose-gray max-w-none">
                <pre className="whitespace-pre-wrap text-gray-700 font-sans text-sm leading-relaxed">
                  {notes.content}
                </pre>
              </div>
              {notes.last_updated && (
                <p className="text-gray-500 text-xs mt-4">
                  Last updated: {new Date(notes.last_updated).toLocaleString()}
                </p>
              )}
            </div>
          ) : (
            <div className="card bg-gray-100">
              <p className="text-gray-600 text-center py-8">
                No trading notes available for {symbol}.
              </p>
              <p className="text-gray-500 text-center text-sm">
                Create <code className="bg-gray-200 px-1 rounded">tickers/{symbol}/notes.md</code> to add them.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default TickerDetail
