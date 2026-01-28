import React, { useState } from 'react'

// Strategy data types
interface StrategyLeg {
  name: string
  action: 'BUY' | 'SELL'
  type: 'CALL' | 'PUT' | 'STOCK'
  strikeOffset?: number // relative to entry price
}

interface StrategyData {
  id: string
  name: string
  riskProfile: 'defined' | 'undefined'
  description: string
  fullDescription: string
  maxProfit: string | null
  maxLoss: string | null
  breakeven: string[]
  idealConditions: string[]
  marketSentiment: 'bullish' | 'neutral' | 'bearish'
  relatedDetectors: string[]
  legs: StrategyLeg[]
  pnlChart: { x: number; profit: number }[] // Price moves relative to entry
}

// Hardcoded strategy database
const STRATEGIES: StrategyData[] = [
  {
    id: 'wheel',
    name: 'Wheel',
    riskProfile: 'defined',
    description: 'Sell cash-secured puts, get assigned stock, sell covered calls, repeat.',
    fullDescription: 'The Wheel is an income-generating strategy combining selling puts (getting assigned stock), then selling calls against the stock. Ideal for generating returns on capital while accumulating shares of quality companies.',
    maxProfit: 'Call strike + premium from puts + premium from calls',
    maxLoss: 'Put strike (if stock falls significantly)',
    breakeven: ['Put strike - total premium received', 'Stock price at assignment'],
    idealConditions: [
      'Stocks you want to own long-term',
      'Consistent monthly income generation',
      'Support level holds above put strike'
    ],
    marketSentiment: 'bullish',
    relatedDetectors: ['IV Spike', 'Unusual Volume', 'Support Bounce'],
    legs: [
      { name: 'Sell Put', action: 'SELL', type: 'PUT', strikeOffset: -5 },
      { name: 'Sell Call', action: 'SELL', type: 'CALL', strikeOffset: 5 }
    ],
    pnlChart: [
      { x: -20, profit: -2000 },
      { x: -10, profit: -1000 },
      { x: 0, profit: 300 },
      { x: 10, profit: 300 },
      { x: 20, profit: 300 }
    ]
  },
  {
    id: 'cash-secured-put',
    name: 'Cash-Secured Put',
    riskProfile: 'defined',
    description: 'Sell put option with cash reserved to buy stock if assigned.',
    fullDescription: 'A conservative income strategy where you sell an out-of-the-money put and keep cash available to purchase the stock if assigned. This generates immediate income while potentially accumulating shares at a discount.',
    maxProfit: 'Premium collected from selling the put',
    maxLoss: 'Put strike price minus premium received (if stock falls below strike)',
    breakeven: ['Put strike - premium received'],
    idealConditions: [
      'Strong conviction on stock direction',
      'Willing to own stock at strike price',
      'Adequate cash reserves available'
    ],
    marketSentiment: 'bullish',
    relatedDetectors: ['Oversold Signal', 'Support Bounce'],
    legs: [
      { name: 'Sell Put', action: 'SELL', type: 'PUT', strikeOffset: -5 }
    ],
    pnlChart: [
      { x: -15, profit: -1500 },
      { x: -5, profit: -500 },
      { x: 0, profit: 200 },
      { x: 10, profit: 200 },
      { x: 20, profit: 200 }
    ]
  },
  {
    id: 'covered-call',
    name: 'Covered Call',
    riskProfile: 'defined',
    description: 'Own stock, sell call to generate income while capping upside.',
    fullDescription: 'A classic income strategy: you own the underlying stock and sell call options against it. This generates income immediately but caps your profit if the stock rises above the strike price.',
    maxProfit: 'Call strike + premium received - stock cost basis',
    maxLoss: 'Stock cost basis - premium received (unlimited downside)',
    breakeven: ['Stock cost - premium received'],
    idealConditions: [
      'Own quality stock you want to keep',
      'Willing to sell if stock rallies',
      'Generate income on existing holdings'
    ],
    marketSentiment: 'neutral',
    relatedDetectors: ['Resistance Touch', 'Overbought Signal'],
    legs: [
      { name: 'Buy Stock', action: 'BUY', type: 'STOCK', strikeOffset: 0 },
      { name: 'Sell Call', action: 'SELL', type: 'CALL', strikeOffset: 5 }
    ],
    pnlChart: [
      { x: -20, profit: -2000 },
      { x: -10, profit: -1000 },
      { x: 0, profit: 0 },
      { x: 10, profit: 500 },
      { x: 20, profit: 500 }
    ]
  },
  {
    id: 'bull-call-spread',
    name: 'Bull Call Spread',
    riskProfile: 'defined',
    description: 'Buy lower call, sell higher call. Limited profit, limited risk.',
    fullDescription: 'A bullish directional strategy that reduces cost by selling a higher strike call to finance buying a lower strike call. Profit is capped but risk is limited to the net debit paid.',
    maxProfit: 'Difference between strikes - net premium paid',
    maxLoss: 'Net premium paid for the spread',
    breakeven: ['Lower strike + net premium paid'],
    idealConditions: [
      'Moderately bullish short-term outlook',
      'Want to limit capital risk',
      'Support level likely to hold'
    ],
    marketSentiment: 'bullish',
    relatedDetectors: ['Breakout Pattern', 'Volume Surge'],
    legs: [
      { name: 'Buy Call', action: 'BUY', type: 'CALL', strikeOffset: -2 },
      { name: 'Sell Call', action: 'SELL', type: 'CALL', strikeOffset: 3 }
    ],
    pnlChart: [
      { x: -10, profit: -200 },
      { x: -5, profit: -200 },
      { x: 0, profit: -100 },
      { x: 5, profit: 200 },
      { x: 10, profit: 500 }
    ]
  },
  {
    id: 'bear-put-spread',
    name: 'Bear Put Spread',
    riskProfile: 'defined',
    description: 'Sell higher put, buy lower put. Benefits from stable or rising price.',
    fullDescription: 'A bearish income strategy that sells a put and buys a lower strike put for protection. Maximum profit equals the net premium collected, and maximum loss is limited to the difference between strikes.',
    maxProfit: 'Net premium collected',
    maxLoss: 'Difference between strikes - net premium received',
    breakeven: ['Higher strike - net premium received'],
    idealConditions: [
      'Neutral to bullish short-term',
      'Expect stock to stay above higher strike',
      'Volatility is elevated'
    ],
    marketSentiment: 'neutral',
    relatedDetectors: ['Resistance Bounce', 'IV Contraction'],
    legs: [
      { name: 'Sell Put', action: 'SELL', type: 'PUT', strikeOffset: -3 },
      { name: 'Buy Put', action: 'BUY', type: 'PUT', strikeOffset: -6 }
    ],
    pnlChart: [
      { x: -15, profit: -300 },
      { x: -8, profit: -300 },
      { x: -3, profit: 200 },
      { x: 5, profit: 200 },
      { x: 15, profit: 200 }
    ]
  },
  {
    id: 'iron-condor',
    name: 'Iron Condor',
    riskProfile: 'defined',
    description: 'Sell call spread + sell put spread. Profits from price stability.',
    fullDescription: 'An advanced income strategy combining bull call spread with bear put spread. Benefits when underlying stays within a range. Maximum profit is limited to total net premium received.',
    maxProfit: 'Net premium collected from both spreads',
    maxLoss: 'Limited to wider leg of either spread',
    breakeven: ['Lower call strike - premium, Higher put strike + premium'],
    idealConditions: [
      'Expect consolidation in price range',
      'Low volatility environment',
      'Support and resistance clearly defined'
    ],
    marketSentiment: 'neutral',
    relatedDetectors: ['Consolidation Pattern', 'IV Drop'],
    legs: [
      { name: 'Sell Call', action: 'SELL', type: 'CALL', strikeOffset: 5 },
      { name: 'Buy Call', action: 'BUY', type: 'CALL', strikeOffset: 8 },
      { name: 'Sell Put', action: 'SELL', type: 'PUT', strikeOffset: -5 },
      { name: 'Buy Put', action: 'BUY', type: 'PUT', strikeOffset: -8 }
    ],
    pnlChart: [
      { x: -15, profit: -300 },
      { x: -8, profit: 200 },
      { x: 0, profit: 300 },
      { x: 8, profit: 200 },
      { x: 15, profit: -300 }
    ]
  },
  {
    id: 'long-straddle',
    name: 'Long Straddle',
    riskProfile: 'undefined',
    description: 'Buy call + buy put at same strike. Profit from large moves.',
    fullDescription: 'A volatility play where you buy both a call and put at the same strike. Profits when the stock moves significantly in either direction, making it ideal for earnings or event-driven moves.',
    maxProfit: null,
    maxLoss: 'Total premium paid for both options',
    breakeven: ['Strike + total premium', 'Strike - total premium'],
    idealConditions: [
      'Expecting large price move soon',
      'Before earnings or major events',
      'Volatility is currently low'
    ],
    marketSentiment: 'neutral',
    relatedDetectors: ['Earnings Announcement', 'Low IV'],
    legs: [
      { name: 'Buy Call', action: 'BUY', type: 'CALL', strikeOffset: 0 },
      { name: 'Buy Put', action: 'BUY', type: 'PUT', strikeOffset: 0 }
    ],
    pnlChart: [
      { x: -20, profit: 800 },
      { x: -10, profit: 200 },
      { x: 0, profit: -300 },
      { x: 10, profit: 200 },
      { x: 20, profit: 800 }
    ]
  },
  {
    id: 'calendar-spread',
    name: 'Calendar Spread',
    riskProfile: 'defined',
    description: 'Sell near-term option, buy longer-term option same strike.',
    fullDescription: 'A time decay play where you sell a near-term option and buy a longer-term option at the same strike. Profits from time decay if the stock stays near the strike. Great for high volatility environments.',
    maxProfit: 'Limited to net credit + longer-term option value at expiration',
    maxLoss: 'Limited, typically the net debit paid if directionally wrong',
    breakeven: ['Strike +/- net premium paid'],
    idealConditions: [
      'Expecting price stability near strike',
      'High implied volatility for time decay',
      'Multiple expirations available'
    ],
    marketSentiment: 'neutral',
    relatedDetectors: ['IV Spike', 'Range Bound'],
    legs: [
      { name: 'Sell Short-term Call', action: 'SELL', type: 'CALL', strikeOffset: 0 },
      { name: 'Buy Long-term Call', action: 'BUY', type: 'CALL', strikeOffset: 0 }
    ],
    pnlChart: [
      { x: -10, profit: -150 },
      { x: -5, profit: 100 },
      { x: 0, profit: 250 },
      { x: 5, profit: 100 },
      { x: 10, profit: -150 }
    ]
  },
  {
    id: 'vertical-spread',
    name: 'Vertical Spread',
    riskProfile: 'defined',
    description: 'Buy and sell same type at different strikes. Directional play.',
    fullDescription: 'A directional strategy where you buy and sell the same type of option (call or put) at different strikes. Reduces cost and limits risk but also caps profit.',
    maxProfit: 'Difference between strikes - net premium paid',
    maxLoss: 'Net premium paid (for debit spread)',
    breakeven: ['Lower strike + net premium paid (for call spread)'],
    idealConditions: [
      'Clear directional bias',
      'Want to reduce cost basis',
      'Limited capital available'
    ],
    marketSentiment: 'bullish',
    relatedDetectors: ['Support Bounce', 'Trend Continuation'],
    legs: [
      { name: 'Buy Call/Put', action: 'BUY', type: 'CALL', strikeOffset: -2 },
      { name: 'Sell Call/Put', action: 'SELL', type: 'CALL', strikeOffset: 3 }
    ],
    pnlChart: [
      { x: -8, profit: -300 },
      { x: -4, profit: -200 },
      { x: 0, profit: -100 },
      { x: 4, profit: 200 },
      { x: 8, profit: 500 }
    ]
  },
  {
    id: 'collar',
    name: 'Collar',
    riskProfile: 'defined',
    description: 'Own stock, buy protective put, sell call. Downside protection.',
    fullDescription: 'A defensive strategy that protects stock holdings by buying a put (downside protection) while selling a call (upside capped). Ideal for reducing risk on appreciated positions.',
    maxProfit: 'Call strike - put strike + net credit',
    maxLoss: 'Stock price - put strike + net cost',
    breakeven: ['Stock cost +/- net credit/debit'],
    idealConditions: [
      'Protect gains on appreciated stock',
      'Expect minor upside, significant downside risk',
      'Want to keep stock ownership'
    ],
    marketSentiment: 'neutral',
    relatedDetectors: ['Overbought Signal', 'Resistance Bounce'],
    legs: [
      { name: 'Buy Stock', action: 'BUY', type: 'STOCK', strikeOffset: 0 },
      { name: 'Buy Put', action: 'BUY', type: 'PUT', strikeOffset: -10 },
      { name: 'Sell Call', action: 'SELL', type: 'CALL', strikeOffset: 10 }
    ],
    pnlChart: [
      { x: -20, profit: -1000 },
      { x: -10, profit: -1000 },
      { x: 0, profit: -100 },
      { x: 10, profit: 500 },
      { x: 20, profit: 500 }
    ]
  }
]

interface StrategyCardProps {
  strategy: StrategyData
  isSelected: boolean
  onClick: () => void
}

// Strategy Card Component
const StrategyCard: React.FC<StrategyCardProps> = ({ strategy, isSelected, onClick }) => {
  const riskColor =
    strategy.riskProfile === 'defined'
      ? 'bg-green-100 text-green-800'
      : 'bg-red-100 text-red-800'

  const sentimentEmoji = {
    bullish: '📈',
    neutral: '↔️',
    bearish: '📉'
  }[strategy.marketSentiment]

  return (
    <div
      onClick={onClick}
      className={`card cursor-pointer transition-all transform hover:shadow-lg hover:-translate-y-1 ${
        isSelected
          ? 'ring-2 ring-blue-500 shadow-lg'
          : 'hover:border-gray-300'
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <h3 className="text-lg font-semibold text-gray-900">{strategy.name}</h3>
        <span className={`badge ${riskColor} px-2.5 py-0.5 text-xs font-medium rounded-full`}>
          {strategy.riskProfile === 'defined' ? '✓ Limited Risk' : '∞ Unlimited Risk'}
        </span>
      </div>

      <p className="text-sm text-gray-600 mb-4">{strategy.description}</p>

      <div className="flex items-center justify-between">
        <span className="text-2xl">{sentimentEmoji}</span>
        <button
          onClick={(e) => {
            e.stopPropagation()
            onClick()
          }}
          className="px-3 py-1.5 bg-blue-50 text-blue-600 text-sm font-medium rounded-lg hover:bg-blue-100 transition-colors"
        >
          View Details
        </button>
      </div>
    </div>
  )
}

// Simple Line Chart Component
interface LineChartProps {
  data: { x: number; profit: number }[]
  title: string
}

const LineChart: React.FC<LineChartProps> = ({ data, title }) => {
  const minProfit = Math.min(...data.map((d) => d.profit))
  const maxProfit = Math.max(...data.map((d) => d.profit))
  const minPrice = Math.min(...data.map((d) => d.x))
  const maxPrice = Math.max(...data.map((d) => d.x))
  const range = maxProfit - minProfit
  const padding = range * 0.2

  const height = 240
  const width = 350
  const chartHeight = height - 80
  const chartWidth = width - 80

  const points = data.map((d, i) => {
    const x = ((d.x - minPrice) / (maxPrice - minPrice)) * chartWidth + 50
    const y =
      height -
      50 -
      ((d.profit - minProfit + padding) / (range + padding * 2)) * chartHeight
    return `${x},${y}`
  })

  const pathData = points.join(' L ')

  // Calculate Y-axis labels (P/L values)
  const yLabelCount = 4
  const yLabels = []
  for (let i = 0; i < yLabelCount; i++) {
    const value = minProfit + (range / (yLabelCount - 1)) * i
    yLabels.push(value)
  }

  // Calculate X-axis labels (price moves)
  const xLabels = [-20, -10, 0, 10, 20].filter(
    (x) => x >= minPrice && x <= maxPrice
  )
  if (xLabels.length < 2) {
    // Fallback if data doesn't include these values
    for (let i = 0; i < 3; i++) {
      const value = minPrice + (maxPrice - minPrice) / 2 * i
      if (!xLabels.includes(value)) xLabels.push(Math.round(value))
    }
  }

  return (
    <div className="bg-gray-50 p-4 rounded-lg">
      <p className="text-sm font-medium text-gray-700 mb-3">{title}</p>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto"
        style={{ maxHeight: '260px' }}
      >
        {/* Grid lines */}
        <line x1="50" y1="30" x2="50" y2={height - 50} stroke="#e5e7eb" />
        <line x1="50" y1={height - 50} x2={width - 20} y2={height - 50} stroke="#e5e7eb" />

        {/* Y-axis label (P/L) */}
        <text x="15" y="35" fontSize="12" fill="#6b7280" fontWeight="600">
          P/L ($)
        </text>

        {/* Y-axis value labels */}
        {yLabels.map((value, i) => {
          const y =
            height -
            50 -
            ((value - minProfit + padding) / (range + padding * 2)) *
              chartHeight
          return (
            <g key={`y-${i}`}>
              <text
                x="45"
                y={y + 4}
                fontSize="10"
                fill="#9ca3af"
                textAnchor="end"
              >
                {Math.round(value)}
              </text>
              <line
                x1="48"
                y1={y}
                x2="50"
                y2={y}
                stroke="#d1d5db"
                strokeWidth="1"
              />
            </g>
          )
        })}

        {/* X-axis label (Price Move) */}
        <text x={width - 15} y={height - 15} fontSize="12" fill="#6b7280" fontWeight="600">
          Price ($)
        </text>

        {/* X-axis value labels */}
        {xLabels.map((value, i) => {
          const x = ((value - minPrice) / (maxPrice - minPrice)) * chartWidth + 50
          return (
            <g key={`x-${i}`}>
              <text
                x={x}
                y={height - 35}
                fontSize="10"
                fill="#9ca3af"
                textAnchor="middle"
              >
                {value >= 0 ? '+' : ''}{value}
              </text>
              <line
                x1={x}
                y1={height - 50}
                x2={x}
                y2={height - 48}
                stroke="#d1d5db"
                strokeWidth="1"
              />
            </g>
          )
        })}

        {/* Zero line */}
        {minProfit < 0 && maxProfit > 0 && (
          <line
            x1="50"
            y1={height - 50 - ((0 - minProfit + padding) / (range + padding * 2)) * chartHeight}
            x2={width - 20}
            y2={height - 50 - ((0 - minProfit + padding) / (range + padding * 2)) * chartHeight}
            stroke="#d1d5db"
            strokeDasharray="4"
          />
        )}

        {/* Line */}
        <polyline
          points={pathData}
          fill="none"
          stroke="#3b82f6"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Points */}
        {points.map((point, i) => {
          const [x, y] = point.split(',').map(Number)
          const profit = data[i].profit
          const isPositive = profit >= 0

          return (
            <g key={i}>
              <circle
                cx={x}
                cy={y}
                r="3"
                fill={isPositive ? '#10b981' : '#ef4444'}
              />
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export const StrategyExplorer: React.FC = () => {
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyData | null>(null)

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">Strategy Explorer</h1>
        <p className="text-lg text-gray-600">
          Learn how to build and execute multi-leg option strategies for different market conditions.
        </p>
      </div>

      {/* Main Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Strategy Cards */}
        <div className="lg:col-span-1">
          <div className="sticky top-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Common Strategies</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-4">
              {STRATEGIES.map((strategy) => (
                <StrategyCard
                  key={strategy.id}
                  strategy={strategy}
                  isSelected={selectedStrategy?.id === strategy.id}
                  onClick={() => setSelectedStrategy(strategy)}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Middle + Right: Strategy Details */}
        <div className="lg:col-span-2">
          {selectedStrategy ? (
            <div className="space-y-6">
              {/* Header Section */}
              <div className="card">
                <div className="mb-4">
                  <h2 className="text-3xl font-bold text-gray-900 mb-2">
                    {selectedStrategy.name}
                  </h2>
                  <p className="text-gray-600">{selectedStrategy.fullDescription}</p>
                </div>

                {/* Risk Profile Section */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6 pt-6 border-t border-gray-200">
                  {selectedStrategy.maxProfit && (
                    <div>
                      <p className="text-sm font-medium text-gray-500 mb-1">Max Profit</p>
                      <p className="text-lg font-semibold text-green-600">
                        {selectedStrategy.maxProfit}
                      </p>
                    </div>
                  )}
                  {selectedStrategy.maxLoss && (
                    <div>
                      <p className="text-sm font-medium text-gray-500 mb-1">Max Loss</p>
                      <p className="text-lg font-semibold text-red-600">
                        {selectedStrategy.maxLoss}
                      </p>
                    </div>
                  )}
                  <div>
                    <p className="text-sm font-medium text-gray-500 mb-1">Risk Profile</p>
                    <p className="text-lg font-semibold">
                      {selectedStrategy.riskProfile === 'defined' ? (
                        <span className="text-green-600">✓ Limited</span>
                      ) : (
                        <span className="text-red-600">∞ Unlimited</span>
                      )}
                    </p>
                  </div>
                </div>

                {/* Breakeven Points */}
                {selectedStrategy.breakeven.length > 0 && (
                  <div className="mt-6 pt-6 border-t border-gray-200">
                    <p className="text-sm font-medium text-gray-700 mb-2">Breakeven Points</p>
                    <div className="flex flex-wrap gap-2">
                      {selectedStrategy.breakeven.map((point, i) => (
                        <span
                          key={i}
                          className="inline-block bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm"
                        >
                          {point}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* P&L Chart */}
              <div className="card">
                <LineChart
                  data={selectedStrategy.pnlChart}
                  title="Potential Profit/Loss Profile"
                />
              </div>

              {/* Ideal Conditions & When to Use */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="card">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Ideal Conditions</h3>
                  <ul className="space-y-3">
                    {selectedStrategy.idealConditions.map((condition, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <span className="text-green-500 mt-1">✓</span>
                        <span className="text-gray-600">{condition}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="card">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Market Sentiment</h3>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
                      <span className="text-2xl">
                        {selectedStrategy.marketSentiment === 'bullish'
                          ? '📈'
                          : selectedStrategy.marketSentiment === 'bearish'
                          ? '📉'
                          : '↔️'}
                      </span>
                      <div>
                        <p className="font-medium text-gray-900">
                          {selectedStrategy.marketSentiment.charAt(0).toUpperCase() +
                            selectedStrategy.marketSentiment.slice(1)}
                        </p>
                        <p className="text-sm text-gray-600">Market outlook for this strategy</p>
                      </div>
                    </div>

                    {selectedStrategy.relatedDetectors.length > 0 && (
                      <div className="mt-4">
                        <p className="text-sm font-medium text-gray-700 mb-2">Related Alerts</p>
                        <div className="flex flex-wrap gap-2">
                          {selectedStrategy.relatedDetectors.map((detector, i) => (
                            <span
                              key={i}
                              className="inline-block bg-orange-50 text-orange-700 px-2.5 py-1 rounded text-xs font-medium"
                            >
                              {detector}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Strategy Legs */}
              <div className="card">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Strategy Legs</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {selectedStrategy.legs.map((leg, i) => (
                    <div key={i} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <p className="font-medium text-gray-900">{leg.name}</p>
                        <span
                          className={`badge px-2.5 py-0.5 text-xs font-medium rounded ${
                            leg.action === 'BUY'
                              ? 'bg-green-100 text-green-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {leg.action}
                        </span>
                      </div>
                      <div className="text-sm text-gray-600 space-y-1">
                        <div>
                          <span className="text-gray-500">Type:</span> {leg.type}
                        </div>
                        {leg.strikeOffset !== undefined && (
                          <div>
                            <span className="text-gray-500">Strike:</span> Entry{' '}
                            {leg.strikeOffset > 0 ? '+' : ''}{leg.strikeOffset}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Educational Note */}
              <div className="card bg-blue-50 border border-blue-200">
                <div className="flex gap-3">
                  <span className="text-2xl">💡</span>
                  <div>
                    <p className="font-semibold text-blue-900 mb-1">Educational Content</p>
                    <p className="text-sm text-blue-800">
                      This strategy explorer provides educational information. Always research thoroughly and
                      consult with a financial advisor before trading options. Past performance does not guarantee
                      future results.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="card flex flex-col items-center justify-center py-12">
              <svg
                className="w-16 h-16 text-gray-400 mb-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="text-lg font-medium text-gray-700 mb-2">Select a Strategy</p>
              <p className="text-gray-500 text-center max-w-sm">
                Click on any strategy card to view detailed information about its structure, profit/loss profile,
                and when to use it.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StrategyExplorer
