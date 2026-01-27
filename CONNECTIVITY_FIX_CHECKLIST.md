# Dashboard Connectivity - Implementation Checklist

**Target**: Fix all connectivity issues preventing dashboard from working on network (e.g., 192.168.1.16:8060)

**Estimated Effort**: 2-3 hours
**Priority**: CRITICAL

---

## Phase 1: Emergency - Get API Running (30 minutes)

### 1.1 Identify and Kill DuckDB Lock Holder
```bash
# Find what's holding the lock
ps aux | grep python | grep -v grep

# Check if PID 563181 is still running
ps -p 563181

# Kill the stuck process (if it's the scheduler)
kill -9 563181

# Verify lock is released
# Try to open database directly with duckdb
python3 -c "import duckdb; db = duckdb.connect('/path/to/cache.db'); print('OK')"
```

**Acceptance Criteria**:
- [ ] DuckDB lock is released
- [ ] Can open database file without "Could not set lock" error

### 1.2 Start API Server
```bash
# Terminal 1: Start the API server
cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard
python scripts/run_api.py

# Terminal 2: Verify it's running
curl http://localhost:8061/health
# Expected response: {"status":"ok","timestamp":"..."}
```

**Acceptance Criteria**:
- [ ] API server starts without database lock errors
- [ ] `curl http://localhost:8061/health` returns 200 OK
- [ ] Port 8061 shows in `netstat -tuln`
- [ ] Dashboard shows health check working (no "Health Check Error")

---

## Phase 2: Network Access - Fix CORS & Hostname (1 hour)

### 2.1 Update API CORS Configuration

**File**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/scripts/run_api.py`

**Current** (lines 493-499):
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8060", "127.0.0.1:8060"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Option A - For Development (Least Secure)**:
Replace with:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Option B - For Production (Recommended)**:
Replace with:
```python
import os

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8060,http://127.0.0.1:8060,http://192.168.1.16:8060"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Implementation Steps**:
1. [ ] Open `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/scripts/run_api.py`
2. [ ] Find `CORSMiddleware` configuration (line 493)
3. [ ] Replace `allow_origins` list with environment-aware version
4. [ ] Save file
5. [ ] Restart API server
6. [ ] Test CORS from remote IP

**Testing**:
```bash
# From different machine on network (192.168.1.16):
curl -H "Origin: http://192.168.1.16:8060" \
     http://192.168.1.16:8061/health

# Should NOT return CORS error, should return health data
```

**Acceptance Criteria**:
- [ ] CORS headers include remote IP origin in response
- [ ] Browser console shows no CORS errors
- [ ] API calls from `192.168.1.16:8060` work

### 2.2 Update Frontend API Base URL

**File**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/.env`

**Current**:
```
VITE_API_BASE_URL=http://localhost:8061
```

**Change to**:
```
VITE_API_BASE_URL=http://192.168.1.16:8061
```

Or if you want it dynamic:
```
# Leave empty to auto-detect from window.location
VITE_API_BASE_URL=
```

**Implementation Steps**:
1. [ ] Open `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/.env`
2. [ ] Change `VITE_API_BASE_URL` value
3. [ ] Save file
4. [ ] Restart frontend (should hot-reload in Vite)
5. [ ] Verify in browser DevTools Network tab

**Acceptance Criteria**:
- [ ] API calls go to correct IP (check Network tab in browser DevTools)
- [ ] Health check succeeds
- [ ] No "Failed to fetch" errors in console

### 2.3 Update WebSocket URL (Optional but Recommended)

**File**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/utils/constants.ts`

**Current** (line 10):
```typescript
export const API_ENDPOINTS = {
  ...
  WEBSOCKET: 'ws://localhost:8061/ws'
}
```

**Option A - Hardcode for now**:
```typescript
export const API_ENDPOINTS = {
  ...
  WEBSOCKET: 'ws://192.168.1.16:8061/ws'
}
```

**Option B - Make it dynamic** (Better):
```typescript
const getWebSocketUrl = () => {
  const apiUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin
  // Replace http/https with ws/wss
  return apiUrl
    .replace(/^https:/, 'wss:')
    .replace(/^http:/, 'ws:')
    .concat('/ws')
}

export const API_ENDPOINTS = {
  ...
  WEBSOCKET: getWebSocketUrl()
}
```

**Implementation Steps** (Option B - Recommended):
1. [ ] Open `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/utils/constants.ts`
2. [ ] Add `getWebSocketUrl()` function
3. [ ] Replace hardcoded WebSocket URL with function call
4. [ ] Save and verify hot-reload

**Acceptance Criteria**:
- [ ] WebSocket connects successfully (check Network tab for ws:// connection)
- [ ] No "WebSocket connection failed" errors in console

---

## Phase 3: Feature Enablement - Config Page Editable (30 minutes)

### 3.1 Add Demo/Prod Mode Toggle Endpoint (Backend)

**File**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/scripts/run_api.py`

**Add after line 658** (after `get_data_mode` endpoint):

```python
@app.post("/config/data-mode", response_model=ConfigModeResponse, tags=["Config"])
async def set_data_mode(mode: str = Query(..., pattern="^(demo|production)$")) -> ConfigModeResponse:
    """
    Set data mode (demo or production).

    Args:
        mode: Either 'demo' or 'production'

    Returns:
        ConfigModeResponse with new mode

    Raises:
        HTTPException: 400 if mode invalid, 500 if setting fails

    Example:
        POST /config/data-mode?mode=production
        {
            "mode": "production",
            "timestamp": "2026-01-27T12:30:00Z"
        }
    """
    try:
        if mode not in ["demo", "production"]:
            raise HTTPException(
                status_code=400,
                detail="mode must be 'demo' or 'production'"
            )

        settings = get_settings()
        settings.demo_mode = mode == "demo"
        logger.info(f"Data mode changed to: {mode}")

        return ConfigModeResponse(
            mode=mode,
            timestamp=get_utc_iso_timestamp(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set data mode: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set data mode: {e}")
```

**Implementation Steps**:
1. [ ] Open `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/scripts/run_api.py`
2. [ ] Navigate to line 658 (after `get_data_mode` function)
3. [ ] Add the new `set_data_mode` endpoint function
4. [ ] Save file
5. [ ] Restart API server
6. [ ] Test with curl:
   ```bash
   curl -X POST "http://localhost:8061/config/data-mode?mode=production"
   ```

**Acceptance Criteria**:
- [ ] Endpoint returns 200 with new mode
- [ ] Endpoint validates mode parameter (rejects invalid values)
- [ ] Endpoint logs the change

### 3.2 Add Demo/Prod Mode Toggle Hook (Frontend)

**File**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/hooks/useApi.ts`

**Add after line 268** (after `useTriggerScan`):

```typescript
/**
 * Set data mode (demo or production)
 */
export const useSetDataMode = (): {
  execute: (mode: 'demo' | 'production') => Promise<ConfigModeResponse>
  loading: boolean
  error: Error | null
  data: ConfigModeResponse | null
} => {
  return useApiPost<string, ConfigModeResponse>('/config/data-mode')
}
```

**Implementation Steps**:
1. [ ] Open `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/hooks/useApi.ts`
2. [ ] Add import for `ConfigModeResponse` type (already imported)
3. [ ] Add `useSetDataMode` hook at end of file
4. [ ] Save file

**Acceptance Criteria**:
- [ ] No TypeScript errors
- [ ] Hook can be imported in other components

### 3.3 Update ConfigStatus Page to Make Editable

**File**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/pages/ConfigStatus.tsx`

**Find the demo mode section** and replace with toggle:

```typescript
// Before: Read-only display
const modeDisplay = (
  <p className="text-sm text-gray-600">
    Current mode: <span className="font-mono font-bold">{mode}</span>
  </p>
)

// After: Make it editable with buttons
const modeDisplay = (
  <div className="flex items-center gap-4">
    <p className="text-sm text-gray-600">
      Current mode: <span className="font-mono font-bold">{mode}</span>
    </p>
    <div className="flex gap-2">
      <button
        onClick={() => handleModeChange('demo')}
        disabled={mode === 'demo' || modeChanging}
        className={`px-3 py-1 rounded text-sm ${
          mode === 'demo'
            ? 'bg-blue-500 text-white'
            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
        }`}
      >
        Demo
      </button>
      <button
        onClick={() => handleModeChange('production')}
        disabled={mode === 'production' || modeChanging}
        className={`px-3 py-1 rounded text-sm ${
          mode === 'production'
            ? 'bg-blue-500 text-white'
            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
        }`}
      >
        Production
      </button>
    </div>
    {modeChanging && <p className="text-xs text-gray-500">Changing...</p>}
  </div>
)

// Add handler
const handleModeChange = async (newMode: 'demo' | 'production') => {
  try {
    setModeChanging(true)
    await setDataMode.execute(newMode)
    // Refetch to confirm
    await refetchMode()
  } catch (err) {
    console.error('Failed to change mode:', err)
  } finally {
    setModeChanging(false)
  }
}
```

**Implementation Steps**:
1. [ ] Open `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/pages/ConfigStatus.tsx`
2. [ ] Import `useSetDataMode` hook at top
3. [ ] Add state for `modeChanging` with `useState`
4. [ ] Add `const setDataMode = useSetDataMode()` hook call
5. [ ] Replace read-only mode display with buttons
6. [ ] Add `handleModeChange` function
7. [ ] Save and verify in browser

**Acceptance Criteria**:
- [ ] Buttons appear for Demo/Production
- [ ] Clicking button calls API
- [ ] Mode updates in UI
- [ ] No errors in browser console

---

## Phase 4: Testing & Verification (30 minutes)

### 4.1 Test Health Check
```bash
# From same machine
curl http://localhost:8061/health

# From remote machine (192.168.1.16)
curl http://192.168.1.16:8061/health

# Both should return {"status":"ok","timestamp":"..."}
```

**Acceptance Criteria**:
- [ ] Both requests return 200 OK
- [ ] Response contains valid timestamp

### 4.2 Test Alerts Endpoint
```bash
# From remote machine
curl "http://192.168.1.16:8061/alerts/latest?limit=5"

# Should return valid alert data
```

**Acceptance Criteria**:
- [ ] Returns 200 OK with alerts array
- [ ] No CORS errors in browser

### 4.3 Test Options Endpoint
```bash
# From remote machine
curl "http://192.168.1.16:8061/options/AAPL/snapshot"

# Should return chain data
```

**Acceptance Criteria**:
- [ ] Returns 200 OK with chain data
- [ ] Data contains underlying_price, calls, puts

### 4.4 Test Scan Trigger
```bash
# From remote machine
curl -X POST "http://192.168.1.16:8061/scan/run"

# Should return scan ID and "running" status
```

**Acceptance Criteria**:
- [ ] Returns 200 OK with scan_id
- [ ] Dashboard scan button works (no more "does nothing")

### 4.5 Test Dashboard from Remote IP

**From browser on different machine** (192.168.1.x):
1. [ ] Navigate to `http://192.168.1.16:8060`
2. [ ] Dashboard loads without 404 errors
3. [ ] Health check passes (no red error box)
4. [ ] Recent alerts display properly
5. [ ] Click "View All Alerts" navigates to alerts page
6. [ ] Alerts page loads alerts from API
7. [ ] Option chain pages load data
8. [ ] Trigger scan button works (no error)
9. [ ] Configuration page shows current mode
10. [ ] Can toggle between Demo/Production modes

**Acceptance Criteria**:
- [ ] All 10 items above pass without errors
- [ ] Browser console has no warnings/errors
- [ ] Network tab shows requests going to correct IP (192.168.1.16)

---

## Phase 5: Documentation & Cleanup (15 minutes)

### 5.1 Update Project Documentation

**File**: `README.md` - Add network access instructions

Add section:
```markdown
## Accessing Dashboard from Network

To access the dashboard from another machine on the network:

1. **Find the API server IP address**:
   ```bash
   hostname -I
   # Example output: 192.168.1.16
   ```

2. **Update frontend configuration**:
   - Edit `frontend/.env`
   - Change `VITE_API_BASE_URL=http://192.168.1.16:8061`

3. **Access from another machine**:
   - Open browser to `http://192.168.1.16:8060`
   - All features should work normally

4. **Or set environment variable before starting**:
   ```bash
   export VITE_API_BASE_URL=http://192.168.1.16:8061
   npm start
   ```
```

### 5.2 Update Environment Variables Documentation

**File**: `frontend/.env.example` - Add note about IP configuration

```
# API Configuration
# For local access (same machine): http://localhost:8061
# For network access: http://<YOUR_IP>:8061
VITE_API_BASE_URL=http://localhost:8061

# WebSocket Configuration
# For local access: ws://localhost:8061/ws
# For network access: ws://<YOUR_IP>:8061/ws
VITE_WS_URL=ws://localhost:8061/ws
```

### 5.3 Document CORS Configuration

**File**: New file `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/CORS_CONFIGURATION.md`

```markdown
# CORS Configuration Guide

## What is CORS?

Cross-Origin Resource Sharing (CORS) is a browser security feature that prevents
JavaScript from accessing data on different hosts unless the server explicitly allows it.

## Current Configuration

The API server allows requests from:
- `http://localhost:8060` (local development)
- `http://127.0.0.1:8060` (local loopback)
- `http://192.168.1.16:8060` (network access)

See `scripts/run_api.py` line 495 for the allow_origins list.

## Adding New Origins

To add support for a new IP address or domain:

1. Update `scripts/run_api.py`:
   ```python
   allow_origins=[
       "http://localhost:8060",
       "http://127.0.0.1:8060",
       "http://192.168.1.16:8060",  # Add your IP here
       "http://new.ip.address:8060",  # New entry
   ]
   ```

2. Restart the API server

3. Test the connection from that origin

## Production Deployment

For production, use environment variable:
```bash
export ALLOWED_ORIGINS="https://yourdomain.com,https://www.yourdomain.com"
python scripts/run_api.py
```
```

### 5.4 Update Troubleshooting Guide

**File**: Update existing documentation with troubleshooting section

---

## Pre-Implementation Checklist

Before starting implementation:

- [ ] Read the full `CONNECTIVITY_ANALYSIS.md`
- [ ] Understand the root causes
- [ ] Have admin/sudo access to kill processes if needed
- [ ] Test API manually before fixing frontend
- [ ] Keep terminal open with `tail -f logs/option_chain_dashboard.log`

---

## Implementation Order

**DO THIS IN ORDER**:

1. **Phase 1** - Kill lock holder and start API
2. **Phase 2** - Fix CORS and hostname issues
3. **Test** - Verify API accessible from remote IP
4. **Phase 3** - Add configuration toggle (optional)
5. **Phase 4** - Full end-to-end testing
6. **Phase 5** - Update documentation

---

## Success Criteria

After completing all phases:

- [ ] Dashboard accessible from `http://192.168.1.16:8060`
- [ ] No "Health Check Error" on dashboard
- [ ] Alerts load and display properly
- [ ] Option chains load and display properly
- [ ] Scan trigger button works
- [ ] Configuration page shows current mode
- [ ] Can toggle between demo/production modes
- [ ] No errors in browser console
- [ ] All network requests go to `192.168.1.16:8061`

---

## Rollback Plan

If something breaks:

1. **Database issues**:
   ```bash
   # Restore from backup or delete cache.db to recreate
   rm /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/data/cache.db
   python -c "from functions.db.connection import init_db; init_db()"
   ```

2. **API won't start**:
   ```bash
   # Check logs
   tail -100 logs/option_chain_dashboard.log
   # Revert changes to run_api.py
   git checkout scripts/run_api.py
   ```

3. **Frontend broken**:
   ```bash
   # Revert .env file
   git checkout frontend/.env
   # Clear node cache
   rm -rf frontend/node_modules/.vite
   ```

---

## Estimated Timeline

- Phase 1 (Emergency): 30 minutes
- Phase 2 (Network): 60 minutes
- Phase 3 (Features): 30 minutes
- Phase 4 (Testing): 30 minutes
- Phase 5 (Docs): 15 minutes

**Total**: ~2.5 hours

---

## Questions?

Refer to `CONNECTIVITY_ANALYSIS.md` for detailed technical explanation of each issue.
