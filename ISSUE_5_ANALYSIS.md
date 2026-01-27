# Issue #5 Analysis: Config Loading + CLI Wiring Inconsistent

**Status**: Analyzing
**Branch**: feature/issue-5-config-wiring
**Issue**: #5 - Config loading + CLI wiring inconsistent (watchlist, scheduler, risk keys; --config-path ignored)

---

## Problem Overview

Configuration loading has multiple issues:

1. **Singleton pattern ignores config_dir parameter after first initialization**
   - `--config-path` argument in run_scan.py is ignored if config manager already initialized elsewhere
   - Causes inconsistent configuration across multiple entry points

2. **Config key mappings are incomplete or missing**
   - Scheduler settings: max_calls_per_hour, max_calls_per_day, etc. not consistently mapped
   - Risk settings: key name mismatches (max_margin_usage_pct vs margin_gate_threshold_pct)
   - Watchlist loading logic is fragmented across multiple methods

3. **CLI argument parsing inconsistent across scripts**
   - run_scan.py has --config-path but doesn't handle it properly
   - Other scripts don't have consistent argument handling
   - No validation of config_dir parameter

4. **Singleton instance never resets**
   - Once created, ConfigManager._instance is permanent
   - No way to switch configuration directory at runtime
   - Makes testing and multi-tenant scenarios impossible

---

## Root Cause Analysis

### Issue 1: Singleton Pattern Flaw

**File**: `functions/config/loader.py` (lines 67-80)

The `get_instance()` method only passes `config_dir` to the constructor on the FIRST call:

```python
@classmethod
def get_instance(cls, config_dir: Optional[Path] = None) -> "ConfigManager":
    if cls._instance is None:
        cls._instance = cls(config_dir)  # ❌ Ignored on subsequent calls
    return cls._instance
```

**Impact**:
- First call: `get_config_manager(config_dir="/custom")` → creates singleton with /custom
- Second call: `get_config_manager(config_dir="/different")` → returns existing singleton (ignores parameter)
- Result: CLI `--config-path` is silently ignored if config already loaded

### Issue 2: Config Key Mapping Issues

**File**: `functions/config/loader.py` (lines 144-163)

Inconsistent key mappings create confusion:

**Scheduler Settings**:
```python
for key in ["max_calls_per_hour", "max_calls_per_day", "flush_threshold", "check_interval_sec"]:
    if value := scheduler_cfg.get(key):
        config_data[key] = value  # Maps to top-level
```

**Risk Settings** with renaming:
```python
# Config file uses one name, code expects another:
"max_margin_usage_pct" → config_data["margin_gate_threshold_pct"]  # ❌ Renamed!
"min_cash_buffer_pct" → config_data["cash_gate_threshold_pct"]    # ❌ Renamed!
```

This renaming is confusing and error-prone.

### Issue 3: Watchlist Loading Fragmentation

**File**: `functions/config/loader.py` (lines 131-142)

Two separate sources with unclear precedence:

1. `config.yaml` watchlist section
2. `watchlist.txt` file

No clear documentation of which takes precedence or what happens if both/neither exist.

### Issue 4: CLI Arguments Ignored

**File**: `scripts/run_scan.py` (lines 604-639)

Even though `--config-path` is parsed and passed to `get_config_manager()`, the singleton pattern ignores it:

```python
parser.add_argument("--config-path", type=str, default="./")
args = parser.parse_args()
config_manager = get_config_manager(config_dir=Path(args.config_path))
# ❌ If ConfigManager already created elsewhere, this parameter is ignored!
```

---

## Solution Approach

### Fix 1: Improve Singleton Pattern
- Add `ConfigManager.reset()` class method for testing/reinitialization
- Warn if config_dir parameter is ignored due to existing singleton
- Validate config_dir exists on first call
- Document singleton behavior clearly

### Fix 2: Standardize Key Mappings
- Create explicit mapping table in code
- Remove confusing renaming (use consistent names)
- Add validation that all required keys exist
- Document all mapped keys in docstrings

### Fix 3: Improve CLI Handling
- Ensure --config-path is actually used
- Add validation that config directory exists
- Add --watchlist-file CLI parameter
- Add helpful error messages

### Fix 4: Improve Testing
- Add tests for singleton reset
- Test that config_dir parameter is honored
- Test watchlist loading precedence
- Test error cases

---

## Implementation Phases

### Phase 1: Fix Singleton Pattern (THIS)
- [ ] Add ConfigManager.reset() class method
- [ ] Add warning if config_dir ignored
- [ ] Validate config_dir exists
- [ ] Document singleton behavior

### Phase 2: Standardize Key Mappings
- [ ] Create mapping table
- [ ] Rename inconsistent keys
- [ ] Add validation
- [ ] Document all keys

### Phase 3: Improve CLI
- [ ] Update run_scan.py to handle --config-path properly
- [ ] Add --watchlist-file parameter
- [ ] Add config directory validation
- [ ] Add helpful error messages

### Phase 4: Add Tests
- [ ] Unit tests for singleton reset
- [ ] Tests for config_dir parameter
- [ ] Tests for watchlist precedence
- [ ] Error case tests

---

## Expected Outcomes

After all fixes:
1. ✅ `--config-path` argument in run_scan.py actually works
2. ✅ ConfigManager can be reset for testing/runtime switching
3. ✅ Config keys have consistent naming and clear mappings
4. ✅ Watchlist loading has documented, predictable behavior
5. ✅ Clear error messages when config issues occur
