# Connectivity Issues - Files to Modify

## Quick Reference - Exact Locations

### Phase 1: Emergency (Get API Running)

**No code changes needed** - Just kill the database lock holder process

```bash
# Find and kill
ps aux | grep python | grep -v grep
kill -9 <PID>  # PID 563181 from logs

# Then start API
cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard
python scripts/run_api.py
```

---

### Phase 2: Network Access

#### File 1: Update API CORS Configuration

**Path**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/scripts/run_api.py`

**Lines to change**: 493-499

**Current code**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8060", "127.0.0.1:8060"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Change to (Development)**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**OR Change to (Production - Recommended)**:
```python
import os

# Add this at the top after other imports (around line 50)
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8060,http://127.0.0.1:8060,http://192.168.1.16:8060"
).split(",")

# Then update middleware (lines 493-499)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Impact**: Allows API requests from any origin (dev) or specified IPs (prod)

---

#### File 2: Update Frontend API Base URL

**Path**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/.env`

**Current code** (entire file):
```
VITE_API_BASE_URL=http://localhost:8061
VITE_APP_NAME=Option Chain Dashboard
VITE_APP_VERSION=1.0.0
VITE_WS_URL=ws://localhost:8061/ws
VITE_ENABLE_REAL_TIME_UPDATES=true
VITE_ENABLE_DARK_MODE=false
```

**Change VITE_API_BASE_URL to your IP**:
```
VITE_API_BASE_URL=http://192.168.1.16:8061
VITE_APP_NAME=Option Chain Dashboard
VITE_APP_VERSION=1.0.0
VITE_WS_URL=ws://localhost:8061/ws
VITE_ENABLE_REAL_TIME_UPDATES=true
VITE_ENABLE_DARK_MODE=false
```

**Note**: Change `192.168.1.16` to whatever IP your server is actually on

**Impact**: Frontend will call API on correct IP instead of localhost

---

#### File 3: Make WebSocket URL Dynamic (Optional but Recommended)

**Path**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/utils/constants.ts`

**Lines to change**: 10 (in API_ENDPOINTS object)

**Current code** (lines 3-11):
```typescript
export const API_ENDPOINTS = {
  HEALTH: '/api/health',
  CONFIG: '/api/config',
  ALERTS: '/api/alerts',
  TICKERS: '/api/tickers',
  OPTION_CHAIN: '/api/options/chain',
  STRATEGIES: '/api/strategies',
  WEBSOCKET: 'ws://localhost:8061/ws'
}
```

**Change to**:
```typescript
// Helper function to get WebSocket URL dynamically
const getWebSocketUrl = (): string => {
  const apiUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin
  // Convert http/https to ws/wss and add /ws path
  const protocol = apiUrl.startsWith('https') ? 'wss' : 'ws'
  const host = apiUrl.replace(/^https?:\/\//, '')
  return `${protocol}://${host}/ws`
}

export const API_ENDPOINTS = {
  HEALTH: '/api/health',
  CONFIG: '/api/config',
  ALERTS: '/api/alerts',
  TICKERS: '/api/tickers',
  OPTION_CHAIN: '/api/options/chain',
  STRATEGIES: '/api/strategies',
  WEBSOCKET: getWebSocketUrl()
}
```

**Impact**: WebSocket will use same host as API (will work from any IP)

---

#### File 4: Update Frontend API Client (Optional - for auto-detection)

**Path**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/utils/apiClient.ts`

**Lines to change**: 1-12 (top of file)

**Current code**:
```typescript
import axios, { AxiosInstance, AxiosError, AxiosResponse } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8061'

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})
```

**Change to** (with better fallback):
```typescript
import axios, { AxiosInstance, AxiosError, AxiosResponse } from 'axios'

// Get API base URL from environment or derive from current location
const getApiBaseUrl = (): string => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }
  
  // Fall back to current hostname with port 8061
  // This allows: http://192.168.1.16:8060 → http://192.168.1.16:8061
  const host = window.location.hostname
  const port = '8061'
  const protocol = window.location.protocol
  
  return `${protocol}//${host}:${port}`
}

const API_BASE_URL = getApiBaseUrl()

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
})
```

**Impact**: Frontend will automatically use correct IP if not specified in .env

---

### Phase 3: Configuration Toggle (Optional)

#### File 5: Add Demo/Prod Mode Toggle Endpoint (Backend)

**Path**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/scripts/run_api.py`

**Location**: After the `get_data_mode()` function (line 658)

**Add this new endpoint**:
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

**Impact**: Allows API to change demo mode dynamically

---

#### File 6: Add Hook to Call Demo Mode Toggle (Frontend)

**Path**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/hooks/useApi.ts`

**Location**: At the end of the file (after line 268)

**Add this new hook**:
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

**Impact**: Frontend can call the new toggle endpoint

---

#### File 7: Update Configuration Page UI

**Path**: `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/frontend/src/pages/ConfigStatus.tsx`

**Note**: Exact changes depend on current component structure. See CONNECTIVITY_FIX_CHECKLIST.md for detailed instructions.

**General approach**:
1. Import `useSetDataMode` hook
2. Add state for `isChanging`
3. Replace read-only mode display with toggle buttons
4. Call `setDataMode.execute('demo')` or `execute('production')` when clicked

**Impact**: Users can toggle mode from Configuration page

---

## Summary Table - All Files

| Phase | File | What to Change | Location | Priority |
|-------|------|---|----------|----------|
| 1 | N/A | Kill PID 563181 | CLI | CRITICAL |
| 2 | run_api.py | Update CORS allow_origins | Lines 493-499 | CRITICAL |
| 2 | frontend/.env | Change VITE_API_BASE_URL | Line 2 | CRITICAL |
| 2 | constants.ts | Make WEBSOCKET dynamic | Line 10 | HIGH |
| 2 | apiClient.ts | Better API URL fallback | Lines 1-12 | MEDIUM |
| 3 | run_api.py | Add POST /config/data-mode | After line 658 | MEDIUM |
| 3 | useApi.ts | Add useSetDataMode hook | End of file | MEDIUM |
| 3 | ConfigStatus.tsx | Add toggle UI | Various | MEDIUM |

---

## Step-by-Step Implementation

### Minimum Fix (15 minutes)
1. Kill PID 563181
2. Start API: `python scripts/run_api.py`
3. Change `frontend/.env` line 2: `VITE_API_BASE_URL=http://192.168.1.16:8061`
4. Change `scripts/run_api.py` line 495: `allow_origins=["*"]`

**Result**: Works from any IP on network

### Recommended Fix (1 hour)
Do minimum fix + add:
5. Make WebSocket URL dynamic (constants.ts line 10)
6. Better API URL fallback (apiClient.ts lines 1-12)

**Result**: Auto-detects correct IP, no config needed

### Full Fix (2.5 hours)
Do recommended fix + add:
7. Add demo/prod toggle endpoint (run_api.py)
8. Add toggle hook (useApi.ts)
9. Update ConfigStatus page with UI

**Result**: All features working + config editable

---

## Testing Each Change

### After Phase 2.1 (CORS fix)
```bash
curl -H "Origin: http://192.168.1.16:8060" \
     http://192.168.1.16:8061/health
# Should return health data, not CORS error
```

### After Phase 2.2 (Frontend URL fix)
```bash
# Open browser DevTools Network tab
# Access http://192.168.1.16:8060
# Check Network tab - requests should go to 192.168.1.16:8061
# No failed requests, no CORS errors
```

### After Phase 3 (Config toggle)
```bash
# Test endpoint
curl -X POST "http://192.168.1.16:8061/config/data-mode?mode=production"
# Should return {"mode":"production","timestamp":"..."}

# Test UI
# Open Configuration page
# Should see Demo/Production toggle buttons
# Click to toggle, should work without errors
```

---

## Environment Variables for Production

Create `.env.production` or use environment variables:

```bash
# Backend
export ALLOWED_ORIGINS="https://yourdomain.com,https://www.yourdomain.com"

# Frontend (set before npm start)
export VITE_API_BASE_URL="https://api.yourdomain.com:8061"
export VITE_WS_URL="wss://api.yourdomain.com:8061/ws"
```

---

**See CONNECTIVITY_FIX_CHECKLIST.md for detailed implementation steps with code examples**
