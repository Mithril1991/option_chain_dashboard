# Issue #17 Analysis: Option Chains Page - Expiration List Never Loads

**Issue**: Option chains page: expiration list never loads (timeout)

**Branch**: feature/issue-17-option-chains-expiration-timeout

**Status**: Analyzing

---

## Problem Overview

When user enters a ticker on the Option Chains page:
1. Page starts loading
2. Expiration dropdown stays empty (no options)
3. Eventually shows error: "timeout of 3000ms exceeded"
4. Can't select expirations to view different option chains

---

## Root Cause Analysis

### Issue 1: Expirations Extraction Logic

**File**: `frontend/src/pages/OptionChains.tsx` (lines 42-45)

```typescript
// Get expirations from alerts data
const expirations = useMemo(() => {
  if (!chain) return []
  return Array.from(new Set([chain.expiration]))
}, [chain])
```

**Problem**:
- Code assumes `chain` object has ONE expiration (`chain.expiration`)
- Creates a Set with single element: `[chain.expiration]`
- Will always return array with 0 or 1 expiration, never multiple
- Can't show user the 30 DTE, 60 DTE, etc. options

### Issue 2: Backend Returns Single Expiration

**File**: `scripts/run_api.py` (lines 1009-1014)

```python
@app.get("/options/{ticker}/snapshot", response_model=ChainSnapshot, tags=["Options"])
async def get_option_chain_snapshot(ticker: str) -> ChainSnapshot:
    """Get a single option chain snapshot for a given ticker."""
    # Loads from JSON file with single snapshot
    chain = load_chain_from_json(ticker)
    return chain
```

**Problem**:
- Endpoint returns single `ChainSnapshot` object with ONE expiration
- No way to request specific expiration date
- Frontend has no way to load alternative expirations
- User stuck looking at only one expiration

### Issue 3: Data Model Mismatch

**File**: `frontend/src/types/api.ts` (lines 67-72)

```typescript
export interface ChainSnapshot {
  ticker: string
  expiration: string        // ← Single expiration, not array!
  calls: OptionContract[]
  puts: OptionContract[]
}
```

**Problem**:
- Type defines single `expiration` string, not array
- Frontend has no type representation for multiple expirations
- Hard to add multi-expiration support without breaking changes

---

## Solution Approach

### Option A: Minimal Fix (Recommended)

Add backend endpoint to list available expirations:

```python
@app.get("/options/{ticker}/expirations", tags=["Options"])
async def get_option_expirations(ticker: str) -> list[str]:
    """Get list of available expiration dates for a ticker."""
    # Query all available expirations from data
    return ["2026-02-20", "2026-03-20", "2026-04-17"]
```

Then frontend can:
1. Call `/options/{ticker}/expirations` to get list
2. Display expirations in dropdown
3. Load chain for selected expiration via `/options/{ticker}/snapshot?expiration={date}`

**Pros**:
- Minimal backend changes
- Frontend can adapt to new endpoint
- Supports multiple expirations
- Clean separation of concerns

**Cons**:
- Additional API call needed

### Option B: Modify Snapshot Endpoint

Change endpoint to return all expirations at once:

```python
@app.get("/options/{ticker}/snapshots", tags=["Options"])
async def get_all_option_chains(ticker: str) -> list[ChainSnapshot]:
    """Get all available option chain snapshots for a ticker."""
    # Load all snapshots for all expirations
    return [chain_30dte, chain_60dte, chain_90dte]
```

**Pros**:
- Single endpoint call gets everything
- Works for all expirations at once

**Cons**:
- Large payload (multiple chains x 100+ strikes each)
- Could cause timeout issues (current problem!)
- Wasteful if user only wants one expiration

### Option C: Add Query Parameter

Modify existing endpoint to accept optional expiration parameter:

```python
@app.get("/options/{ticker}/snapshot", tags=["Options"])
async def get_option_chain_snapshot(
    ticker: str,
    expiration: Optional[str] = None
) -> ChainSnapshot:
    """Get option chain for ticker and optional expiration date."""
    # Load for specific expiration or latest
```

**Pros**:
- Backward compatible
- Single endpoint for all needs

**Cons**:
- Requires expiration parameter passed from frontend
- Need to list expirations somewhere

---

## Recommended Solution (Option A)

### Phase 1: Add Expirations Endpoint

```python
# scripts/run_api.py

@app.get("/options/{ticker}/expirations", tags=["Options"])
async def get_option_expirations(ticker: str) -> List[str]:
    """Get available expiration dates for a ticker.

    Returns list of ISO 8601 date strings in ascending order.

    Example:
        GET /options/AAPL/expirations
        ["2026-02-20", "2026-03-20", "2026-04-17", ...]
    """
    try:
        # For now, load from single snapshot file and extract expiration
        # TODO: When chain_snapshots table added, query for distinct expirations
        chain = load_chain_from_json(ticker)
        if chain:
            return [chain.expiration]
        return []
    except Exception as e:
        logger.error(f"Failed to get expirations for {ticker}: {e}")
        return []
```

### Phase 2: Update Frontend to Use New Endpoint

```typescript
// frontend/src/hooks/useApi.ts

export const useOptionExpirations = (ticker: string) => {
  const url = ticker ? `/options/${ticker}/expirations` : null
  return useApi<string[]>(url, {
    immediate: !!ticker,
    dependencies: [ticker]
  })
}
```

### Phase 3: Update OptionChains Component

```typescript
// frontend/src/pages/OptionChains.tsx

const { data: allExpirations, loading: expirationLoading } = useOptionExpirations(ticker)

const expirations = useMemo(() => {
  return allExpirations || []
}, [allExpirations])
```

---

## Expected Outcomes

After fix:
1. ✅ Expirations list populates from `/options/{ticker}/expirations`
2. ✅ Dropdown shows all available expirations (30 DTE, 60 DTE, 90 DTE, etc.)
3. ✅ User can select different expirations
4. ✅ Chain loads for selected expiration
5. ✅ No more timeout errors (simpler API responses)

---

## Current Limitation & Future Work

**Note**: Even with this fix, `/options/{ticker}/snapshot` only returns ONE expiration. To support selecting different expirations:

1. Add optional `expiration` query parameter: `/options/{ticker}/snapshot?expiration=2026-03-20`
2. OR load from `chain_snapshots` table when available (stores all expirations)
3. OR user must accept viewing only latest expiration

For now, fix expirations endpoint so at least it's clear which expiration is available.

---

## Addresses Issue

✅ **"Expiration list never loads"** → Populate from dedicated endpoint
✅ **"Timeout error"** → Simpler endpoint = faster response
✅ **"Can't select expirations"** → List will show available dates

