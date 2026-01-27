# API Integration Quick Reference

## Import Paths
```typescript
// API Client
import { apiClient, API_BASE_URL } from '@utils/apiClient'

// Type Definitions
import type {
  HealthResponse, ScanResponse, AlertResponse,
  ChainSnapshot, FeatureResponse, OptionContract
} from '@types/api'
import { DetectorType, StrategyType } from '@types/alert'

// Hooks - Raw API
import {
  useApi, useApiPost, useApiPut, useApiDelete,
  useHealthCheck, useLatestAlerts, useAlertsByTicker,
  useOptionChain, useFeatures, useScanStatus, useTriggerScan
} from '@hooks/useApi'

// Hooks - With Store Integration
import {
  useHealthCheckIntegration,
  useLatestAlertsIntegration,
  useAlertsByTickerIntegration,
  useOptionChainIntegration,
  useFeaturesIntegration,
  useScanStatusIntegration,
  useTriggerScanIntegration
} from '@hooks/useApiIntegration'

// State Management
import { useApiStore } from '@store/apiStore'
```

## Common Tasks

### Display Latest Alerts
```typescript
function AlertsList() {
  const { alerts, loading, error } = useLatestAlertsIntegration(50)

  if (loading) return <Spinner />
  if (error) return <Error>{error.message}</Error>
  return alerts.map(a => <AlertCard key={a.id} alert={a} />)
}
```

### Show Ticker Options Chain
```typescript
function ChainView({ ticker }: { ticker: string }) {
  const { chain, loading } = useOptionChainIntegration(ticker)

  if (loading) return <Spinner />
  return (
    <>
      <CallsTable calls={chain?.calls} />
      <PutsTable puts={chain?.puts} />
    </>
  )
}
```

### Monitor Scan Progress
```typescript
function ScanMonitor({ scanId }: { scanId: number }) {
  const { scan } = useScanStatusIntegration(scanId)
  // Auto-polls every 5 seconds

  return <Progress value={scan?.ticker_count} total={scan?.alert_count} />
}
```

### Start a Scan
```typescript
function StartScanButton() {
  const { triggerScan, loading, error } = useTriggerScanIntegration()

  return (
    <button
      onClick={async () => {
        const result = await triggerScan()
        console.log(`Scan ${result.scan_id} started`)
      }}
      disabled={loading}
    >
      {error ? 'Error' : loading ? 'Starting...' : 'Start Scan'}
    </button>
  )
}
```

### Get Data from Store
```typescript
// Access store directly (no component re-render)
const store = useApiStore.getState()
console.log(store.latestAlerts)
console.log(store.optionChains['AAPL'])

// Or use selector (causes re-render on change)
function MyComponent() {
  const alerts = useApiStore((state) => state.latestAlerts)
  const applesChain = useApiStore((state) => state.getOptionChain('AAPL'))
}
```

### Handle Errors
```typescript
function SafeComponent() {
  const { alerts, error, refetch } = useLatestAlertsIntegration()

  if (error) {
    return (
      <div>
        <p>Error: {error.message}</p>
        <button onClick={refetch}>Retry</button>
      </div>
    )
  }

  return <AlertsList alerts={alerts} />
}
```

### Poll for Updates
```typescript
// Health check (polls every 30 seconds)
const { health } = useHealthCheckIntegration()

// Scan status (polls every 5 seconds)
const { scan } = useScanStatusIntegration(scanId)

// Custom polling
const { data, refetch } = useApi('/custom', {
  interval: 10000, // 10 seconds
  immediate: true
})
```

### Refresh Data
```typescript
function RefreshableList() {
  const { alerts, refetch, loading } = useLatestAlertsIntegration()

  return (
    <>
      <button onClick={refetch} disabled={loading}>
        {loading ? 'Refreshing...' : 'Refresh'}
      </button>
      <AlertsList alerts={alerts} />
    </>
  )
}
```

## Response Types at a Glance

### HealthResponse
```typescript
{
  status: string // 'healthy', 'degraded', etc.
  timestamp: string
}
```

### AlertResponse
```typescript
{
  id: number
  ticker: string
  detector_name: string
  score: number // 0-1
  metrics: Record<string, unknown>
  explanation: Record<string, unknown>
  strategies: string[]
  created_at: string
}
```

### ChainSnapshot
```typescript
{
  ticker: string
  expiration: string
  calls: OptionContract[]
  puts: OptionContract[]
}
```

### OptionContract
```typescript
{
  strike: number
  bid: number
  ask: number
  lastPrice: number
  volume: number
  openInterest: number
  impliedVolatility: number
  delta: number
  gamma: number
  theta: number
  vega: number
  rho?: number
  expirationDate: string
}
```

### FeatureResponse
```typescript
{
  ticker: string
  timestamp: string
  price: number
  technicals: Record<string, unknown>
  volatility: Record<string, unknown>
  [key: string]: unknown
}
```

### ScanResponse
```typescript
{
  scan_id: number
  status: string
  ticker_count: number
  alert_count: number
}
```

## Hook Signatures

### useApi<T>(url, options?)
```typescript
const { data, loading, error, refetch } = useApi<T>(url, {
  immediate: boolean        // auto-fetch on mount
  interval: number         // auto-refetch interval (ms)
  dependencies: any[]      // re-fetch when deps change
  onSuccess: (data) => {} // success callback
  onError: (error) => {}   // error callback
})
```

### useApiPost<T, R>(url)
```typescript
const { execute, loading, error, data } = useApiPost<RequestType, ResponseType>(url)
const response = await execute(payload)
```

### useApiPut<T, R>(url) & useApiDelete(url)
Same as useApiPost

### Domain Hooks
All return: `{ data, loading, error, refetch }`
- `useHealthCheck()`
- `useLatestAlerts(limit?: number)`
- `useAlertsByTicker(ticker: string)`
- `useOptionChain(ticker: string)`
- `useFeatures(ticker: string)`
- `useScanStatus(scanId: number)`
- `useTriggerScan()` - returns `{ execute, loading, error, data }`

### Integration Hooks
Same returns as domain hooks but with store sync

## Detector Types
```typescript
enum DetectorType {
  LOW_IV = 'low_iv',
  RICH_PREMIUM = 'rich_premium',
  EARNINGS_CRUSH = 'earnings_crush',
  TERM_KINK = 'term_kink',
  SKEW_ANOMALY = 'skew_anomaly',
  REGIME_SHIFT = 'regime_shift'
}
```

## Strategy Types
```typescript
enum StrategyType {
  WHEEL = 'wheel',
  CSP = 'csp',
  COVERED_CALL = 'covered_call',
  BULL_CALL_SPREAD = 'bull_call_spread',
  BEAR_CALL_SPREAD = 'bear_call_spread',
  BULL_PUT_SPREAD = 'bull_put_spread',
  BEAR_PUT_SPREAD = 'bear_put_spread',
  IRON_CONDOR = 'iron_condor',
  BUTTERFLY = 'butterfly',
  STRADDLE = 'straddle',
  STRANGLE = 'strangle',
  COLLAR = 'collar'
}
```

## Store Actions

```typescript
const store = useApiStore()

// Getters
store.latestAlerts
store.optionChains['AAPL']
store.features['AAPL']
store.scans[123]

// Actions
store.setHealth(response)
store.setLatestAlerts(alerts)
store.setOptionChain(ticker, chain)
store.setFeatures(ticker, features)
store.setScan(scanId, response)

// Utilities
store.getAlertForTicker('AAPL')
store.getOptionChain('AAPL')
store.getFeatures('AAPL')
store.getScan(scanId)
store.reset()
```

## Environment Variables

**.env.local**
```
VITE_API_BASE_URL=http://localhost:8061
```

## Debugging

```typescript
// Check store state
const state = useApiStore.getState()
console.log(state)

// Enable API logging (in utils/apiClient.ts)
apiClient.interceptors.request.use(config => {
  console.log('➡️ ', config.method?.toUpperCase(), config.url)
  return config
})

apiClient.interceptors.response.use(
  response => {
    console.log('✅', response.status, response.config.url)
    return response
  },
  error => {
    console.error('❌', error.response?.status, error.config?.url)
    return Promise.reject(error)
  }
)
```

## Best Practices Checklist

- [ ] Use integration hooks in components (not raw API hooks)
- [ ] Always handle `loading` and `error` states
- [ ] Use `refetch` function for manual refresh
- [ ] Type all props and state with API types
- [ ] Use TypeScript strict mode
- [ ] Handle errors with try/catch in mutation handlers
- [ ] Document custom API hooks with JSDoc
- [ ] Keep store data normalized (by ID/ticker)
- [ ] Use `immediate: false` for non-essential data
- [ ] Set reasonable polling intervals (30s for health, 5s for status)
