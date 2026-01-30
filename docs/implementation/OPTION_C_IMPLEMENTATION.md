# Option C: JSON Export Implementation

## Overview

This document describes the implementation of **Option C: JSON Export for DuckDB Concurrency Resolution** in the Option Chain Dashboard.

## Problem Statement

The scheduler and API both need to access the DuckDB database simultaneously:
- **Scheduler** needs to write alerts, chain snapshots, scans, and features continuously
- **API** needs to read the same data to serve requests

DuckDB does not support concurrent access from multiple processes, resulting in lock contention and "Could not set lock" errors.

## Solution: Hybrid Approach (Option C)

Instead of fighting DuckDB's concurrency limitations, we work around them by:

1. **Scheduler writes to database** (exclusive lock during brief writes)
2. **Scheduler periodically exports to JSON** (every 5-10 minutes)
3. **API reads from JSON files** instead of database (no locks needed)
4. **Database acts as source of truth**, JSON files as read-only cache

This solves concurrency while maintaining data integrity and consistency.

## Implementation Details

### Core Components

#### 1. JSON Exporter Module (`functions/export/json_exporter.py`)

**Responsibility**: Export data from database to JSON files

**Key Features**:
- `JSONExporter` class with methods for each data type
- Atomic writes (write to temp file, then rename for safety)
- Timestamped archives in `data/exports/archive/` for historical tracking
- Latest exports in `data/exports/` for API to read
- Full error handling and logging

**Methods**:
```python
export_alerts(min_score: float = 0.0) -> Dict[str, Any]
export_chains(limit: int = 1000) -> Dict[str, Any]
export_scans(days: int = 30) -> Dict[str, Any]
export_features(limit: int = 10000) -> Dict[str, Any]
export_all() -> Dict[str, Dict[str, Any]]
```

**Data Files Created**:
- `data/exports/alerts.json` - Latest alerts
- `data/exports/chains.json` - Recent chain snapshots
- `data/exports/scans.json` - Scan history
- `data/exports/features.json` - Computed features
- `data/exports/archive/` - Timestamped backups

#### 2. Scheduler Integration (`scripts/scheduler_engine.py`)

**Responsibility**: Periodically trigger exports during normal operation

**Integration Points**:
- After data collection/flush phase
- Every 5-10 minutes (configurable)
- Before transitioning to next state

**Code Integration**:
```python
from functions.export import JSONExporter

exporter = JSONExporter()
export_results = exporter.export_all()
logger.info(f"Export completed: {export_results}")
```

#### 3. API JSON Loading Functions (`scripts/run_api.py`)

**Responsibility**: Load data from JSON files instead of database

**New Functions**:
```python
load_alerts_from_json(min_score: float = 0.0, limit: int = 500) -> List[Dict]
load_chains_from_json(ticker: Optional[str] = None, limit: int = 100) -> List[Dict]
load_scans_from_json(limit: int = 100) -> List[Dict]
load_features_from_json(ticker: Optional[str] = None) -> Optional[Dict]
get_export_dir() -> Path
```

**API Endpoints Updated**:
- `GET /scans/latest` - Loads from JSON
- `GET /alerts/latest` - Loads from JSON
- `GET /alerts` - Loads from JSON with filtering
- `GET /alerts/ticker/{ticker}` - Loads from JSON
- `GET /options/{ticker}/snapshot` - Loads from JSON
- `GET /features/{ticker}/latest` - Loads from JSON

## Data Flow

### Write Path (Scheduler)
```
Data Collection
    ↓
Database Write (brief lock)
    ↓
Buffer Accumulation
    ↓
Flush to Database (brief lock)
    ↓
Export to JSON (read from DB, write to files)
    ↓
Archive Copy (optional)
```

### Read Path (API)
```
API Request
    ↓
Load from JSON File (no lock needed)
    ↓
Filter/Process
    ↓
Return Response
```

## File Structure

```
data/
├── exports/
│   ├── alerts.json          (Latest alerts)
│   ├── chains.json          (Latest chain snapshots)
│   ├── scans.json           (Latest scans)
│   ├── features.json        (Latest features)
│   └── archive/
│       ├── alerts_20260127_120000.json
│       ├── chains_20260127_120000.json
│       ├── scans_20260127_120000.json
│       └── features_20260127_120000.json
```

## Error Handling

**Graceful Degradation**:
- If JSON file doesn't exist: Return empty list or default response
- If JSON parse fails: Log error, return empty data
- If export fails: Log error, continue normal operation (data already in DB)
- If database locked: No impact on API (uses JSON)

**Resilience**:
- Archives provide historical backup if latest export corrupts
- Atomic writes prevent partial/corrupted files
- Database remains source of truth for archival

## Configuration

No new configuration required. Works with existing setup:
- Export runs automatically when triggered by scheduler
- API automatically uses JSON loading functions
- Fallback to empty responses if no export yet available

## Performance Characteristics

**Scheduler Impact**:
- Export operation: ~100-500ms for typical data volumes
- Runs during "FLUSHING" state (already blocking state)
- Minimal CPU/memory overhead

**API Impact**:
- JSON file reads: ~10-50ms for typical volumes
- File-based filtering more efficient than DB queries
- No lock contention with scheduler

**Data Freshness**:
- API sees data 5-10 minutes old (export interval)
- Acceptable for dashboard/analysis workload
- More recent data available via database if needed

## Migration Path

**Phase 1** (Current):
- Implement JSON export module
- Update API to load from JSON
- Enable in scheduler

**Phase 2** (Future):
- Monitor performance/data freshness
- Adjust export frequency based on needs
- Consider hybrid approach (critical data from DB, historical from JSON)

**Phase 3** (Optional):
- Switch to read-only API mode with JSON only
- Database used only for write operations
- Simplifies concurrency model further

## Testing

**Unit Tests**:
- JSON export with sample data
- Atomic write behavior
- Archive creation
- Error handling

**Integration Tests**:
- Scheduler → Export → API read flow
- Data consistency between exports
- Error recovery scenarios

**Performance Tests**:
- Export time with various data volumes
- API response times with JSON loading
- Concurrent scheduler + API operations

## Advantages Over Alternatives

### vs. Option A (Multiple DuckDB Instances)
- ✅ Simpler deployment (single database file)
- ✅ Automatic backups in archive
- ✅ Easier debugging and monitoring
- ✅ No need to manage multiple DB instances

### vs. Option B (PostgreSQL/SQLite)
- ✅ No external service required
- ✅ No connection pooling complexity
- ✅ Easier scaling (JSON export can be parallelized)
- ✅ Files are self-contained, portable

## Monitoring

**Key Metrics**:
- Export duration (target: < 1 second)
- Export frequency (every 5-10 minutes)
- JSON file sizes (alerts, chains, scans, features)
- API latency (should improve from no DB lock)
- Data staleness (export timestamp vs current time)

**Logging**:
- All exports logged with timestamp
- File sizes and record counts
- Errors logged with full context
- Archive operations logged

## Future Enhancements

1. **Configurable Export Frequency**: Allow tuning based on data volume
2. **Selective Export**: Only export changed data (delta export)
3. **Compression**: Gzip archives for storage efficiency
4. **S3 Upload**: Optional cloud backup of archives
5. **Data Retention**: Auto-cleanup old archives (>7 days)
6. **Export Monitoring**: Dashboard widget showing export status

## Conclusion

Option C (JSON Export) provides a practical, maintainable solution to the DuckDB concurrency problem by working with the database's limitations rather than against them. The hybrid approach maintains data integrity while improving system reliability and performance.
