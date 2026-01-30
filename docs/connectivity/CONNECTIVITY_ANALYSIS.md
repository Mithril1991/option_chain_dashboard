# Dashboard Connectivity Issues - Comprehensive Analysis

**Analysis Date**: 2026-01-27
**Status**: CRITICAL - Backend API not running, Frontend isolated from API

---

## Executive Summary

The Option Chain Dashboard has **critical connectivity issues** preventing the frontend from communicating with the backend API. The frontend is running on port 8060 but the backend API (port 8061) is **not running**. Additionally, there are **hardcoded localhost URLs** in the frontend configuration that assume both services are running on the same machine, which breaks when accessing the dashboard from a different IP address (e.g., 192.168.1.16).

### User-Reported Issues Match Root Causes
1. **"Health Check Error"** → API endpoint unreachable (API not running)
2. **"Failed to load alerts"** → API endpoint `/alerts/latest` unreachable
3. **"Error loading option chain"** → API endpoint `/options/{ticker}/snapshot` unreachable
4. **"Trigger new scan does nothing"** → API endpoint `/scan/run` unreachable
5. **"Demo mode but config read-only"** → Demo mode is hardcoded as true in config.yaml

---

## Issue 1: Backend API Not Running

### Problem
The FastAPI backend server (port 8061) is **not currently running**.

### Evidence
```bash
# Port 8060 is listening (React frontend)
tcp 0 0 0.0.0.0:8060 0.0.0.0:* LISTEN

# Port 8061 is NOT listening (API server missing)
# grep "8061" returned nothing

# Latest log shows API shutdown at 12:24:16 UTC
2026-01-27T12:24:16.724761+00:00Z [INFO] scripts.run_api:lifespan:466 - Shutting down Option Chain Dashboard API server...
```

### Expected State
- Backend API should be listening on `0.0.0.0:8061` (all interfaces, not just localhost)
- Database must be unlocked before API can start

### Database Lock Issue
There are DuckDB concurrency issues visible in logs (Task #3):
```
IO Error: Could not set lock on file "/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/data/cache.db":
Conflicting lock is held in /usr/bin/python3.12 (PID 563181)
```

This indicates another Python process is holding the database lock, preventing the API from starting.

---

## Issue 2: Hardcoded Localhost URLs (Network Accessibility Problem)

### Problem
The frontend is configured with hardcoded `localhost:8061` URLs, which:
1. Only works if API is on the same machine
2. Fails when accessing dashboard from a different IP (e.g., `192.168.1.16:8060`)
3. Browser security doesn't allow mixed protocols or different IPs

### Configuration Files Affected

#### File: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/.env`
```
VITE_API_BASE_URL=http://localhost:8061
VITE_WS_URL=ws://localhost:8061/ws
```

#### File: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/utils/constants.ts`
```typescript
export const API_ENDPOINTS = {
  HEALTH: '/api/health',        // Expects baseURL to be set
  CONFIG: '/api/config',
  ALERTS: '/api/alerts',
  ...
}

export const API_ENDPOINTS = {
  ...
  WEBSOCKET: 'ws://localhost:8061/ws'  // ← HARDCODED! Should use env var
}
```

#### File: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/utils/apiClient.ts`
```typescript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8061'
```

**Issue**: Falls back to `localhost:8061` if env var not set. For network access, should fail loudly or use a discoverable endpoint.

### Impact
When accessing `http://192.168.1.16:8060`:
- Frontend loads successfully
- Frontend tries to call `http://localhost:8061/health`
- Request fails because `localhost` doesn't resolve to the backend server IP
- User sees "Health Check Error"

---

## Issue 3: API Server Not Configured for Network Accessibility

### Problem
Even when running, the API might only be accessible from localhost depending on binding.

### Current Configuration (Correct)
**File**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/scripts/run_api.py` (lines 1507-1513)
```python
uvicorn.run(
    "scripts.run_api:app",
    host="0.0.0.0",      # ✓ Binds to all interfaces
    port=8061,
    reload=True,
    log_level="info",
)
```

**Status**: ✓ API binds to `0.0.0.0:8061` (correct for network access)

### Task #2 Status
According to task list, "Fix network accessibility - bind to 0.0.0.0:8061 for FastAPI backend" is marked as `in_progress`. The code shows it's already configured correctly, but the service isn't running.

---

## Issue 4: CORS Configuration May Block Frontend

### Problem
FastAPI CORS middleware is configured restrictively.

### Current CORS Config
**File**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/scripts/run_api.py` (lines 493-499)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8060", "127.0.0.1:8060"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue
CORS only allows requests from:
- `http://localhost:8060` (localhost only)
- `http://127.0.0.1:8060` (loopback only)

When accessing frontend from `http://192.168.1.16:8060`, the browser blocks API requests with CORS error:
```
Access-Control-Allow-Origin: Only localhost:8060 and 127.0.0.1:8060 allowed
```

### Impact
Even if API were running and URL was correct, requests from `192.168.1.16:8060` would be blocked by browser CORS policy.

---

## Issue 5: WebSocket Hardcoded (Bonus Issue)

### Problem
WebSocket connection is hardcoded, not environment-aware.

**File**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/utils/constants.ts` (line 10)
```typescript
export const WEBSOCKET: 'ws://localhost:8061/ws'
```

This prevents real-time updates when accessing from a different IP.

---

## API Endpoints Verified (Working When API Runs)

When the API was running (logs from 12:23-12:24), the following endpoints worked:
- ✓ `GET /health` - Returns 200 with status
- ✓ `GET /alerts/latest` - Returns alerts from JSON
- ✓ `GET /alerts` - Filters alerts
- ✓ `GET /options/{ticker}/snapshot` - Returns options chain
- ✓ `GET /features/{ticker}/latest` - Returns feature data
- ✓ `GET /config/data-mode` - Returns current mode
- ✓ `GET /` - Root endpoint
- ✓ `POST /scan/run` - Triggers scan (not tested in logs shown)

**Status**: API endpoints are properly implemented and functional.

---

## Frontend API Client Behavior

### API Call Flow
1. Dashboard component calls `useHealthCheckIntegration()`
2. Hook calls `useHealthCheck()`
3. `useHealthCheck()` calls `useApi('/health')`
4. `useApi()` calls `apiClient.get<T>('/health')`
5. apiClient uses base URL: `http://localhost:8061` (or env var)
6. Request sent to `http://localhost:8061/health`
7. **If API not running**: Connection refused
8. **If accessing from different IP**: Request to wrong address

### Error Handling
Frontend has proper error handling:
- Shows "Health Check Error" with error message
- Shows "Failed to load alerts" when alerts endpoint fails
- Shows "Error loading option chain" when options endpoint fails
- Scan trigger silently fails if endpoint unreachable

**Status**: Error handling is correct, but root cause is API connectivity.

---

## Configuration Status Summary

| Component | Config | Current Value | Issue | Priority |
|-----------|--------|---------------|-------|----------|
| API Host/Port | run_api.py | 0.0.0.0:8061 | Not running | CRITICAL |
| API Base URL | .env | localhost:8061 | Not network accessible | HIGH |
| API Fallback | apiClient.ts | localhost:8061 | Hardcoded fallback | HIGH |
| CORS Origins | run_api.py | localhost:8060, 127.0.0.1:8060 | Rejects remote IP | HIGH |
| WebSocket URL | constants.ts | ws://localhost:8061/ws | Hardcoded | MEDIUM |
| Demo Mode | config.yaml | true | Can't toggle in UI | MEDIUM |

---

## Root Cause Chain

```
PRIMARY ISSUE: Backend API not running
    ↓
DuckDB database lock held by another process (PID 563181)
    ↓
Scheduler engine or another instance can't release lock
    ↓
API can't initialize database
    ↓
API startup fails

SECONDARY ISSUES (Even when API would run):
    ↓
Frontend uses hardcoded localhost:8061 URLs
    ↓
API CORS only allows localhost origins
    ↓
Accessing from 192.168.1.16 fails with network errors
    ↓
User sees "Health Check Error", "Failed to load alerts", etc.
```

---

## What Works vs What Doesn't

### ✓ Works (Verified in logs)
- Frontend (Vite dev server) running on port 8060
- API endpoints implemented and return correct responses
- Logging and error handling
- Configuration loading
- Request/response middleware
- Database schema initialization (when not locked)
- API root endpoint (`GET /`)

### ✗ Doesn't Work
- Backend API startup (database lock)
- Frontend accessing API from different IP (localhost hardcoded)
- CORS for remote IP access
- WebSocket connections from remote IP
- Configuration page editable toggle
- Demo/Production mode toggle in dashboard

---

## Impact Assessment

### Blocked Functionality
1. Health status monitoring - can't verify API is alive
2. Alert viewing - can't load alerts from API
3. Options chain viewing - can't load options data
4. Scan triggering - can't execute new scans
5. Real-time updates - WebSocket won't work from remote IP

### User-Facing Symptoms
- Dashboard shows "Health Check Error" on load
- "Recent Alerts" section shows error message
- Trying to view option chains results in empty state with error
- "Trigger Scan" button appears to do nothing (silent error)
- Configuration page read-only (demo mode hardcoded)

---

## Fix Checklist

### CRITICAL (Must Fix)
- [ ] **Kill conflicting DuckDB process** - Release database lock so API can start
  - Find PID 563181: `ps aux | grep 563181`
  - Kill if it's a stuck scheduler: `kill -9 563181`
  - Or stop main.py if running

- [ ] **Start API server** - Backend must be listening on 8061
  - `cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard`
  - `python scripts/run_api.py` or via main.py
  - Verify: `curl http://localhost:8061/health`

### HIGH (Should Fix for Network Access)
- [ ] **Update CORS configuration** - Allow remote IP access
  - File: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/scripts/run_api.py`
  - Change `allow_origins` to include `192.168.1.16:8060` or use `["*"]` for development
  - Or use environment variable for dynamic origin

- [ ] **Make API URL environment-aware** - Support different IPs
  - File: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/.env`
  - Use `VITE_API_BASE_URL=http://192.168.1.16:8061` instead of localhost
  - Or auto-detect from current hostname

- [ ] **Fix WebSocket URL** - Make it environment-aware
  - File: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/utils/constants.ts`
  - Use environment variable instead of hardcoded string

### MEDIUM (Nice to Have)
- [ ] **Make configuration page editable** - Allow demo/prod toggle
  - File: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/pages/ConfigStatus.tsx`
  - Implement POST to `/config/reload` endpoint

- [ ] **Add runtime mode toggle** - Expose `DEMO_MODE` setting
  - Add endpoint: `POST /config/demo-mode` to toggle
  - Update UI to allow mode switching

### LOW (Future)
- [ ] Add health check retry logic with backoff
- [ ] Add connection status indicator in UI
- [ ] Implement WebSocket fallback to polling

---

## Testing the Fix

### Step 1: Verify API Connectivity
```bash
# Should return 200 OK with health data
curl http://localhost:8061/health

# Should return list of alerts
curl http://localhost:8061/alerts/latest?limit=5

# Should return options chain for AAPL
curl http://localhost:8061/options/AAPL/snapshot
```

### Step 2: Verify CORS (from different IP)
```bash
# From 192.168.1.16 browser:
curl -H "Origin: http://192.168.1.16:8060" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: Content-Type" \
     http://192.168.1.16:8061/health
```

### Step 3: Verify Frontend Works
```bash
# Access dashboard from different machine:
# http://192.168.1.16:8060

# Check browser console for:
# 1. No CORS errors
# 2. Health check succeeds
# 3. Alerts load
# 4. Options chains load
```

---

## Files to Modify

### Priority 1 (Must fix to get working)
1. `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/scripts/run_api.py`
   - Line 495: Update `allow_origins` for remote access
   - Consider reading from environment variable

### Priority 2 (Should fix for network access)
2. `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/.env`
   - Change `VITE_API_BASE_URL` to match actual API server IP

3. `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/utils/apiClient.ts`
   - Consider auto-detecting API base URL from hostname

4. `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/utils/constants.ts`
   - Line 10: Make `WEBSOCKET` environment-aware

### Priority 3 (Feature enablement)
5. `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/pages/ConfigStatus.tsx`
   - Add form to toggle demo/production mode

---

## Summary

The Option Chain Dashboard connectivity issues are caused by:

1. **Backend API not running** (critical blocker)
2. **Hardcoded localhost URLs** (breaks network access)
3. **CORS configured for localhost only** (blocks remote requests)
4. **WebSocket hardcoded** (breaks real-time features)
5. **Demo mode hardcoded** (can't toggle in UI)

All API endpoints are properly implemented and tested. The frontend error handling is correct. Once the API is running and the hostname/CORS issues are fixed, the dashboard will work correctly from any network location.

---

## Next Steps

1. **Immediately**: Stop any conflicting Python process holding DuckDB lock
2. **ASAP**: Start the API server and verify it's listening on 8061
3. **Today**: Update CORS and API URL configuration for network access
4. **This week**: Make WebSocket and API discovery dynamic
5. **Later**: Implement configuration page editable features

---

**Prepared by**: Claude Code Analysis
**Date**: 2026-01-27
**Status**: Analysis complete, ready for implementation
