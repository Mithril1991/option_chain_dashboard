# Issue #7 Analysis: Frontend/Backend API Contract Mismatch

**Status**: Analyzing
**Branch**: fix/issue-7-api-contract-mismatch
**Issue**: #7 - Frontend/Backend API contract mismatch (routes, payload shape, score scale)

---

## Problem Overview

The frontend (React/TypeScript) and backend (FastAPI/Python) have mismatched API contracts, causing type errors and integration failures. The mismatch affects:

1. **AlertResponse structure** - Field name and missing fields
2. **OptionContract structure** - Field name casing (snake_case vs camelCase)
3. **ChainSnapshotResponse** - Extra fields and nested structure issues
4. **Score scale interpretation** - Potential range mismatch (0-100 vs 0-1)

---

## Detailed Mismatches

### Issue 1: AlertResponse Structure Mismatch

**File**: `frontend/src/types/api.ts` (lines 34-43)

**Frontend expects**:
```typescript
interface AlertResponse {
  id: number
  ticker: string
  detector_name: string
  score: number
  metrics: Record<string, unknown>
  explanation: Record<string, unknown>
  strategies: string[]
  created_at: string
}
```

**File**: `scripts/run_api.py` (lines 332-341)

**Backend returns**:
```python
class AlertResponse(BaseModel):
    id: int
    scan_id: int              # ❌ Extra field - frontend doesn't expect
    ticker: str
    detector_name: str
    score: float
    alert_data: Dict[str, Any]  # ❌ Wrong name: should be "metrics"
    created_at: str
    # ❌ Missing: explanation, strategies
```

**Mismatches**:
| Field | Frontend | Backend | Status |
|-------|----------|---------|--------|
| `id` | ✅ | ✅ | Matches |
| `ticker` | ✅ | ✅ | Matches |
| `detector_name` | ✅ | ✅ | Matches |
| `score` | ✅ | ✅ | Matches |
| `metrics` | ✅ Expected | ❌ Returns `alert_data` | **MISMATCH** |
| `explanation` | ✅ Expected | ❌ Not provided | **MISSING** |
| `strategies` | ✅ Expected | ❌ Not provided | **MISSING** |
| `created_at` | ✅ | ✅ | Matches |
| `scan_id` | ❌ Not expected | ✅ | **EXTRA** |

**Impact**: Frontend TypeScript errors when accessing `alert.metrics`, `alert.explanation`, `alert.strategies`

---

### Issue 2: OptionContract Structure Mismatch (Field Name Casing)

**File**: `frontend/src/types/api.ts` (lines 48-62)

**Frontend expects (camelCase)**:
```typescript
interface OptionContract {
  strike: number
  bid: number
  ask: number
  lastPrice: number
  volume: number
  openInterest: number
  impliedVolatility: number
  delta: number
  gamma: number
  vega: number
  theta: number
  rho?: number
  expirationDate: string
}
```

**File**: `scripts/run_api.py` (lines 352-366)

**Backend returns (snake_case)**:
```python
class OptionContractResponse(BaseModel):
    strike: float
    option_type: str                # ❌ Extra field
    bid: float
    ask: float
    volume: int
    open_interest: int              # ❌ Should be openInterest
    implied_volatility: float       # ❌ Should be impliedVolatility
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    # ❌ Missing: lastPrice, expirationDate
```

**Mismatches**:
| Field | Frontend | Backend | Status |
|-------|----------|---------|--------|
| `strike` | ✅ | ✅ | Matches |
| `bid` | ✅ | ✅ | Matches |
| `ask` | ✅ | ✅ | Matches |
| `lastPrice` | ✅ Expected | ❌ Not provided | **MISSING** |
| `volume` | ✅ | ✅ | Matches |
| `openInterest` | ✅ camelCase | ❌ `open_interest` (snake_case) | **MISMATCH** |
| `impliedVolatility` | ✅ camelCase | ❌ `implied_volatility` (snake_case) | **MISMATCH** |
| `delta` | ✅ | ✅ | Matches |
| `gamma` | ✅ | ✅ | Matches |
| `theta` | ✅ | ✅ | Matches |
| `vega` | ✅ | ✅ | Matches |
| `rho` | ✅ Optional | ✅ Optional | Matches |
| `expirationDate` | ✅ Expected | ❌ Not provided | **MISSING** |
| `option_type` | ❌ Not expected | ✅ | **EXTRA** |

**Impact**: Frontend TypeScript errors: `Property 'openInterest' does not exist on type 'OptionContract'`

---

### Issue 3: ChainSnapshotResponse Structure Mismatch

**File**: `frontend/src/types/api.ts` (lines 67-72)

**Frontend expects**:
```typescript
interface ChainSnapshot {
  ticker: string
  expiration: string
  calls: OptionContract[]
  puts: OptionContract[]
}
```

**File**: `scripts/run_api.py` (lines 369-377)

**Backend returns**:
```python
class ChainSnapshotResponse(BaseModel):
    ticker: str
    timestamp: str                    # ❌ Extra field
    underlying_price: float          # ❌ Extra field
    expiration: str
    calls: List[OptionContractResponse]  # ❌ Contains snake_case fields
    puts: List[OptionContractResponse]   # ❌ Contains snake_case fields
```

**Mismatches**:
| Field | Frontend | Backend | Status |
|-------|----------|---------|--------|
| `ticker` | ✅ | ✅ | Matches |
| `expiration` | ✅ | ✅ | Matches |
| `calls` | ✅ | ✅ (but wrong structure) | **NESTED MISMATCH** |
| `puts` | ✅ | ✅ (but wrong structure) | **NESTED MISMATCH** |
| `timestamp` | ❌ Not expected | ✅ | **EXTRA** |
| `underlying_price` | ❌ Not expected | ✅ | **EXTRA** |

**Impact**: Cascading failure due to OptionContract mismatches in nested arrays

---

### Issue 4: Score Scale

**File**: `scripts/run_api.py` (line 1033)

**Backend Implementation**:
```python
min_score: float = Query(0, ge=0, le=100, description="Minimum alert score")
```

**Backend returns**: Score 0-100 range

**Frontend expectation**: Treats score as a number (no explicit range validation)

**Status**: ⚠️ Unclear if frontend expects 0-100 or 0-1. Backend uses 0-100, frontend doesn't validate, so likely OK but should verify.

---

## Root Causes

1. **Different naming conventions**: Backend uses Python snake_case, frontend expects TypeScript camelCase
2. **No type synchronization**: Backend Pydantic models and frontend TypeScript interfaces developed independently
3. **Extra fields in responses**: Backend includes `scan_id`, `timestamp`, `underlying_price`, `option_type` that frontend doesn't use
4. **Missing fields in responses**: Backend doesn't extract `explanation`, `strategies`, `lastPrice`, `expirationDate` from alert data
5. **Incomplete OptionContract data**: Backend doesn't include price/expiration info needed by frontend

---

## Solution Strategy

### Approach: Transform in Backend Responses

Rather than changing the database/business logic, transform responses to match frontend contract:

1. **AlertResponse**: Map `alert_data` to `metrics`, extract `explanation` and `strategies` from alert data
2. **OptionContractResponse**: Add camelCase field names, compute/include `lastPrice`, include `expirationDate`
3. **ChainSnapshotResponse**: Remove extra fields, ensure nested contracts match

### Implementation Steps

1. Update `AlertResponse` Pydantic model to match frontend contract
2. Update `OptionContractResponse` to use camelCase and include missing fields
3. Update all endpoints that return these types to transform data appropriately
4. Add tests to verify response structure matches frontend expectations

---

## Files to Modify

### Backend (Python)

1. **scripts/run_api.py** - Update Pydantic response models:
   - `AlertResponse` class (lines 332-341)
   - `OptionContractResponse` class (lines 352-366)
   - `ChainSnapshotResponse` class (lines 369-377)
   - Alert endpoints to extract `explanation` and `strategies`
   - Options endpoints to add camelCase fields

2. **functions/db/repositories.py** - Possibly update if alert data storage needs changes

### Frontend (TypeScript)

- No changes needed if backend properly conforms to existing contract

---

## Testing Plan

### Unit Tests
- Test AlertResponse transformation extracts correct fields
- Test OptionContractResponse camelCase fields present
- Test missing fields are computed/provided

### Integration Tests
- Call `/alerts/latest` and verify response structure
- Call `/options/{ticker}/snapshot` and verify response structure
- Parse response as frontend `AlertResponse` type
- Parse response as frontend `OptionContract` type

### Type Safety
- Frontend should compile with no TypeScript errors
- All response types should match frontend interfaces exactly

---

## Implementation Order

1. Analyze alert data structure to understand how to extract `explanation` and `strategies`
2. Update `AlertResponse` model
3. Update alert endpoint handlers to transform data
4. Update `OptionContractResponse` with camelCase and missing fields
5. Update chain snapshot endpoints
6. Add contract validation tests
7. Create PR with comprehensive documentation

---

## Next Steps

1. Read alert data structure to understand nested JSON
2. Understand strategies format in alert data
3. Implement transformations in FastAPI response constructors
4. Test endpoints with actual data
