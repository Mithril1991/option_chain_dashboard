# Dashboard Connectivity - Visual Diagrams

## Current State (BROKEN)

```
USER MACHINE (192.168.1.16)
┌────────────────────────────────────┐
│ Browser: http://192.168.1.16:8060  │
│                                    │
│ Frontend loads OK (Vite running)   │
│ ✓ HTML/CSS/JS files served         │
│                                    │
│ API calls:                         │
│ ✗ http://localhost:8061/health     │
│   └─ 404 / Connection refused      │
│   └─ (localhost = 127.0.0.1 on     │
│       client, not server IP!)      │
└────────────────────────────────────┘
           │
           │ (tries http://localhost:8061)
           │ (which is 127.0.0.1 on client)
           │ (doesn't exist on this machine)
           │
           ✗ Connection refused

SERVER MACHINE (192.168.1.16)
┌────────────────────────────────────┐
│ ✓ Frontend running on 0.0.0.0:8060 │
│ ✗ Backend NOT running on 0.0.0.0:  │
│   (Database locked - can't start)  │
│                                    │
│ DB Lock held by PID 563181         │
│ Cannot start API until released    │
└────────────────────────────────────┘
```

### Result
- Browser at client can't reach API
- API isn't running anyway
- User sees "Health Check Error", "Failed to load alerts", etc.

---

## How It Should Work (Current Issues Highlighted)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PROBLEM 1: DATABASE LOCK                         │
│  /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/data/    │
│  └─ cache.db ← LOCKED by PID 563181 (scheduler still running?)     │
│                                                                     │
│  CONSEQUENCE: API won't start                                      │
│  FIX: kill -9 563181                                               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│               API SERVER (Should be on 0.0.0.0:8061)                │
│  /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/         │
│  └─ scripts/run_api.py                                             │
│     ├─ Binds to 0.0.0.0:8061 ✓ (correct)                           │
│     └─ CORS allows_origins: [localhost, 127.0.0.1]                │
│        └─ PROBLEM 2: Doesn't include 192.168.1.16 ✗               │
│                                                                     │
│  Endpoints implemented ✓:                                          │
│  ├─ GET /health                                                    │
│  ├─ GET /alerts/latest                                             │
│  ├─ GET /options/{ticker}/snapshot                                │
│  ├─ GET /features/{ticker}/latest                                 │
│  ├─ POST /scan/run                                                 │
│  └─ [etc - all working]                                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│        FRONTEND (Running on 0.0.0.0:8060) ✓                        │
│  /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/        │
│  └─ frontend/                                                      │
│     ├─ .env:                                                       │
│     │  VITE_API_BASE_URL=http://localhost:8061                    │
│     │  └─ PROBLEM 3: Hardcoded localhost ✗                        │
│     └─ src/utils/                                                  │
│        ├─ apiClient.ts: Fallback to localhost ✗                   │
│        ├─ constants.ts: WEBSOCKET hardcoded ✗                     │
│        └─ All requests go to: http://localhost:8061               │
│           (not 192.168.1.16:8061)                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Diagram - Network Access

```
╔═══════════════════════════════════════════════════════════════════╗
║              CLIENT NETWORK (Another Machine)                    ║
║              IP: 192.168.1.20 or any other IP                   ║
║                                                                   ║
║  ┌──────────────────────────────┐                               ║
║  │ Web Browser                  │                               ║
║  │ http://192.168.1.16:8060     │                               ║
║  └──────────────────────────────┘                               ║
║                │                                                 ║
║    Can it reach 192.168.1.16:8060?                              ║
║                │                                                 ║
║                YES (if frontend bound to 0.0.0.0) ✓              ║
║                │                                                 ║
║                ├─────────────────────────────────┐              ║
║                │         HTML/CSS/JS            │              ║
║                │         (Frontend loads) ✓     │              ║
║                └─────────────────────────────────┘              ║
║                │                                                 ║
║    Can it reach 192.168.1.16:8061?                              ║
║                │                                                 ║
║                NO (current configuration) ✗                      ║
║                ├─ Frontend tries: localhost:8061                ║
║                │  (which is 127.0.0.1 on THIS machine)         ║
║                ├─ Connection refused                             ║
║                └─ User sees error: "Health Check Error"          ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
            Network (LAN) 192.168.1.0/24
                    │
                    │ TCP packets to 192.168.1.16:8061
                    │
╔═══════════════════════════════════════════════════════════════════╗
║           SERVER NETWORK (Option Chain Dashboard)                ║
║           IP: 192.168.1.16                                      ║
║                                                                   ║
║  ┌──────────────────────────────┐                               ║
║  │ Port 8060 (Vite frontend)    │                               ║
║  │ Listening on 0.0.0.0 ✓        │                               ║
║  │ Can handle requests from any  │                               ║
║  │ IP on network ✓               │                               ║
║  └──────────────────────────────┘                               ║
║                                                                   ║
║  ┌──────────────────────────────┐                               ║
║  │ Port 8061 (FastAPI backend)  │                               ║
║  │ STATUS: NOT RUNNING ✗         │                               ║
║  │ (Database locked)             │                               ║
║  │                               │                               ║
║  │ Would listen on:              │                               ║
║  │ 0.0.0.0:8061 ✓ (code ready)  │                               ║
║  │ But database is locked        │                               ║
║  └──────────────────────────────┘                               ║
║                                                                   ║
║  ┌──────────────────────────────┐                               ║
║  │ Database Lock                │                               ║
║  │ /data/cache.db               │                               ║
║  │ Locked by: PID 563181        │                               ║
║  │ Status: BLOCKING ✗           │                               ║
║  │ Action: kill -9 563181       │                               ║
║  └──────────────────────────────┘                               ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## Request Flow - Current (Broken)

```
User opens browser at 192.168.1.16:8060

1. Browser to Frontend (port 8060)
   ┌─────────────────────────────────┐
   │ Request: http://192.168.1.16:   │
   │         8060                    │
   │                                 │
   │ Path: 0.0.0.0:8060              │
   │ Status: ✓ LISTENING             │
   │                                 │
   │ Response: HTML/CSS/JS           │
   │ Status: ✓ SUCCESS               │
   └─────────────────────────────────┘

2. Browser loads frontend JavaScript

3. Frontend runs useHealthCheck() hook

4. Hook calls: apiClient.get('/health')

5. apiClient uses base URL:
   ┌─────────────────────────────────┐
   │ VITE_API_BASE_URL               │
   │ = http://localhost:8061         │
   │   └─ PROBLEM: localhost!        │
   │                                 │
   │ Full URL becomes:               │
   │ http://localhost:8061/health    │
   │ └─ Resolves to 127.0.0.1 on    │
   │    CLIENT machine (not server!) │
   └─────────────────────────────────┘

6. Browser makes request to localhost:8061
   ┌─────────────────────────────────┐
   │ Request: http://127.0.0.1:8061/ │
   │         health                  │
   │                                 │
   │ Machine: Client (192.168.1.20)  │
   │ Port: 8061 on client machine    │
   │                                 │
   │ Path: 0.0.0.0:8061 on client    │
   │ Status: ✗ NOT LISTENING         │
   │                                 │
   │ Error: Connection refused       │
   │ Status: ✗ FAILED                │
   └─────────────────────────────────┘

7. Frontend receives error

8. Dashboard displays:
   ┌─────────────────────────────────┐
   │ "Health Check Error"            │
   │                                 │
   │ Error message:                  │
   │ Connection refused              │
   └─────────────────────────────────┘

9. Alerts, options, scans all fail with same error
```

---

## Request Flow - After Fix

```
User opens browser at 192.168.1.16:8060

1. Browser to Frontend (port 8060)
   ┌─────────────────────────────────┐
   │ Request: http://192.168.1.16:   │
   │         8060                    │
   │                                 │
   │ Path: 0.0.0.0:8060              │
   │ Status: ✓ LISTENING             │
   │ Response: ✓ SUCCESS             │
   └─────────────────────────────────┘

2. Browser loads frontend JavaScript

3. Frontend runs useHealthCheck() hook

4. Hook calls: apiClient.get('/health')

5. apiClient uses base URL:
   ┌─────────────────────────────────┐
   │ VITE_API_BASE_URL               │
   │ = http://192.168.1.16:8061      │
   │   └─ FIXED: Real IP!            │
   │                                 │
   │ Full URL becomes:               │
   │ http://192.168.1.16:8061/health │
   │ └─ Resolves to server IP        │
   └─────────────────────────────────┘

6. Browser makes request to 192.168.1.16:8061
   ┌─────────────────────────────────┐
   │ Request: http://192.168.1.16:   │
   │         8061/health             │
   │                                 │
   │ Destination: Server (192.168.1. │
   │             16)                 │
   │ Port: 8061                      │
   │                                 │
   │ Path: 0.0.0.0:8061 on server    │
   │ Status: ✓ LISTENING             │
   │ Response: ✓ SUCCESS             │
   └─────────────────────────────────┘

7. Browser receives health data:
   ┌─────────────────────────────────┐
   │ {                               │
   │   "status": "ok",               │
   │   "timestamp": "2026-01-27T..." │
   │ }                               │
   └─────────────────────────────────┘

8. Dashboard displays:
   ┌─────────────────────────────────┐
   │ ✓ System Status: Healthy        │
   │ ✓ Recent Alerts: [data]         │
   │ ✓ Option Chains: [data]         │
   │ ✓ All working!                  │
   └─────────────────────────────────┘
```

---

## CORS Flow Diagram

### Before Fix (Rejected)

```
CLIENT (192.168.1.20:8060)
  │
  ├─ Browser loads frontend: ✓
  │  Origin: http://192.168.1.20:8060
  │
  └─ Browser makes API request
     To: http://192.168.1.16:8061/health
     Origin header: http://192.168.1.20:8060
     │
     ▼
SERVER (192.168.1.16:8061)
  │
  ├─ Receives request
  │  From origin: http://192.168.1.20:8060
  │
  ├─ Checks CORS allow_origins:
  │  ├─ http://localhost:8060 ✗ (doesn't match)
  │  ├─ http://127.0.0.1:8060 ✗ (doesn't match)
  │  └─ 192.168.1.20:8060 not in list ✗
  │
  ├─ Response WITHOUT CORS headers:
  │  Access-Control-Allow-Origin: (not set)
  │
  └─ Status: 200 (body sent)
     │
     ▼
BROWSER (Client)
  │
  ├─ Receives response
  │
  ├─ Checks CORS headers:
  │  ├─ Access-Control-Allow-Origin: (not present)
  │  └─ Origin not whitelisted!
  │
  ├─ BLOCKS response in JavaScript
  │  (Same-Origin Policy violation)
  │
  └─ Error in console:
     "Access to XMLHttpRequest at 'http://192.168.1.16:8061/health'
      from origin 'http://192.168.1.20:8060' has been blocked by
      CORS policy: No 'Access-Control-Allow-Origin' header is present"

USER SEES:
  "Health Check Error" or no data displayed
```

### After Fix (Allowed)

```
CLIENT (192.168.1.20:8060)
  │
  ├─ Browser loads frontend: ✓
  │  Origin: http://192.168.1.20:8060
  │
  └─ Browser makes API request
     To: http://192.168.1.16:8061/health
     Origin header: http://192.168.1.20:8060
     │
     ▼
SERVER (192.168.1.16:8061)
  │
  ├─ Receives request
  │  From origin: http://192.168.1.20:8060
  │
  ├─ Checks CORS allow_origins:
  │  ├─ "*" (wildcard) = ALLOW ALL ✓
  │  OR
  │  ├─ http://192.168.1.20:8060 ✓ (in list)
  │
  ├─ Response WITH CORS headers:
  │  Access-Control-Allow-Origin: *
  │  (OR: Access-Control-Allow-Origin: http://192.168.1.20:8060)
  │
  └─ Status: 200 + data + headers
     │
     ▼
BROWSER (Client)
  │
  ├─ Receives response
  │
  ├─ Checks CORS headers:
  │  ├─ Access-Control-Allow-Origin: * ✓ (or matching origin)
  │  └─ Origin is whitelisted! ✓
  │
  ├─ ALLOWS response in JavaScript
  │
  └─ No errors in console

USER SEES:
  ✓ Health check passes
  ✓ Data displayed properly
```

---

## Configuration Changes Required

```
BEFORE (Current - Broken)
├─ scripts/run_api.py
│  └─ allow_origins=[
│        "http://localhost:8060",
│        "127.0.0.1:8060"
│     ]  ✗ No remote IPs
│
├─ frontend/.env
│  └─ VITE_API_BASE_URL=http://localhost:8061  ✗ Hardcoded
│
└─ frontend/src/utils/constants.ts
   └─ WEBSOCKET: 'ws://localhost:8061/ws'  ✗ Hardcoded

                              │
                              │ Apply fixes
                              ▼

AFTER (Fixed - Working)
├─ scripts/run_api.py
│  └─ allow_origins=[
│        "http://localhost:8060",
│        "127.0.0.1:8060",
│        "http://192.168.1.16:8060"  ✓ Add your IP
│     ]
│
├─ frontend/.env
│  └─ VITE_API_BASE_URL=http://192.168.1.16:8061  ✓ Use real IP
│
└─ frontend/src/utils/constants.ts
   └─ WEBSOCKET: dynamic (based on API_BASE_URL)  ✓ Dynamic
```

---

## Component Dependencies

```
Dashboard Component
│
├─ useHealthCheckIntegration()
│  └─ useHealthCheck()
│     └─ useApi('/health')
│        └─ apiClient.get()
│           └─ axios
│              └─ http://[API_BASE_URL]/health
│                 └─ CORS must allow origin
│                    └─ API must be running
│
├─ useLatestAlertsIntegration()
│  └─ useLatestAlerts()
│     └─ useApi('/alerts/latest')
│        └─ apiClient.get()
│           └─ http://[API_BASE_URL]/alerts/latest
│
├─ useTriggerScanIntegration()
│  └─ useTriggerScan()
│     └─ useApiPost('/scan/run')
│        └─ apiClient.post()
│           └─ http://[API_BASE_URL]/scan/run
│
└─ [All other features]
   └─ Depend on same chain:
      API_BASE_URL → CORS → API running

Where API_BASE_URL = import.meta.env.VITE_API_BASE_URL
Default fallback: 'http://localhost:8061'
```

---

## Database Lock Issue

```
Process holding lock:
  PID: 563181
  Command: /usr/bin/python3.12
  Holding: /data/cache.db
  Acquired: [timestamp from logs]

Why it blocks API:
  1. FastAPI tries to start
  2. Calls: from functions.db.connection import init_db
  3. init_db() tries to open cache.db
  4. DuckDB sees existing lock
  5. Throws error: "Could not set lock"
  6. API startup fails
  7. Process exits
  8. Port 8061 never opens

Solution:
  1. Identify owner of PID 563181
     ps -p 563181

  2. If it's scheduler stuck:
     kill -9 563181

  3. Or restart main.py to clean up:
     pkill -f "main.py"

  4. Then start API again:
     python scripts/run_api.py
```

---

## Status Summary Table

```
┌─────────────────┬──────────┬────────────────┬──────────────┐
│ Component       │ Current  │ Required       │ Status       │
├─────────────────┼──────────┼────────────────┼──────────────┤
│ Frontend on     │ Working  │ 0.0.0.0:8060   │ ✓ OK         │
│ 8060            │ ✓        │                │              │
├─────────────────┼──────────┼────────────────┼──────────────┤
│ API on 8061     │ NOT      │ 0.0.0.0:8061   │ ✗ CRITICAL   │
│ (running)       │ RUNNING  │                │ (DB locked)  │
├─────────────────┼──────────┼────────────────┼──────────────┤
│ API CORS        │ localhost│ IP list or     │ ✗ NEEDS FIX  │
│ whitelist       │ only     │ wildcard       │ (excludes    │
│                 │          │                │ remote IPs)  │
├─────────────────┼──────────┼────────────────┼──────────────┤
│ Frontend API    │ localhost│ Real IP        │ ✗ NEEDS FIX  │
│ base URL        │ hardcoded│ (192.168.1.16) │ (hardcoded)  │
├─────────────────┼──────────┼────────────────┼──────────────┤
│ WebSocket URL   │ localhost│ Dynamic or     │ ✗ NEEDS FIX  │
│                 │ hardcoded│ real IP        │ (hardcoded)  │
├─────────────────┼──────────┼────────────────┼──────────────┤
│ Demo mode       │ True     │ Toggleable via │ ✗ NEEDS FIX  │
│ toggle          │ hardcoded│ API + UI       │ (no toggle)  │
└─────────────────┴──────────┴────────────────┴──────────────┘
```

---

**For implementation details, see: CONNECTIVITY_FIX_CHECKLIST.md**
**For technical analysis, see: CONNECTIVITY_ANALYSIS.md**
