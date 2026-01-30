# Issue #16 Analysis: Alert Feed Page Issues

**Issue**: Alert Feed page: unreadable date range and repeated network errors

**Branch**: feature/issue-16-alert-feed-date-range-errors

**Status**: Analyzing

---

## Problem Overview

The Alert Feed page has 2 critical issues:

1. **Unreadable date range selector** - White text on white background makes date range controls invisible
2. **Repeated network errors** - Alerts fail to load with "network error" despite backend being accessible

---

## Root Cause Analysis

### Issue 1: Unreadable Date Range Selector

**File**: `frontend/src/pages/AlertFeed.tsx` (line 243-259)

```jsx
<div>
  <label className="block text-sm font-medium text-gray-700 mb-2">
    Date Range
  </label>
  <select
    value={filters.dateRange}
    onChange={(e) => setFilters(prev => ({
      ...prev,
      dateRange: e.target.value as DateRange
    }))}
    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none bg-white"
  >
```

**Problem**:
- Select element has `bg-white` but no explicit `text-color`
- Browser may default to white text in some themes/browsers
- No `text-gray-900` or similar explicitly set
- Doesn't specify option colors for dropdown

**Similar Issue**: Custom date range labels (lines 266, 280) also lack explicit text color

### Issue 2: Repeated Network Errors

**File**: `frontend/src/pages/AlertFeed.tsx` (line 57)

```typescript
const { alerts, loading, error, refetch } = useLatestAlertsIntegration(200)
```

**Possible causes:**
1. Fetching 200 alerts at once might exceed API timeout
2. JSON file loading on backend (`run_api.py`) is slow for large alert files
3. Network error not being caught properly - missing error handling
4. Error state never clears even after successful retry

**File**: `frontend/src/hooks/useApiIntegration.ts` (lines 51-70)

Integration hook doesn't handle retry logic properly - just exposes raw error.

---

## Solution Approach

### Fix 1: Fix Date Range Selector Colors

- Add explicit `text-gray-900` to all text inputs and selects
- Add explicit `text-gray-900` to all select options
- Add explicit color to date inputs

### Fix 2: Improve Alerts Loading

- Reduce default limit from 200 to 50 (more reasonable)
- Add retry button with exponential backoff
- Add timeout indicator
- Improve error messaging

### Fix 3: Add Automatic Retry

- Auto-retry once on network error
- Show retry button if manual retry needed
- Clear error state before retry

---

## Implementation Plan

### Phase 1: Fix UI Colors

Update all input/select elements:
- Add `text-gray-900` to text color
- Add `placeholder-gray-500` for placeholders
- Add explicit option coloring

### Phase 2: Improve Error Handling

- Increase fetch limit gradually (start with 50)
- Add retry button
- Add "Retrying..." state
- Clear error on retry

### Phase 3: Add Better Error Messages

- Distinguish between timeout vs connection error
- Show helpful suggestions
- Add retry interval

---

## Expected Outcomes

After fixes:
1. ✅ Date range controls are readable in all themes
2. ✅ Alerts load without repeated network errors
3. ✅ Meaningful error messages if network issue
4. ✅ Retry mechanism works properly
5. ✅ Error clears after successful load

