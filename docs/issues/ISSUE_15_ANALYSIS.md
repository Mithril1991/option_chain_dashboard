# Issue #15 Analysis: Dashboard Main Panel Issues

**Issue**: Dashboard main panel: alerts timeout, health mismatch, scan button no-op

**Branch**: feature/issue-15-dashboard-alerts-timeout

**Status**: Analyzing

---

## Problem Overview

The dashboard exhibits 4 distinct but related problems:

1. **Alerts timeout (3000ms)** - Despite 30s axios timeout, alerts fail to load with "timeout of 3000ms exceeded"
2. **Health mismatch** - Health indicator shows different status than actual API connectivity
3. **Mode badges disagree** - Header shows "Production" while System Status shows "Demo" on same page
4. **Scan button no-op** - "Trigger New Scan" button sends request but gives no user feedback

All problems stem from incorrect/missing API integrations and insufficient health/status endpoint design.

---

## Root Cause Analysis

### Issue 1: Alerts Timeout (3000ms)

**File**: `frontend/src/utils/apiClient.ts` (line 7)
- axios client has 30s timeout configured ✅
- But error message says "3000ms" ❌

**File**: `frontend/src/pages/Dashboard.tsx` (line 15)
- Uses `useLatestAlertsIntegration(20)` hook
- Hook calls `/alerts/latest?limit=50` endpoint

**File**: `scripts/run_api.py` (lines 1089-1115)
- `/alerts/latest` endpoint loads from JSON file instead of database
- Calls `load_alerts_from_json()` which has NO ERROR HANDLING for slow/missing file

**Root Cause**: No timeout at frontend level, but JSON loading likely slow OR the error message is hardcoded somewhere else.

### Issue 2: Health Mismatch

**File**: `scripts/run_api.py` (lines 666-696) - `/health` endpoint
- Returns only: `status` (ok/error), `timestamp`, `message`
- MISSING: `last_scan_time`, `uptime`, `data_mode`, `scan_status`, `api_calls_today`

**File**: `frontend/src/pages/Dashboard.tsx` (lines 28-29)
```javascript
const systemHealthy = health?.status === 'healthy'
const isApiConnected = !healthError && health?.status !== 'unhealthy'
```
- ❌ Health endpoint returns 'ok' or 'error', NOT 'healthy' or 'unhealthy'
- ❌ Dashboard has wrong property checks

### Issue 3: Mode Badges Disagree

**File**: `frontend/src/pages/Dashboard.tsx` (lines 238-244)
```javascript
// Data Mode section:
{health?.status === 'healthy' ? 'Production' : 'Demo'}
```
- ❌ Uses health status to determine mode (WRONG!)
- Should call `/config/data-mode` endpoint instead
- Header probably shows different status from a different source

**File**: `scripts/run_api.py` (lines 699-720)
- `/config/data-mode` GET endpoint EXISTS but Dashboard doesn't use it

### Issue 4: Scan Button No-Op

**File**: `frontend/src/pages/Dashboard.tsx` (lines 32-38)
```javascript
const handleTriggerScan = async () => {
  try {
    await triggerScan()  // No feedback after this!
  } catch (err) {
    console.error('Failed to trigger scan:', err)
  }
}
```
- ❌ No success message shown to user
- ❌ No UI state update after trigger
- ❌ User doesn't know if scan started or failed

**File**: `frontend/src/hooks/useApiIntegration.ts` (lines 176-201)
- `useTriggerScanIntegration()` exists but doesn't update UI state properly

---

## Solution Approach

### Fix 1: Enhance Health Endpoint
- Add missing fields: `last_scan_time`, `uptime`, `data_mode`, `scan_status`
- Change response structure to match frontend expectations
- Cache last scan time in database

### Fix 2: Fix Mode Detection Logic
- Dashboard should call `/config/data-mode` endpoint
- Display actual mode from API, not guessed from health status
- Add mode refresh button to System Status section

### Fix 3: Fix Scan Button Feedback
- Show toast notification on success
- Show toast notification on error with retry button
- Disable button during scan execution
- Update scan status in UI after trigger

### Fix 4: Optimize Alerts Loading
- Check if JSON file loading is causing delays
- Add error handling for missing/slow files
- Consider adding retry logic

### Fix 5: Fix Health Status Values
- Return consistent status values: 'ok' / 'error' (not 'healthy' / 'unhealthy')
- OR update frontend to check for 'ok' instead of 'healthy'

---

## Implementation Plan

### Phase 1: Fix API Health Endpoint

```python
# scripts/run_api.py - Enhanced HealthResponse

class HealthResponse(BaseModel):
    status: str  # 'ok' or 'error'
    timestamp: str  # UTC ISO 8601
    message: Optional[str] = None
    # NEW FIELDS:
    last_scan_time: Optional[str] = None  # Last scan completion time
    uptime_seconds: int = 0  # Process uptime
    data_mode: str = 'demo'  # 'demo' or 'production'
    scan_status: str = 'idle'  # 'idle', 'running', 'completed', 'error'
    api_calls_today: int = 0  # API calls made today
```

Update `/health` endpoint to query:
- `scheduler_state` table for `last_collection_ts`, `current_state`
- `scans` table for latest scan timestamp
- `get_settings()` for data_mode
- Process uptime

### Phase 2: Fix Frontend Dashboard

```typescript
// frontend/src/pages/Dashboard.tsx - Fixed sections:

// 1. Data Mode: Use actual mode from API
const { mode } = useConfigModeIntegration()  // NEW hook
const actualMode = mode || 'demo'

// 2. Scan Status: Show actual status from health endpoint
const scanStatus = health?.scan_status || 'unknown'

// 3. Last Scan Time: Use actual timestamp from endpoint
const lastScan = health?.last_scan_time || 'Never'

// 4. Scan Button: Add feedback
const handleTriggerScan = async () => {
  try {
    const result = await triggerScan()
    // Show success toast
    toast.success(`Scan #${result.scan_id} triggered`)
    // Refresh health status
    refetchHealth()
  } catch (err) {
    // Show error toast with retry
    toast.error(`Failed to trigger scan: ${err.message}`)
  }
}
```

### Phase 3: Add Missing Hooks

```typescript
// frontend/src/hooks/useApi.ts - NEW hook:

export const useConfigMode = (): UseApiState<ConfigModeResponse> & { refetch: () => Promise<void> } => {
  return useApi<ConfigModeResponse>('/config/data-mode', {
    immediate: true,
    interval: 60000  // Refresh every 60 seconds
  })
}

// frontend/src/hooks/useApiIntegration.ts - NEW integration:

export const useConfigModeIntegration = () => {
  const { mode, modeLoading, modeError, setMode } = useApiStore()  // Need to add to store
  const apiMode = useConfigMode()

  useEffect(() => {
    if (apiMode.data) {
      setMode(apiMode.data.mode)
    }
  }, [apiMode.data, setMode])

  return {
    mode,
    loading: modeLoading,
    error: modeError
  }
}
```

### Phase 4: Fix Zustand Store

```typescript
// frontend/src/store/apiStore.ts - Add mode management:

interface ApiStore {
  // ... existing state ...
  mode: string | null
  modeLoading: boolean
  modeError: Error | null
  setMode: (mode: string) => void
  setModeLoading: (loading: boolean) => void
  setModeError: (error: Error | null) => void
}
```

---

## Expected Outcomes

After all fixes:

1. ✅ **Alerts load properly** without timeout errors
2. ✅ **Health/mode/status all consistent** across page
3. ✅ **Mode badges show actual API mode**, not guessed
4. ✅ **Scan button shows feedback** with success/error notifications
5. ✅ **Last scan time displays correctly** from database
6. ✅ **API health status includes full system status**, not just connection check

---

## Files to Modify

### Backend (Python):
- `scripts/run_api.py` - Enhance health endpoint + add missing fields
- `functions/db/repositories.py` - Query last scan time from DB
- `functions/db/connection.py` - Add uptime tracking

### Frontend (TypeScript/React):
- `frontend/src/pages/Dashboard.tsx` - Fix mode/status display + scan button feedback
- `frontend/src/hooks/useApi.ts` - Add useConfigMode hook
- `frontend/src/hooks/useApiIntegration.ts` - Add useConfigModeIntegration
- `frontend/src/store/apiStore.ts` - Add mode state management
- `frontend/src/types/api.ts` - Update HealthResponse type

### Configuration:
- `.env` / `VITE_*` variables if needed for timeouts

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Breaking existing health checks | Low | Medium | Add fields, maintain backward compatibility |
| Mode endpoint not responding | Low | Low | Add fallback to demo mode in UI |
| Last scan time query slow | Low | Medium | Cache in memory, pre-compute on startup |
| Toast notifications block UI | Very Low | Low | Use non-blocking toast library |

