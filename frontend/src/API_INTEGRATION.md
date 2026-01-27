# API Integration Guide

This document describes the React frontend API integration layer for the Option Chain Dashboard.

## Architecture Overview

The API integration is built in layers:

```
Components
    ↓
useApiIntegration (High-level hooks with store sync)
    ↓
useApi (Low-level domain-specific hooks)
    ↓
apiClient (Axios instance with interceptors)
    ↓
Backend API (FastAPI server)
```

## Core Components

### 1. API Client (`utils/apiClient.ts`)

**Purpose**: Axios instance with global configuration and interceptors

**Features**:
- Centralized base URL configuration via `VITE_API_BASE_URL`
- 30-second timeout
- Request/response interceptors for auth and error handling
- Automatic error handling for 401/500 status codes

**Usage**:
```typescript
import { apiClient } from '@utils/apiClient'

const response = await apiClient.get('/health')
const data = await apiClient.post('/scan/run', {})
```

### 2. Type Definitions

#### `types/api.ts`
Defines all API response types:
- `HealthResponse`: Health check status
- `ScanResponse`: Scan execution response
- `AlertResponse`: Individual alert from detector
- `ChainSnapshot`: Options chain snapshot
- `FeatureResponse`: Feature data with technicals
- Plus legacy types for backward compatibility

#### `types/alert.ts`
Alert-specific types and enums:
- `DetectorType` enum: LOW_IV, RICH_PREMIUM, EARNINGS_CRUSH, TERM_KINK, SKEW_ANOMALY, REGIME_SHIFT
- `StrategyType` enum: WHEEL, CSP, COVERED_CALL, BULL_CALL_SPREAD, etc.
- `AlertWithScore`: Alert with calculated severity
- `AlertFilter`: For filtering alerts

### 3. Low-Level Hooks (`hooks/useApi.ts`)

Generic and domain-specific hooks for individual API endpoints.

#### Generic Hooks

**`useApi<T>(url, options)`**
- GET requests with optional auto-refetch
- Returns: `{ data, loading, error, refetch }`
- Options: `immediate`, `dependencies`, `interval`, `onSuccess`, `onError`

```typescript
const { data, loading, error, refetch } = useApi<AlertResponse[]>('/alerts/latest')
```

**`useApiPost<T, R>(url)`**
- POST requests for mutations
- Returns: `{ execute, loading, error, data }`

```typescript
const { execute, loading } = useApiPost<ScanRequest, ScanResponse>('/scan/run')
await execute({ tickers: ['AAPL', 'MSFT'] })
```

**`useApiPut<T, R>(url)` and `useApiDelete(url)`**
- Similar to POST but for PUT/DELETE operations

#### Domain-Specific Hooks

Built on top of generic hooks for convenience:

**Health Check** (polls every 30 seconds)
```typescript
const { data: health, loading, error } = useHealthCheck()
```

**Latest Alerts** (with limit parameter)
```typescript
const { data: alerts, loading, error } = useLatestAlerts(50)
```

**Alerts by Ticker** (only fetches if ticker is provided)
```typescript
const { data: alerts, loading, error } = useAlertsByTicker('AAPL')
```

**Option Chain** (ticker-specific)
```typescript
const { data: chain, loading, error } = useOptionChain('AAPL')
// Returns: { ticker, expiration, calls: [], puts: [] }
```

**Features** (technical indicators)
```typescript
const { data: features, loading, error } = useFeatures('AAPL')
// Returns: { ticker, timestamp, price, technicals, volatility, ... }
```

**Scan Status** (polls every 5 seconds)
```typescript
const { data: scan, loading } = useScanStatus(scanId)
```

**Trigger Scan** (POST endpoint)
```typescript
const { execute, loading, error, data } = useTriggerScan()
await execute()
```

### 4. State Management (`store/apiStore.ts`)

Zustand store for caching API responses and managing loading/error states.

**Organized by data type**:
- Health data
- Latest alerts + alerts by ticker
- Option chains (by ticker)
- Features (by ticker)
- Scans (by ID)

**Key Methods**:

```typescript
import { useApiStore } from '@store/apiStore'

// Get store state
const health = useApiStore((state) => state.health)
const alerts = useApiStore((state) => state.latestAlerts)
const chain = useApiStore((state) => state.optionChains['AAPL'])

// Update store (usually done by integration hooks)
const { setHealth, setLatestAlerts, setOptionChain } = useApiStore()

// Utility getters
const alerts = useApiStore((state) => state.getAlertForTicker('AAPL'))
const chain = useApiStore((state) => state.getOptionChain('AAPL'))

// Reset all data
useApiStore((state) => state.reset())
```

### 5. High-Level Integration Hooks (`hooks/useApiIntegration.ts`)

Combine raw API hooks with Zustand store management for easy component integration.

**Features**:
- Automatically sync API data to store
- Manage loading/error states
- Provide refetch functions
- Type-safe returns

**Available Hooks**:
- `useHealthCheckIntegration()`
- `useLatestAlertsIntegration(limit?)`
- `useAlertsByTickerIntegration(ticker)`
- `useOptionChainIntegration(ticker)`
- `useFeaturesIntegration(ticker)`
- `useScanStatusIntegration(scanId)`
- `useTriggerScanIntegration()`

**Example Usage**:
```typescript
import { useHealthCheckIntegration, useLatestAlertsIntegration } from '@hooks/useApiIntegration'

function Dashboard() {
  const { health, loading: healthLoading } = useHealthCheckIntegration()
  const { alerts, loading: alertsLoading, refetch } = useLatestAlertsIntegration(50)

  return (
    <div>
      {healthLoading && <p>Loading health...</p>}
      {health && <p>Status: {health.status}</p>}

      {alertsLoading && <p>Loading alerts...</p>}
      <button onClick={refetch}>Refresh Alerts</button>
      {alerts.map(alert => (
        <AlertCard key={alert.id} alert={alert} />
      ))}
    </div>
  )
}
```

## Usage Patterns

### Pattern 1: Simple Data Display
```typescript
function AlertList() {
  const { alerts, loading, error } = useLatestAlertsIntegration(25)

  if (loading) return <Spinner />
  if (error) return <ErrorMessage error={error} />

  return (
    <div>
      {alerts.map(alert => (
        <AlertCard key={alert.id} alert={alert} />
      ))}
    </div>
  )
}
```

### Pattern 2: Ticker-Specific Data
```typescript
function TickerDetails({ ticker }: { ticker: string }) {
  const { chain, loading, error, refetch } = useOptionChainIntegration(ticker)
  const { features, loading: featuresLoading } = useFeaturesIntegration(ticker)

  return (
    <div>
      <button onClick={refetch}>Refresh</button>
      {loading && <Spinner />}
      {chain && <ChainViewer chain={chain} />}
      {features && <TechnicalIndicators features={features} />}
    </div>
  )
}
```

### Pattern 3: Polling Operations
```typescript
function ScanProgress({ scanId }: { scanId: number }) {
  const { scan, loading, error } = useScanStatusIntegration(scanId)

  useEffect(() => {
    // The hook already polls every 5 seconds
    // Component just displays the results
  }, [])

  if (scan?.status === 'completed') {
    return <SuccessMessage />
  }

  return <ProgressBar progress={scan?.progress} />
}
```

### Pattern 4: Mutations with Store Update
```typescript
function ScanButton() {
  const { triggerScan, loading } = useTriggerScanIntegration()
  const scans = useApiStore((state) => state.scans)

  const handleClick = async () => {
    try {
      const result = await triggerScan()
      console.log(`Scan ${result.scan_id} started`)
    } catch (err) {
      console.error('Failed to start scan', err)
    }
  }

  return <button onClick={handleClick} disabled={loading}>Start Scan</button>
}
```

## Error Handling

### API-Level Errors
```typescript
const { execute, error } = useTriggerScan()

try {
  await execute()
} catch (err) {
  console.error('Scan failed:', err.message)
}
```

### Component-Level Error Handling
```typescript
function AlertDisplay() {
  const { alerts, error } = useLatestAlertsIntegration()

  if (error) {
    return (
      <ErrorBoundary>
        <div>Failed to load alerts: {error.message}</div>
        <button onClick={refetch}>Retry</button>
      </ErrorBoundary>
    )
  }

  return <AlertList alerts={alerts} />
}
```

## Environment Configuration

Set the API base URL via environment variable:

**.env.local**:
```
VITE_API_BASE_URL=http://localhost:8061
```

**Development**: Defaults to `http://localhost:8061`
**Production**: Set via deployment configuration

## TypeScript Strict Mode

All files use TypeScript strict mode:
```typescript
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitAny": true
  }
}
```

## Adding New API Endpoints

### Step 1: Add Type Definition
```typescript
// types/api.ts
export interface NewResponse {
  id: number
  data: string
}
```

### Step 2: Create Low-Level Hook
```typescript
// hooks/useApi.ts
export const useNewEndpoint = (): UseApiState<NewResponse> & { refetch: () => Promise<void> } => {
  return useApi<NewResponse>('/new-endpoint', { immediate: true })
}
```

### Step 3: Create Integration Hook
```typescript
// hooks/useApiIntegration.ts
export const useNewEndpointIntegration = () => {
  const { setNewData, setNewError } = useApiStore()
  const api = useNewEndpoint()

  useEffect(() => {
    if (api.data) setNewData(api.data)
    if (api.error) setNewError(api.error)
  }, [api.data, api.error])

  return {
    data: useApiStore((state) => state.newData),
    loading: api.loading,
    error: api.error,
    refetch: api.refetch
  }
}
```

### Step 4: Update Store
```typescript
// store/apiStore.ts
interface ApiState {
  newData: NewResponse | null
  // ... add actions: setNewData, setNewError
}
```

## Best Practices

1. **Use integration hooks in components** - They handle store sync automatically
2. **Use raw hooks for simple cases** - When you don't need store caching
3. **Always handle loading and error states** - Show spinners and error messages
4. **Refetch on dependency changes** - Use `dependencies` array for manual control
5. **Keep stores normalized** - Store by ID/ticker to avoid duplication
6. **Type everything** - Use TypeScript strict mode
7. **Document API contracts** - Keep types in sync with backend

## Debugging

### Check Store State
```typescript
// In browser console
import { useApiStore } from '@store/apiStore'
const state = useApiStore.getState()
console.log(state)
```

### Enable API Logging
```typescript
// utils/apiClient.ts - add logging to interceptors
apiClient.interceptors.request.use((config) => {
  console.log('API Request:', config.url, config.data)
  return config
})
```

### Network Tab
Monitor actual API calls in browser DevTools Network tab:
- Check request/response headers
- Verify payload structure
- Monitor timing

## Migration from Old Patterns

If migrating from inline fetch calls:

**Before**:
```typescript
const [alerts, setAlerts] = useState([])
useEffect(() => {
  fetch('/api/alerts')
    .then(r => r.json())
    .then(setAlerts)
}, [])
```

**After**:
```typescript
const { alerts } = useLatestAlertsIntegration(50)
```

Much cleaner! The hook handles:
- Fetching
- Loading/error states
- Caching
- Auto-refetch with interval
- Store synchronization
