# Hybrid Approach Testing Guide

## Quick Start - Testing the Implementation

### Prerequisites
```bash
cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard
source venv/bin/activate  # Activate Python environment
```

### Test 1: Verify JSON Export Module Loads
```bash
python3 -c "from functions.export import JSONExporter; print('✓ JSONExporter imported successfully')"
```

### Test 2: Start Scheduler and Verify Exports
**Terminal 1 - Start Scheduler**:
```bash
python3 -m scripts.scheduler_engine
```

Watch for logs like:
```
INFO: SchedulerEngine initialized: export_interval=300s
INFO: Exporting collected data to JSON...
INFO: Data export completed successfully
```

**Terminal 2 - Check JSON files are created**:
```bash
# Wait 30 seconds for first export
sleep 30
ls -lh data/exports/
cat data/exports/alerts.json | head -20
```

Expected output:
```
-rw-r--r-- alerts.json    (contains { "export_timestamp": "...", "alerts": [...] })
-rw-r--r-- chains.json    (contains { "export_timestamp": "...", "chains": [...] })
-rw-r--r-- scans.json     (contains { "export_timestamp": "...", "scans": [...] })
-rw-r--r-- features.json  (contains { "export_timestamp": "...", "features": [...] })
```

### Test 3: Start API While Scheduler is Running
**Terminal 3 - Start API** (while scheduler is still running in Terminal 1):
```bash
python3 scripts/run_api.py
```

Expected: API starts successfully WITHOUT database lock errors!

Previously would fail with:
```
Error: "Could not set lock on database... Conflicting lock"
```

Now should see:
```
INFO: Starting Option Chain Dashboard API server...
INFO: Startup completed successfully
```

### Test 4: Test API Endpoints Read from JSON

**Terminal 4 - Test endpoints**:
```bash
# Get latest alerts from JSON (not database)
curl -s http://localhost:8061/alerts/latest?limit=5 | python3 -m json.tool | head -30

# Get alerts for specific ticker
curl -s "http://localhost:8061/alerts?ticker=AAPL" | python3 -m json.tool | head -20

# Get latest scans
curl -s http://localhost:8061/scans/latest | python3 -m json.tool | head -20

# Get options snapshot
curl -s "http://localhost:8061/options/AAPL/snapshot" | python3 -m json.tool | head -20

# Get features
curl -s "http://localhost:8061/features/AAPL/latest" | python3 -m json.tool | head -20
```

All should return data from JSON without database lock!

### Test 5: Verify Periodic Exports Work
Monitor scheduler logs for periodic exports:
```bash
tail -f logs/option_chain_dashboard.log | grep "Periodic export"
```

Should see:
```
INFO: Periodic export triggered (305s since last export)
INFO: Data export completed successfully
```

### Test 6: Verify Archives Are Created
Check for timestamped archives:
```bash
ls -lh data/exports/archive/
```

Expected structure:
```
alerts_20260127_120000.json     (timestamp when exported)
chains_20260127_120000.json
scans_20260127_120000.json
features_20260127_120000.json
alerts_20260127_120500.json     (next 5-minute export)
...
```

### Test 7: Graceful Handling of Missing Data

**Terminal 3** (API still running):
```bash
# Request ticker with no data - should return empty, not error
curl -s "http://localhost:8061/alerts/ticker/NONEXISTENT" | python3 -m json.tool
# Expected: { "alerts": [], "total_count": 0, "timestamp": "..." }

# Request features for missing ticker - should return empty
curl -s "http://localhost:8061/features/NONEXISTENT/latest" | python3 -m json.tool
# Expected: { "ticker": "NONEXISTENT", "features": {}, "timestamp": "..." }

# Options snapshot for missing ticker
curl -s "http://localhost:8061/options/NONEXISTENT/snapshot" | python3 -m json.tool
# Expected: { "ticker": "NONEXISTENT", "calls": [], "puts": [], ... }
```

## Concurrent Execution Test

### Test 8: Verify Scheduler and API Can Run Together

**Terminal 1**: Scheduler running (Step 2)
**Terminal 3**: API running (Step 3)
**Terminal 4**: Continuously query API (Step 4)

```bash
# Run continuous API requests while scheduler is exporting
while true; do
    echo "=== $(date) ==="
    curl -s http://localhost:8061/alerts/latest?limit=3 | python3 -m json.tool | head -5
    echo ""
    sleep 5
done
```

**Expected behavior**:
- API returns data every 5 seconds
- No database lock errors
- Scheduler continues running in Terminal 1
- Both are truly running simultaneously

If either fails, check logs for errors.

## Troubleshooting

### Problem: JSON files not created

**Check**:
1. Is scheduler still running? (check Terminal 1)
2. Are there any errors in scheduler logs?
   ```bash
   tail -20 logs/option_chain_dashboard.log | grep -i error
   ```
3. Check directory permissions:
   ```bash
   ls -ld data/exports/
   chmod 755 data/exports
   ```

### Problem: API returns empty results

**Check**:
1. Are JSON files being created?
   ```bash
   ls -lh data/exports/*.json
   ```
2. Are the JSON files being updated?
   ```bash
   stat data/exports/alerts.json | grep Modify
   ```
3. Check file contents:
   ```bash
   python3 -c "import json; f=json.load(open('data/exports/alerts.json')); print(f'Alerts: {len(f.get(\"alerts\", []))}')"
   ```

### Problem: API still gets database lock

**Diagnose**:
```bash
# Check for open DuckDB connections
lsof | grep cache.db

# Or kill existing processes
pkill -f "scheduler_engine\|run_api"
sleep 2

# And restart fresh
```

## Performance Validation

### Test 9: Measure Response Times

**JSON-based API (current)**:
```bash
time curl -s http://localhost:8061/alerts/latest?limit=100 > /dev/null
# Expected: < 50ms
```

**Compare to Database-based** (if you want to test old way):
```bash
# Would need to temporarily revert API to use database
# Expected: 100-200ms (with network overhead)
```

### Test 10: Load Testing

```bash
# Install Apache Bench if not available
# apt-get install apache2-utils

# Test alerts endpoint under load
ab -n 1000 -c 10 http://localhost:8061/alerts/latest?limit=50

# Expected: High throughput with < 50ms average response time
```

## Data Validation

### Test 11: Verify Data Structure

```bash
python3 << 'EOF'
import json
from pathlib import Path

export_dir = Path("data/exports")

# Check alerts.json structure
with open(export_dir / "alerts.json") as f:
    alerts_data = json.load(f)
    print(f"Alerts export keys: {list(alerts_data.keys())}")
    if alerts_data.get("alerts"):
        print(f"Sample alert: {alerts_data['alerts'][0]}")

# Check chains.json structure
with open(export_dir / "chains.json") as f:
    chains_data = json.load(f)
    print(f"Chains export keys: {list(chains_data.keys())}")
    if chains_data.get("chains"):
        print(f"Sample chain: {chains_data['chains'][0]}")

# Check export timestamps are recent
print(f"\nExport timestamps:")
for file in export_dir.glob("*.json"):
    if file.name != ".gitkeep":
        data = json.load(open(file))
        print(f"  {file.name}: {data.get('export_timestamp', 'N/A')}")
EOF
```

## Cleanup Between Tests

```bash
# Stop all running processes
pkill -f "scheduler_engine\|run_api"

# Clear old exports (optional)
rm -f data/exports/*.json

# Restart fresh
```

## Success Checklist

- [ ] Scheduler starts without errors
- [ ] API starts while scheduler is running (no lock errors)
- [ ] JSON files created in `data/exports/`
- [ ] Timestamped archives created
- [ ] `/alerts/latest` returns data from JSON
- [ ] `/scans/latest` returns data from JSON
- [ ] `/options/{ticker}/snapshot` returns data
- [ ] `/features/{ticker}/latest` returns data
- [ ] Missing tickers return empty gracefully
- [ ] Periodic exports happen every 5 minutes
- [ ] Both scheduler and API run simultaneously
- [ ] API response times < 50ms

## Advanced Testing

### Monitor JSON File Updates
```bash
# Watch when files get updated
watch -n 1 'ls -lh data/exports/*.json'

# Or use find with mmin
find data/exports -name "*.json" -mmin -1  # Modified in last minute
```

### Tail Both Scheduler and API Logs
```bash
# Terminal 1: Scheduler
tail -f logs/option_chain_dashboard.log | grep "Scheduler\|Exporting\|export"

# Terminal 2: API (separate terminal if logging enabled)
tail -f logs/option_chain_dashboard.log | grep "GET\|alerts\|json"
```

## Regression Testing

If you later refactor, verify:
1. All endpoints still work
2. JSON structure unchanged
3. Export frequency preserved
4. Archives still created
5. Scheduler and API still concurrent
