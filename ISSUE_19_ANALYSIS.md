# Issue #19 Analysis: ConfigStatus Page Conflicts

**Created**: 2026-01-27
**Issue**: Conflicting/non-editable configuration and status information
**Branch**: feature/issue-19-config-status-page-conflicts

---

## Problem Statement

The ConfigStatus page displays hardcoded and conflicting information instead of pulling live data from the backend API. Multiple sections use mock data or hardcoded values, creating confusion about actual system state.

---

## Root Causes Identified

### 1. **SystemStatusSection Uses Mock Config (Lines 28-68)**

**Current Behavior**:
```typescript
const SystemStatusSection: React.FC<{ config: SystemConfig }> = ({ config }) => {
  return (
    <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
      <div className="grid grid-cols-2 gap-6">
        <div>
          <p className="text-sm font-medium text-gray-600">Last Scan</p>
          <p className="text-xl font-bold text-gray-900">{formatRelativeTime(new Date(config.lastScanTime))}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-600">Next Scan</p>
          <p className="text-xl font-bold text-gray-900">{formatRelativeTime(new Date(config.nextScanTime))}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-600">Uptime</p>
          <p className="text-xl font-bold text-gray-900">{config.uptime}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-600">Current Status</p>
          <p className="text-xl font-bold text-gray-900">Idle</p>  {/* HARDCODED */}
        </div>
      </div>
    </div>
  )
}
```

**Issues**:
- Receives mock `config` object passed from main component (line 571)
- `lastScanTime` and `nextScanTime` are hardcoded offsets from now (lines 551-552)
- `uptime` is hardcoded string "7 days 14 hours" (line 553)
- `Current Status` is hardcoded as "Idle" (line 62)
- These should come from the `/health` endpoint which provides real data

**Expected Behavior**:
- Use `useHealthCheckIntegration()` hook to fetch real health data
- Display actual `last_scan_time` from health response
- Display actual `scan_status` from health response
- Show real uptime from health response

---

### 2. **DataModeSection Uses Hardcoded Fetch URL (Lines 71-212, Main Fetch at 524-542)**

**Current Behavior**:
```typescript
useEffect(() => {
  const fetchDataMode = async () => {
    try {
      const response = await fetch('http://192.168.1.16:8061/config/data-mode')
      if (response.ok) {
        const data = await response.json()
        setDataMode(data.mode === 'demo' ? 'demo' : 'production')
      }
    } catch (err) {
      logger.error(`Failed to fetch data mode: ${err instanceof Error ? err.message : 'Unknown error'}`)
      setDataMode('demo')
    } finally {
      setLoadingMode(false)
    }
  }

  fetchDataMode()
}, [])
```

**Issues**:
- Line 527: Uses hardcoded IP address `http://192.168.1.16:8061`
- Should use `apiClient` from `@utils/apiClient` instead
- Not leveraging existing error handling and retry logic from apiClient
- Creates CORS/connectivity issues if API is on different host

**Expected Behavior**:
- Use `apiClient.get('/config/data-mode')` instead
- Leverage existing apiClient error handling
- Support flexible API URL configuration

---

### 3. **ConfigurationSummarySection Shows Read-Only Mock Data (Lines 216-247)**

**Current Behavior**:
```typescript
const ConfigurationSummarySection: React.FC<{ config: SystemConfig }> = ({ config }) => {
  return (
    <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Configuration Summary</h2>
        <span className="px-3 py-1 bg-gray-200 text-gray-700 rounded-full text-xs font-medium">
          Read Only
        </span>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
          <span className="text-gray-700">Risk Free Rate</span>
          <span className="font-semibold text-gray-900">{config.riskFreeRate * 100}%</span>
        </div>
        {/* Similar for maxAlertsPerDay, alertCooldownHours, etc. */}
      </div>

      <p className="text-xs text-gray-500 text-center mt-4">
        All configuration values are read-only. Modify settings in the backend configuration files.
      </p>
    </div>
  )
}
```

**Issues**:
- Shows "Read Only" badge, implying this is definitive current config
- Displays `config` prop which is hardcoded mock data (lines 545-554)
- Doesn't fetch actual backend configuration
- Values are fixed at component render time, never updated
- Message "Modify settings in the backend" is unhelpful to users

**Expected Behavior**:
- Either fetch actual config from backend and display it, OR
- Remove this section entirely since users can't edit it anyway, OR
- Make it clear these are example values, not live config

---

### 4. **Main ConfigStatus Component Uses All Mock Data (Lines 519-586)**

**Current Behavior**:
```typescript
export const ConfigStatus: React.FC = () => {
  const [dataMode, setDataMode] = useState<'demo' | 'production'>('demo')
  const [loadingMode, setLoadingMode] = useState(true)

  // ... fetch data mode ...

  // Mock configuration data
  const mockConfig: SystemConfig = {
    riskFreeRate: 0.045,
    maxAlertsPerDay: 50,
    alertCooldownHours: 2,
    marginRequirementPercent: 25,
    maxConcentrationPercent: 5,
    lastScanTime: new Date(Date.now() - 15 * 60000).toISOString(),      // 15 min ago
    nextScanTime: new Date(Date.now() + 45 * 60000).toISOString(),      // 45 min from now
    uptime: '7 days 14 hours'
  }

  // Mock watchlist data
  const mockWatchlist: Watchlist = {
    tickers: ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN', 'META', 'NVDA', 'AMD'],
    lastUpdated: new Date().toISOString()
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <SystemStatusSection config={mockConfig} />                  {/* Passes mock data */}
      {!loadingMode && <DataModeSection mode={dataMode} />}        {/* Uses fetched data */}
      <ConfigurationSummarySection config={mockConfig} />          {/* Passes mock data */}
      <WatchlistSection watchlist={mockWatchlist} />               {/* Uses mock data */}
      <APIStatusSection />                                          {/* Uses real health data ✓ */}
    </div>
  )
}
```

**Issues**:
- Creates new mock objects on every render (wasteful)
- `mockConfig` lastScanTime/nextScanTime change every render (confusing UX)
- `mockWatchlist` hardcoded to 8 specific tickers
- Only `APIStatusSection` uses real data via `useHealthCheckIntegration()`
- Creates inconsistency: APIStatusSection shows real data, but System Status shows fake data

---

### 5. **Inconsistent Data Sources Across Page**

| Section | Data Source | Status |
|---------|---|---|
| **System Status** | Mock config (lines 545-554) | ❌ Hardcoded |
| **Data Mode** | Hardcoded fetch to 192.168.1.16:8061 | ⚠️ Hardcoded URL |
| **Configuration Summary** | Mock config | ❌ Hardcoded |
| **Watchlist** | Mock data (8 tickers hardcoded) | ❌ Hardcoded |
| **API Status** | `useHealthCheckIntegration()` | ✅ Real data |

User sees conflicting information:
- APIStatusSection says "Connected" and shows component health
- But SystemStatusSection shows fake "Last Scan" and "Next Scan" times
- And DataMode may differ from actual backend state

---

## Solution Strategy

### 1. Update SystemStatusSection to Use Health Data

```typescript
const SystemStatusSection: React.FC = () => {
  const { health, loading, error } = useHealthCheckIntegration()

  if (loading) return <div>Loading...</div>
  if (error || !health) return <div>Unable to load system status</div>

  return (
    <div className="card mb-6 p-6 border border-gray-200 rounded-lg">
      <div className="grid grid-cols-2 gap-6">
        <div>
          <p className="text-sm font-medium text-gray-600">Last Scan</p>
          <p className="text-xl font-bold text-gray-900">
            {health.last_scan_time
              ? formatRelativeTime(new Date(health.last_scan_time))
              : 'Never'}
          </p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-600">Scan Status</p>
          <p className="text-xl font-bold text-gray-900">{health.scan_status}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-600">Uptime</p>
          <p className="text-xl font-bold text-gray-900">{formatUptime(health.uptime_seconds)}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-600">API Budget (24h)</p>
          <p className="text-xl font-bold text-gray-900">{health.api_calls_today}/~2000</p>
        </div>
      </div>
    </div>
  )
}
```

**Changes**:
- Uses `useHealthCheckIntegration()` hook (no props needed)
- Displays real `last_scan_time` from health endpoint
- Shows actual `scan_status` instead of hardcoded "Idle"
- Uses `uptime_seconds` from health (converted to human-readable format)
- Shows API call budget from `api_calls_today` field

---

### 2. Fix DataModeSection to Use apiClient

```typescript
useEffect(() => {
  const fetchDataMode = async () => {
    try {
      setLoadingMode(true)
      const response = await apiClient.get('/config/data-mode')
      setDataMode(response.data.mode === 'demo' ? 'demo' : 'production')
    } catch (err) {
      logger.error(`Failed to fetch data mode: ${err instanceof Error ? err.message : 'Unknown error'}`)
      setDataMode('demo')
    } finally {
      setLoadingMode(false)
    }
  }

  fetchDataMode()
}, [])
```

**Changes**:
- Replace hardcoded fetch with `apiClient.get()`
- Leverages existing error handling and retry logic
- Supports flexible API URL configuration
- Consistent with rest of application

---

### 3. Remove or Update ConfigurationSummarySection

**Option A - Remove it entirely** (recommended):
- It serves no purpose if read-only
- Users can't interact with it
- Reduces clutter

**Option B - Show it as reference only**:
- Add note: "These are default/example values. Actual configuration in backend config files."
- Don't call it "Read Only" (confusing)
- Make styling clearly indicate it's not editable

Implementing Option A (removing the section).

---

### 4. Update Watchlist Section to Fetch Real Data

Create a hook or fetch real watchlist:

```typescript
const WatchlistSection: React.FC<{ watchlist?: Watchlist }> = ({ watchlist }) => {
  const [watches, setWatches] = useState<Watchlist | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchWatchlist = async () => {
      try {
        const response = await apiClient.get('/config/watchlist')
        setWatches(response.data)
      } catch (err) {
        logger.error('Failed to fetch watchlist')
        setWatches(null)
      } finally {
        setLoading(false)
      }
    }

    fetchWatchlist()
  }, [])

  const displayWatchlist = watches || watchlist
  // ... rest of component ...
}
```

---

### 5. Remove Mock Data From Main Component

```typescript
export const ConfigStatus: React.FC = () => {
  const [dataMode, setDataMode] = useState<'demo' | 'production'>('demo')
  const [loadingMode, setLoadingMode] = useState(true)

  // ... fetch data mode ...

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-4xl font-bold text-gray-900">Configuration & Status</h1>
      <p className="text-gray-600 mt-2">System health monitoring and configuration overview</p>

      {/* System Status Section - Now fetches its own data */}
      <SystemStatusSection />

      {/* Data Mode Section - Uses fetched data */}
      {!loadingMode && <DataModeSection mode={dataMode} />}

      {/* Watchlist Section - Fetches its own data */}
      <WatchlistSection />

      {/* API Status Section - Already works correctly */}
      <APIStatusSection />
    </div>
  )
}
```

---

## Implementation Checklist

- [ ] Update `SystemStatusSection` to use `useHealthCheckIntegration()`
- [ ] Update `DataModeSection` to use `apiClient` instead of hardcoded fetch
- [ ] Add utility function `formatUptime()` to convert seconds to "X days Y hours"
- [ ] Create new endpoint (if needed) to fetch watchlist from backend
- [ ] Update `WatchlistSection` to fetch real data
- [ ] Remove `ConfigurationSummarySection` or replace with note
- [ ] Remove mock `mockConfig` and `mockWatchlist` from main component
- [ ] Test all sections display real data
- [ ] Verify data consistency across page
- [ ] Create PR #24

---

## Expected Outcome

After fixes:
1. ✅ System Status shows **real** last scan time, scan status, uptime, API budget
2. ✅ Data Mode shows **real** current mode (fetched via apiClient)
3. ✅ Watchlist shows **real** monitored tickers (from backend)
4. ✅ API Status shows real component health (already working)
5. ✅ All data sources are consistent and live-updating
6. ✅ No hardcoded IPs or mock data visible to user
