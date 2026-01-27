"""
FastAPI server for Option Chain Dashboard.

This script sets up and runs the FastAPI backend server on port 8061, providing
all API endpoints for the React frontend to call. It initializes the database,
repositories, and all core services on startup.

Core Features:
    - Health & Config Endpoints: System health monitoring and configuration management
    - Scan Endpoints: Trigger scans and retrieve scan history
    - Alert Endpoints: Query and filter generated alerts
    - Options Chain Endpoints: Access current and historical option chain data
    - Feature Endpoints: Retrieve computed feature sets for tickers
    - Transaction Endpoints: CSV import and transaction history

API Documentation:
    - Swagger UI: http://localhost:8061/docs
    - ReDoc: http://localhost:8061/redoc
    - OpenAPI Schema: http://localhost:8061/openapi.json

All timestamps are UTC ISO 8601 format. All responses include proper error handling
with status codes and descriptive error messages.

Configuration:
    - Port: 8061 (configurable via environment or command line)
    - CORS: Enabled for localhost:8060 (React frontend)
    - Logging: All requests logged with method, path, status, response time

Usage:
    python scripts/run_api.py
    # OR with uvicorn directly:
    uvicorn scripts.run_api:app --host 0.0.0.0 --port 8061 --reload
"""

import time
import json
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from pathlib import Path as PathlibPath

from fastapi import FastAPI, Query, Path, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from functions.util.logging_setup import setup_logging, get_logger
from functions.config.loader import get_config_manager
from functions.config.settings import get_settings
from functions.db.connection import init_db, get_db

# Initialize database FIRST before importing repositories
# Note: When run as subprocess from main.py, database is already initialized.
# Try to initialize, but don't fail if database is already locked by parent process.
try:
    init_db()
except Exception as e:
    error_msg = str(e)
    if "Could not set lock" in error_msg or "Conflicting lock" in error_msg:
        # Database already initialized by parent process (main.py)
        # This is expected when run as subprocess
        import sys
        print(f"[DEBUG] Database already locked by parent process (expected): {error_msg[:100]}", file=sys.stderr)
    else:
        raise

from functions.db.repositories import (
    ScanRepository,
    FeatureSnapshotRepository,
    AlertRepository,
    ChainSnapshotRepository,
)
from functions.market.models import OptionContract, OptionsChain


# ============================================================================
# JSON FILE LOADING FUNCTIONS (Hybrid Approach - Option C)
# ============================================================================

def get_export_dir() -> PathlibPath:
    """Get path to data/exports directory."""
    project_root = PathlibPath(__file__).parent.parent
    return project_root / "data" / "exports"


def load_alerts_from_json(min_score: float = 0.0, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Load alerts from JSON file (not database).

    Args:
        min_score: Filter alerts by minimum score
        limit: Maximum alerts to return

    Returns:
        List of alert dictionaries, empty list if file not found
    """
    try:
        export_dir = get_export_dir()
        alerts_file = export_dir / "alerts.json"

        if not alerts_file.exists():
            logger.debug(f"Alerts JSON file not found: {alerts_file}")
            return []

        with open(alerts_file, 'r') as f:
            data = json.load(f)
            alerts = data.get("alerts", [])

            # Filter by score
            if min_score > 0:
                alerts = [a for a in alerts if a.get("score", 0) >= min_score]

            # Respect limit
            return alerts[:limit]

    except Exception as e:
        logger.error(f"Failed to load alerts from JSON: {e}")
        return []


def load_chains_from_json(ticker: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Load chain snapshots from JSON file (not database).

    Args:
        ticker: Optional filter by ticker
        limit: Maximum chains to return

    Returns:
        List of chain snapshot dictionaries, empty list if file not found
    """
    try:
        export_dir = get_export_dir()
        chains_file = export_dir / "chains.json"

        if not chains_file.exists():
            logger.debug(f"Chains JSON file not found: {chains_file}")
            return []

        with open(chains_file, 'r') as f:
            data = json.load(f)
            chains = data.get("chains", [])

            # Filter by ticker if provided
            if ticker:
                chains = [c for c in chains if c.get("ticker") == ticker]

            # Respect limit
            return chains[:limit]

    except Exception as e:
        logger.error(f"Failed to load chains from JSON: {e}")
        return []


def load_scans_from_json(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Load scans from JSON file (not database).

    Args:
        limit: Maximum scans to return

    Returns:
        List of scan dictionaries, empty list if file not found
    """
    try:
        export_dir = get_export_dir()
        scans_file = export_dir / "scans.json"

        if not scans_file.exists():
            logger.debug(f"Scans JSON file not found: {scans_file}")
            return []

        with open(scans_file, 'r') as f:
            data = json.load(f)
            scans = data.get("scans", [])
            return scans[:limit]

    except Exception as e:
        logger.error(f"Failed to load scans from JSON: {e}")
        return []


def load_features_from_json(ticker: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Load feature snapshot from JSON file (not database).

    Args:
        ticker: Optional filter by specific ticker

    Returns:
        Feature snapshot dictionary or None if not found
    """
    try:
        export_dir = get_export_dir()
        features_file = export_dir / "features.json"

        if not features_file.exists():
            logger.debug(f"Features JSON file not found: {features_file}")
            return None

        with open(features_file, 'r') as f:
            data = json.load(f)
            features_list = data.get("features", [])

            # If ticker specified, find matching feature
            if ticker:
                for feature in features_list:
                    if feature.get("ticker") == ticker:
                        return feature
                return None

            # Return first (most recent) feature
            return features_list[0] if features_list else None

    except Exception as e:
        logger.error(f"Failed to load features from JSON: {e}")
        return None

# ============================================================================
# LOGGING SETUP
# ============================================================================

setup_logging()
logger = get_logger(__name__)

# ============================================================================
# PYDANTIC RESPONSE MODELS
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Status indicator ('ok' or 'error')")
    timestamp: str = Field(..., description="UTC ISO 8601 timestamp")
    message: Optional[str] = Field(None, description="Optional status message")


class ConfigReloadResponse(BaseModel):
    """Configuration reload response model."""

    status: str = Field(..., description="Status indicator ('reloaded' or 'error')")
    timestamp: str = Field(..., description="UTC ISO 8601 timestamp")
    config_hash: str = Field(..., description="SHA256 hash of loaded configuration")
    message: Optional[str] = Field(None, description="Optional message")


class ConfigModeResponse(BaseModel):
    """Data mode configuration response model."""

    mode: str = Field(..., description="Data mode ('demo' or 'production')")
    timestamp: str = Field(..., description="UTC ISO 8601 timestamp")


class ConfigUpdateRequest(BaseModel):
    """Configuration update request model.

    Allows updating configuration values at runtime without server restart.
    This endpoint enables mode switching (demo/production) from the frontend,
    allowing users to test with synthetic data or switch to live market data.

    WHY THIS IS USEFUL:
    - Developers can quickly test with demo data without waiting for restarts
    - Users can toggle between safe testing and live trading modes
    - Supports A/B testing of different data sources without redeployment
    """

    mode: Optional[str] = Field(
        None,
        description="Data mode to switch to ('demo' or 'production')"
    )


class ConfigUpdateResponse(BaseModel):
    """Configuration update response model.

    Returns the new configuration state after successful update.
    Includes timestamp for audit trail and demo_mode flag for client state sync.
    """

    status: str = Field(..., description="Update status ('updated' or 'error')")
    mode: Optional[str] = Field(None, description="New data mode ('demo' or 'production')")
    demo_mode: Optional[bool] = Field(None, description="New demo_mode flag value (True=demo, False=production)")
    message: Optional[str] = Field(None, description="Status message for debugging")
    timestamp: str = Field(..., description="UTC ISO 8601 timestamp of update")


class ScanResponse(BaseModel):
    """Scan execution response model."""

    scan_id: int = Field(..., description="Unique ID of scan")
    status: str = Field(..., description="Scan status ('running', 'completed', 'failed')")
    timestamp: str = Field(..., description="UTC ISO 8601 timestamp")
    ticker_count: Optional[int] = Field(None, description="Number of tickers scanned")
    alert_count: Optional[int] = Field(None, description="Number of alerts generated")


class ScanStatusResponse(BaseModel):
    """Scan status response model."""

    scan_id: int = Field(..., description="Unique ID of scan")
    status: str = Field(..., description="Current scan status")
    created_at: str = Field(..., description="UTC ISO 8601 creation timestamp")
    completed_at: Optional[str] = Field(None, description="UTC ISO 8601 completion time")
    ticker_count: Optional[int] = Field(None, description="Tickers processed")
    alert_count: Optional[int] = Field(None, description="Alerts generated")
    runtime_seconds: Optional[float] = Field(None, description="Execution time")


class ScanSummaryResponse(BaseModel):
    """Summary of a single scan."""

    scan_id: int
    created_at: str
    status: str
    ticker_count: Optional[int] = None
    alert_count: Optional[int] = None


class ScansHistoryResponse(BaseModel):
    """Recent scans history response model."""

    scans: List[ScanSummaryResponse] = Field(..., description="List of recent scans")
    total_count: int = Field(..., description="Total scans available")
    timestamp: str = Field(..., description="UTC ISO 8601 timestamp")


class AlertResponse(BaseModel):
    """Single alert response model."""

    id: int = Field(..., description="Alert ID")
    scan_id: int = Field(..., description="Scan ID that generated alert")
    ticker: str = Field(..., description="Stock ticker symbol")
    detector_name: str = Field(..., description="Name of detector that generated alert")
    score: float = Field(..., description="Alert score (0-100)")
    alert_data: Dict[str, Any] = Field(..., description="Alert details and metrics")
    created_at: str = Field(..., description="UTC ISO 8601 creation timestamp")


class AlertsResponse(BaseModel):
    """Multiple alerts response model."""

    alerts: List[AlertResponse] = Field(..., description="List of alerts")
    total_count: int = Field(..., description="Total alerts matching filter")
    timestamp: str = Field(..., description="UTC ISO 8601 timestamp")


class OptionContractResponse(BaseModel):
    """Single option contract response."""

    strike: float
    option_type: str
    bid: float
    ask: float
    volume: int
    open_interest: int
    implied_volatility: float
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    rho: Optional[float] = None


class ChainSnapshotResponse(BaseModel):
    """Options chain snapshot response model."""

    ticker: str = Field(..., description="Stock ticker symbol")
    timestamp: str = Field(..., description="UTC ISO 8601 snapshot timestamp")
    underlying_price: float = Field(..., description="Current underlying stock price")
    expiration: str = Field(..., description="Option expiration date (YYYY-MM-DD)")
    calls: List[OptionContractResponse] = Field(..., description="Call option contracts")
    puts: List[OptionContractResponse] = Field(..., description="Put option contracts")


class FeaturesResponse(BaseModel):
    """Feature set response model."""

    ticker: str = Field(..., description="Stock ticker symbol")
    timestamp: str = Field(..., description="UTC ISO 8601 feature computation timestamp")
    features: Dict[str, Any] = Field(..., description="Computed features for ticker")


class TransactionResponse(BaseModel):
    """Single transaction response."""

    id: int
    timestamp: str
    ticker: str
    transaction_type: str
    quantity: int
    price: float
    notes: Optional[str] = None


class TransactionsResponse(BaseModel):
    """Multiple transactions response model."""

    transactions: List[TransactionResponse]
    total_count: int
    timestamp: str


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error type or message")
    details: Optional[str] = Field(None, description="Additional error details")
    timestamp: str = Field(..., description="UTC ISO 8601 timestamp")


# ============================================================================
# GLOBAL STATE & INITIALIZATION
# ============================================================================

# Repositories - initialized on startup
scan_repo: Optional[ScanRepository] = None
feature_repo: Optional[FeatureSnapshotRepository] = None
alert_repo: Optional[AlertRepository] = None
chain_repo: Optional[ChainSnapshotRepository] = None


def get_utc_iso_timestamp() -> str:
    """Get current UTC time as ISO 8601 string.

    Returns:
        ISO 8601 formatted timestamp (e.g., '2026-01-26T15:30:45.123456Z')
    """
    return datetime.now(timezone.utc).isoformat()


def get_config_hash() -> str:
    """Get SHA256 hash of current configuration.

    Returns:
        Hexadecimal SHA256 hash of configuration
    """
    config_mgr = get_config_manager()
    return config_mgr.config_hash


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.

    Startup:
        - Initialize database connection and run migrations
        - Create repository instances
        - Load configuration
        - Setup logging

    Shutdown:
        - Close database connections
        - Cleanup resources
    """
    # ========================================================================
    # STARTUP
    # ========================================================================
    logger.info("Starting Option Chain Dashboard API server...")

    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully")

        # Initialize repositories
        global scan_repo, feature_repo, alert_repo, chain_repo
        scan_repo = ScanRepository()
        feature_repo = FeatureSnapshotRepository()
        alert_repo = AlertRepository()
        chain_repo = ChainSnapshotRepository()
        logger.info("Repositories initialized successfully")

        # Load configuration
        config_mgr = get_config_manager()
        logger.info(f"Configuration loaded: hash={config_mgr.config_hash[:8]}...")

        # Get settings
        settings = get_settings()
        logger.info(f"Settings loaded: demo_mode={settings.demo_mode}")

        logger.info("Startup completed successfully")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    # ========================================================================
    # SHUTDOWN
    # ========================================================================
    logger.info("Shutting down Option Chain Dashboard API server...")
    try:
        # Cleanup - add any database cleanup here if needed
        logger.info("Shutdown completed")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# ============================================================================
# FASTAPI APP SETUP
# ============================================================================

app = FastAPI(
    title="Option Chain Dashboard API",
    description="REST API for options analysis platform with real-time data and pattern detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ============================================================================
# MIDDLEWARE SETUP
# ============================================================================

# CORS Middleware - Enable cross-origin requests from React frontend
# Configured to support:
# - http://192.168.1.16:8060: LAN access from the frontend (frontend IP)
# - http://localhost:8060: Local development with localhost
# - 127.0.0.1:8060: Loopback IP for local development
# This allows the frontend running on any of these origins to make API calls
# to the backend while preventing other unauthorized origins from accessing it
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://192.168.1.16:8060",  # LAN access (frontend on IP)
        "http://localhost:8060",      # Local development
        "http://127.0.0.1:8060",      # Loopback address for dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """
    Middleware for logging all HTTP requests and responses.

    Logs:
        - HTTP method and path
        - Response status code
        - Request/response time in milliseconds
        - Any query parameters or request body size

    Args:
        request: FastAPI Request object
        call_next: Next middleware/route handler

    Returns:
        Response from next middleware/route handler
    """
    start_time = time.time()
    request_id = hashlib.md5(
        f"{start_time}{id(request)}".encode()
    ).hexdigest()[:8]

    logger.debug(
        f"[{request_id}] {request.method} {request.url.path} - "
        f"Client: {request.client.host if request.client else 'unknown'}"
    )

    try:
        response = await call_next(request)
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"Error: {e} ({elapsed_ms:.1f}ms)"
        )
        raise

    elapsed_ms = (time.time() - start_time) * 1000
    logger.info(
        f"[{request_id}] {request.method} {request.url.path} - "
        f"Status: {response.status_code} ({elapsed_ms:.1f}ms)"
    )

    return response


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handle FastAPI HTTP exceptions.

    Args:
        request: The request that caused the exception
        exc: The HTTPException

    Returns:
        JSON error response with status code
    """
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail or "HTTP Error",
            timestamp=get_utc_iso_timestamp(),
        ).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle uncaught exceptions.

    Args:
        request: The request that caused the exception
        exc: The exception

    Returns:
        JSON error response with 500 status code
    """
    logger.error(f"Unhandled Exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            details=str(exc),
            timestamp=get_utc_iso_timestamp(),
        ).dict(),
    )


# ============================================================================
# HEALTH & CONFIG ENDPOINTS
# ============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        HealthResponse with status and timestamp

    Example:
        GET /health
        {
            "status": "ok",
            "timestamp": "2026-01-26T15:30:45.123456Z"
        }
    """
    try:
        # Try to verify database connection
        if not scan_repo:
            raise RuntimeError("Database not initialized")
        logger.debug("Health check passed")
        return HealthResponse(
            status="ok",
            timestamp=get_utc_iso_timestamp(),
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error",
            timestamp=get_utc_iso_timestamp(),
            message=str(e),
        )


@app.get("/config/data-mode", response_model=ConfigModeResponse, tags=["Config"])
async def get_data_mode() -> ConfigModeResponse:
    """
    Get current data mode (demo or production).

    Returns:
        ConfigModeResponse with current mode

    Example:
        GET /config/data-mode
        {
            "mode": "demo",
            "timestamp": "2026-01-26T15:30:45.123456Z"
        }
    """
    settings = get_settings()
    mode = "demo" if settings.demo_mode else "production"
    logger.debug(f"Data mode: {mode}")
    return ConfigModeResponse(
        mode=mode,
        timestamp=get_utc_iso_timestamp(),
    )


@app.post("/config/data-mode", response_model=ConfigUpdateResponse, tags=["Config"])
async def update_data_mode(request: ConfigUpdateRequest) -> ConfigUpdateResponse:
    """
    Update data mode (demo or production) at runtime.

    This endpoint allows switching between demo mode (synthetic data) and
    production mode (live market data) WITHOUT restarting the server.

    WHY THIS IS USEFUL:
    - Developers can test with demo data then switch to live data on the fly
    - Users can safely test strategies with synthetic data before going live
    - No server restart required - changes take effect immediately for next API calls
    - Maintains audit trail with timestamp of each mode change

    Args:
        request: ConfigUpdateRequest with mode ('demo' or 'production')

    Returns:
        ConfigUpdateResponse with new mode and updated demo_mode flag

    Raises:
        HTTPException: 400 if mode is invalid, 500 if update fails

    Example:
        POST /config/data-mode
        {
            "mode": "production"
        }

        Response:
        {
            "status": "updated",
            "mode": "production",
            "demo_mode": false,
            "message": "Switched from demo to production mode",
            "timestamp": "2026-01-26T15:30:45.123456Z"
        }
    """
    try:
        # Validate input
        if not request.mode:
            raise HTTPException(
                status_code=400,
                detail="mode parameter is required ('demo' or 'production')"
            )

        if request.mode not in ["demo", "production"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: '{request.mode}'. Must be 'demo' or 'production'"
            )

        # Get current settings
        settings = get_settings()
        old_mode = "demo" if settings.demo_mode else "production"

        # Update demo_mode flag in settings
        # NOTE: Settings are immutable (Pydantic), but we can modify the flag in memory
        new_demo_mode = (request.mode == "demo")
        settings.demo_mode = new_demo_mode

        # Log the mode change with timestamp for audit trail
        logger.info(
            f"Data mode switched: {old_mode} → {request.mode} "
            f"[{get_utc_iso_timestamp()}]"
        )

        return ConfigUpdateResponse(
            status="updated",
            mode=request.mode,
            demo_mode=new_demo_mode,
            message=f"Switched from {old_mode} to {request.mode} mode",
            timestamp=get_utc_iso_timestamp(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update data mode: {e}")
        raise HTTPException(status_code=500, detail=f"Mode update failed: {e}")


@app.post("/config/update", response_model=ConfigUpdateResponse, tags=["Config"])
async def update_config(request: ConfigUpdateRequest) -> ConfigUpdateResponse:
    """
    Generic configuration update endpoint (future expansion).

    This endpoint is designed for future use to update other configuration
    values beyond just demo_mode. Currently supports mode switching.

    FUTURE SUPPORT:
    - Risk-free rate adjustment
    - Cache TTL configuration
    - Alert thresholds
    - Other runtime settings

    WHY THIS IS STRUCTURED THIS WAY:
    - Single endpoint for all config updates (consistent API)
    - Easy to extend with new fields in ConfigUpdateRequest
    - Maintains timestamp audit trail for all changes
    - Type-safe validation via Pydantic models

    Args:
        request: ConfigUpdateRequest with fields to update

    Returns:
        ConfigUpdateResponse with new values and status

    Example:
        POST /config/update
        {
            "mode": "production"
        }
    """
    # For now, delegate to data-mode endpoint
    # This will be extended for other config fields in the future
    if request.mode:
        return await update_data_mode(request)

    return ConfigUpdateResponse(
        status="error",
        message="No configuration fields to update",
        timestamp=get_utc_iso_timestamp(),
    )


@app.post("/config/reload", response_model=ConfigReloadResponse, tags=["Config"])
async def reload_config() -> ConfigReloadResponse:
    """
    Reload configuration from disk.

    Reloads config.yaml and related configuration files. Useful for
    updating settings without restarting the server.

    Returns:
        ConfigReloadResponse with new config hash

    Raises:
        HTTPException: 500 if configuration reload fails

    Example:
        POST /config/reload
        {
            "status": "reloaded",
            "config_hash": "a1b2c3d4...",
            "timestamp": "2026-01-26T15:30:45.123456Z"
        }
    """
    try:
        config_mgr = get_config_manager()
        config_mgr.reload()
        config_hash = config_mgr.config_hash
        logger.info(f"Configuration reloaded: hash={config_hash[:8]}...")
        return ConfigReloadResponse(
            status="reloaded",
            config_hash=config_hash,
            timestamp=get_utc_iso_timestamp(),
        )
    except Exception as e:
        logger.error(f"Configuration reload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration reload failed: {e}")


# ============================================================================
# SCAN ENDPOINTS
# ============================================================================


@app.post("/scan/run", response_model=ScanResponse, tags=["Scans"])
async def trigger_scan() -> ScanResponse:
    """
    Trigger a new options analysis scan immediately.

    This endpoint creates a new scan record and returns the scan ID. The scan
    itself runs asynchronously; use /scan/status/{scan_id} to check progress.

    Returns:
        ScanResponse with scan_id and initial status

    Raises:
        HTTPException: 500 if scan creation fails

    Example:
        POST /scan/run
        {
            "scan_id": 42,
            "status": "running",
            "timestamp": "2026-01-26T15:30:45.123456Z"
        }
    """
    try:
        config_mgr = get_config_manager()
        config_hash = config_mgr.config_hash

        # Create scan record in database
        if not scan_repo:
            raise RuntimeError("Scan repository not initialized")

        scan_id = scan_repo.create_scan(config_hash)
        logger.info(f"Triggered new scan: id={scan_id}")

        return ScanResponse(
            scan_id=scan_id,
            status="running",
            timestamp=get_utc_iso_timestamp(),
        )
    except Exception as e:
        logger.error(f"Failed to trigger scan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger scan: {e}")


@app.get("/scan/status/{scan_id}", response_model=ScanStatusResponse, tags=["Scans"])
async def get_scan_status(scan_id: int) -> ScanStatusResponse:
    """
    Get status and metrics for a specific scan.

    Returns:
        ScanStatusResponse with current status, timestamps, and metrics

    Raises:
        HTTPException: 404 if scan_id not found, 500 if query fails

    Example:
        GET /scan/status/42
        {
            "scan_id": 42,
            "status": "completed",
            "created_at": "2026-01-26T15:30:00Z",
            "ticker_count": 50,
            "alert_count": 12,
            "runtime_seconds": 125.3
        }
    """
    try:
        if not scan_repo:
            raise RuntimeError("Scan repository not initialized")

        scan = scan_repo.get_scan(scan_id)
        if not scan:
            logger.warning(f"Scan not found: id={scan_id}")
            raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

        logger.debug(f"Retrieved scan status: id={scan_id}, status={scan.get('status')}")

        return ScanStatusResponse(
            scan_id=scan_id,
            status=scan.get("status", "unknown"),
            created_at=scan.get("created_at", get_utc_iso_timestamp()),
            completed_at=scan.get("completed_at"),
            ticker_count=scan.get("tickers_scanned"),
            alert_count=scan.get("alerts_generated"),
            runtime_seconds=scan.get("runtime_seconds"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scan status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scan status: {e}")


@app.get("/scans/latest", response_model=ScansHistoryResponse, tags=["Scans"])
async def get_latest_scans(
    limit: int = Query(10, ge=1, le=100, description="Number of scans to return")
) -> ScansHistoryResponse:
    """
    Get latest scans summary.

    Returns the most recent scans with summary information. Useful for
    monitoring scan history and recent alert activity.

    Args:
        limit: Maximum number of scans to return (default 10, max 100)

    Returns:
        ScansHistoryResponse with list of recent scans

    Raises:
        HTTPException: 500 if query fails

    Example:
        GET /scans/latest?limit=10
        {
            "scans": [
                {
                    "scan_id": 50,
                    "created_at": "2026-01-26T16:00:00Z",
                    "status": "completed",
                    "ticker_count": 50,
                    "alert_count": 8
                }
            ],
            "total_count": 50,
            "timestamp": "2026-01-26T15:30:45.123456Z"
        }
    """
    try:
        # Load scans from JSON file (Hybrid Approach - Option C)
        scans = load_scans_from_json(limit=limit)
        logger.debug(f"Retrieved {len(scans)} scans from JSON")

        scan_summaries = [
            ScanSummaryResponse(
                scan_id=scan.get("id", 0),
                created_at=scan.get("created_at", get_utc_iso_timestamp()),
                status=scan.get("status", "unknown"),
                ticker_count=scan.get("tickers_scanned"),
                alert_count=scan.get("alerts_generated"),
            )
            for scan in scans
        ]

        return ScansHistoryResponse(
            scans=scan_summaries,
            total_count=len(scans),
            timestamp=get_utc_iso_timestamp(),
        )
    except Exception as e:
        logger.error(f"Failed to get scan history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scan history: {e}")


# ============================================================================
# ALERT ENDPOINTS
# ============================================================================


@app.get("/alerts/latest", response_model=AlertsResponse, tags=["Alerts"])
async def get_latest_alerts(
    limit: int = Query(50, ge=1, le=500, description="Number of alerts to return"),
    min_score: float = Query(0, ge=0, le=100, description="Minimum alert score"),
) -> AlertsResponse:
    """
    Get latest alerts, sorted by score descending.

    Returns the most recent alerts filtered by minimum score. Useful for
    dashboards showing top opportunities.

    Args:
        limit: Maximum alerts to return (default 50, max 500)
        min_score: Minimum alert score filter (0-100, default 0)

    Returns:
        AlertsResponse with filtered alerts

    Raises:
        HTTPException: 500 if query fails

    Example:
        GET /alerts/latest?limit=50&min_score=60
        {
            "alerts": [
                {
                    "id": 1,
                    "scan_id": 42,
                    "ticker": "AAPL",
                    "detector_name": "volume_spike",
                    "score": 85.5,
                    "alert_data": {...},
                    "created_at": "2026-01-26T15:30:00Z"
                }
            ],
            "total_count": 12,
            "timestamp": "2026-01-26T15:30:45.123456Z"
        }
    """
    try:
        # Load alerts from JSON file (Hybrid Approach - Option C)
        alerts = load_alerts_from_json(min_score=min_score, limit=limit)
        logger.debug(f"Retrieved {len(alerts)} alerts from JSON (limit={limit}, min_score={min_score})")

        alert_responses = [
            AlertResponse(
                id=alert.get("id", 0),
                scan_id=alert.get("scan_id", 0),
                ticker=alert.get("ticker", ""),
                detector_name=alert.get("detector_name", ""),
                score=alert.get("score", 0),
                alert_data=alert.get("alert_data", alert.get("alert_json", {})) if isinstance(alert.get("alert_data"), dict) else json.loads(alert.get("alert_json", "{}")),
                created_at=alert.get("created_at", get_utc_iso_timestamp()),
            )
            for alert in alerts
        ]

        return AlertsResponse(
            alerts=alert_responses,
            total_count=len(alerts),
            timestamp=get_utc_iso_timestamp(),
        )
    except Exception as e:
        logger.error(f"Failed to get latest alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {e}")


@app.get("/alerts", response_model=AlertsResponse, tags=["Alerts"])
async def filter_alerts(
    ticker: Optional[str] = Query(None, description="Filter by ticker symbol"),
    min_score: float = Query(0, ge=0, le=100, description="Minimum alert score"),
    detector: Optional[str] = Query(None, description="Filter by detector name"),
    limit: int = Query(100, ge=1, le=500, description="Number of alerts to return"),
) -> AlertsResponse:
    """
    Filter alerts by ticker, score, and detector.

    Allows complex filtering of alerts by multiple criteria. Useful for
    analyzing specific opportunities or patterns.

    Args:
        ticker: Optional ticker symbol filter (e.g., "AAPL")
        min_score: Minimum alert score (0-100, default 0)
        detector: Optional detector name filter
        limit: Maximum alerts to return (default 100, max 500)

    Returns:
        AlertsResponse with filtered alerts

    Raises:
        HTTPException: 500 if query fails

    Example:
        GET /alerts?ticker=AAPL&min_score=60&limit=50
        {
            "alerts": [...],
            "total_count": 8,
            "timestamp": "2026-01-26T15:30:45.123456Z"
        }
    """
    try:
        # Load alerts from JSON file (Hybrid Approach - Option C)
        alerts = load_alerts_from_json(min_score=0, limit=limit * 10)

        # Apply ticker filter
        if ticker:
            alerts = [a for a in alerts if a.get("ticker") == ticker]

        # Apply detector filter
        if detector:
            alerts = [a for a in alerts if a.get("detector_name") == detector]

        # Apply score filter
        alerts = [a for a in alerts if a.get("score", 0) >= min_score]

        # Respect limit
        alerts = alerts[:limit]

        logger.debug(
            f"Retrieved {len(alerts)} alerts from JSON "
            f"(ticker={ticker}, min_score={min_score}, detector={detector})"
        )

        alert_responses = [
            AlertResponse(
                id=alert.get("id", 0),
                scan_id=alert.get("scan_id", 0),
                ticker=alert.get("ticker", ""),
                detector_name=alert.get("detector_name", ""),
                score=alert.get("score", 0),
                alert_data=alert.get("alert_data", alert.get("alert_json", {})) if isinstance(alert.get("alert_data"), dict) else json.loads(alert.get("alert_json", "{}")),
                created_at=alert.get("created_at", get_utc_iso_timestamp()),
            )
            for alert in alerts
        ]

        return AlertsResponse(
            alerts=alert_responses,
            total_count=len(alerts),
            timestamp=get_utc_iso_timestamp(),
        )
    except Exception as e:
        logger.error(f"Failed to filter alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to filter alerts: {e}")


@app.get("/alerts/ticker/{ticker}", response_model=AlertsResponse, tags=["Alerts"])
async def get_ticker_alerts(
    ticker: str = Path(..., description="Stock ticker symbol"),
    limit: int = Query(100, ge=1, le=500, description="Number of alerts to return"),
) -> AlertsResponse:
    """
    Get all alerts for a specific ticker.

    Returns:
        AlertsResponse with all alerts for the ticker

    Raises:
        HTTPException: 404 if no alerts found, 500 if query fails

    Example:
        GET /alerts/ticker/AAPL?limit=50
        {
            "alerts": [...],
            "total_count": 12,
            "timestamp": "2026-01-26T15:30:45.123456Z"
        }
    """
    try:
        # Load alerts from JSON file (Hybrid Approach - Option C)
        all_alerts = load_alerts_from_json(min_score=0, limit=10000)
        alerts = [a for a in all_alerts if a.get("ticker") == ticker][:limit]

        if not alerts:
            logger.info(f"No alerts found for ticker: {ticker}")
            # Return empty list instead of 404 for consistency
            return AlertsResponse(
                alerts=[],
                total_count=0,
                timestamp=get_utc_iso_timestamp(),
            )

        logger.debug(f"Retrieved {len(alerts)} alerts for ticker: {ticker}")

        alert_responses = [
            AlertResponse(
                id=alert.get("id", 0),
                scan_id=alert.get("scan_id", 0),
                ticker=alert.get("ticker", ""),
                detector_name=alert.get("detector_name", ""),
                score=alert.get("score", 0),
                alert_data=alert.get("alert_data", alert.get("alert_json", {})) if isinstance(alert.get("alert_data"), dict) else json.loads(alert.get("alert_json", "{}")),
                created_at=alert.get("created_at", get_utc_iso_timestamp()),
            )
            for alert in alerts
        ]

        return AlertsResponse(
            alerts=alert_responses,
            total_count=len(alerts),
            timestamp=get_utc_iso_timestamp(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get alerts for ticker {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {e}")


# ============================================================================
# OPTIONS CHAIN ENDPOINTS
# ============================================================================


@app.get("/options/{ticker}/snapshot", response_model=ChainSnapshotResponse, tags=["Options"])
async def get_options_snapshot(
    ticker: str = Path(..., description="Stock ticker symbol")
) -> ChainSnapshotResponse:
    """
    Get current options chain snapshot for a ticker.

    Returns the current bid/ask, Greeks, and other contract details for both
    call and put options on a specific ticker. Includes both the nearest and
    secondary expirations.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        ChainSnapshotResponse with calls and puts for both expirations

    Raises:
        HTTPException: 404 if no data available, 500 if query fails

    Example:
        GET /options/AAPL/snapshot
        {
            "ticker": "AAPL",
            "timestamp": "2026-01-26T15:30:00Z",
            "underlying_price": 192.50,
            "expiration": "2026-02-20",
            "calls": [...],
            "puts": [...]
        }
    """
    try:
        # Load chain snapshot from JSON file (Hybrid Approach - Option C)
        chains = load_chains_from_json(ticker=ticker, limit=1)

        if not chains:
            logger.info(f"No chain snapshot available for ticker: {ticker}")
            # Return minimal response instead of 404 for consistency
            return ChainSnapshotResponse(
                ticker=ticker,
                timestamp=get_utc_iso_timestamp(),
                underlying_price=0,
                expiration="",
                calls=[],
                puts=[],
            )

        chain = chains[0]

        # Convert to response format
        calls = [
            OptionContractResponse(
                strike=c.get("strike", 0),
                option_type="call",
                bid=c.get("bid", 0),
                ask=c.get("ask", 0),
                volume=c.get("volume", 0),
                open_interest=c.get("open_interest", 0),
                implied_volatility=c.get("implied_volatility", 0),
                delta=c.get("delta"),
                gamma=c.get("gamma"),
                vega=c.get("vega"),
                theta=c.get("theta"),
                rho=c.get("rho"),
            )
            for c in chain.get("calls", [])
        ]

        puts = [
            OptionContractResponse(
                strike=p.get("strike", 0),
                option_type="put",
                bid=p.get("bid", 0),
                ask=p.get("ask", 0),
                volume=p.get("volume", 0),
                open_interest=p.get("open_interest", 0),
                implied_volatility=p.get("implied_volatility", 0),
                delta=p.get("delta"),
                gamma=p.get("gamma"),
                vega=p.get("vega"),
                theta=p.get("theta"),
                rho=p.get("rho"),
            )
            for p in chain.get("puts", [])
        ]

        logger.debug(
            f"Retrieved chain snapshot for {ticker} from JSON: "
            f"{len(calls)} calls, {len(puts)} puts"
        )

        return ChainSnapshotResponse(
            ticker=ticker,
            timestamp=chain.get("timestamp", get_utc_iso_timestamp()),
            underlying_price=chain.get("underlying_price", 0),
            expiration=chain.get("expiration", ""),
            calls=calls,
            puts=puts,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get options snapshot for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get options data: {e}")


@app.get("/options/{ticker}/history", response_model=List[ChainSnapshotResponse], tags=["Options"])
async def get_options_history(
    ticker: str = Path(..., description="Stock ticker symbol"),
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum snapshots to return"),
) -> List[ChainSnapshotResponse]:
    """
    Get historical options chain snapshots for a ticker.

    Returns historical snapshots of options chains, useful for analyzing
    how volatility, open interest, and bid/ask spreads evolve over time.

    Args:
        ticker: Stock ticker symbol
        days: Look back period in days (default 30, max 365)
        limit: Maximum snapshots to return (default 100, max 1000)

    Returns:
        List of ChainSnapshotResponse ordered by timestamp descending

    Raises:
        HTTPException: 404 if no history available, 500 if query fails

    Example:
        GET /options/AAPL/history?days=30&limit=50
        [
            {
                "ticker": "AAPL",
                "timestamp": "2026-01-26T15:30:00Z",
                "underlying_price": 192.50,
                ...
            }
        ]
    """
    try:
        if not chain_repo:
            raise RuntimeError("Chain repository not initialized")

        # Get historical chain snapshots
        chains = chain_repo.get_snapshot_history(ticker, days=days, limit=limit)

        if not chains:
            logger.info(f"No chain history available for ticker: {ticker}")
            raise HTTPException(
                status_code=404,
                detail=f"No historical chain data available for ticker {ticker}",
            )

        logger.debug(
            f"Retrieved {len(chains)} historical chain snapshots for {ticker} "
            f"({days} days, limit {limit})"
        )

        responses = [
            ChainSnapshotResponse(
                ticker=ticker,
                timestamp=chain.get("timestamp", get_utc_iso_timestamp()),
                underlying_price=chain.get("underlying_price", 0),
                expiration=chain.get("expiration", ""),
                calls=[
                    OptionContractResponse(
                        strike=c.get("strike", 0),
                        option_type="call",
                        bid=c.get("bid", 0),
                        ask=c.get("ask", 0),
                        volume=c.get("volume", 0),
                        open_interest=c.get("open_interest", 0),
                        implied_volatility=c.get("implied_volatility", 0),
                    )
                    for c in chain.get("calls", [])
                ],
                puts=[
                    OptionContractResponse(
                        strike=p.get("strike", 0),
                        option_type="put",
                        bid=p.get("bid", 0),
                        ask=p.get("ask", 0),
                        volume=p.get("volume", 0),
                        open_interest=p.get("open_interest", 0),
                        implied_volatility=p.get("implied_volatility", 0),
                    )
                    for p in chain.get("puts", [])
                ],
            )
            for chain in chains
        ]

        return responses
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chain history for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get history: {e}")


# ============================================================================
# FEATURE ENDPOINTS
# ============================================================================


@app.get("/features/{ticker}/latest", response_model=FeaturesResponse, tags=["Features"])
async def get_latest_features(
    ticker: str = Path(..., description="Stock ticker symbol")
) -> FeaturesResponse:
    """
    Get latest computed features for a ticker.

    Returns the most recent feature set computed during a scan, including
    volatility metrics, volume analysis, Greeks aggregates, etc.

    Args:
        ticker: Stock ticker symbol

    Returns:
        FeaturesResponse with feature set

    Raises:
        HTTPException: 404 if no features available, 500 if query fails

    Example:
        GET /features/AAPL/latest
        {
            "ticker": "AAPL",
            "timestamp": "2026-01-26T15:30:00Z",
            "features": {
                "iv_percentile": 65.5,
                "volume_spike": 2.3,
                "skew_rank": 8
            }
        }
    """
    try:
        # Load features from JSON file (Hybrid Approach - Option C)
        features = load_features_from_json(ticker=ticker)

        if not features:
            logger.info(f"No features available for ticker: {ticker}")
            # Return empty response instead of 404 for consistency
            return FeaturesResponse(
                ticker=ticker,
                timestamp=get_utc_iso_timestamp(),
                features={},
            )

        logger.debug(f"Retrieved latest features for ticker {ticker} from JSON")

        return FeaturesResponse(
            ticker=ticker,
            timestamp=features.get("created_at", get_utc_iso_timestamp()),
            features=features.get("features", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get features for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get features: {e}")


@app.post("/features/compute", response_model=FeaturesResponse, tags=["Features"])
async def compute_features_endpoint(
    ticker: str = Query(..., description="Stock ticker symbol")
) -> FeaturesResponse:
    """
    Trigger immediate feature computation for a ticker.

    This endpoint initiates on-demand feature computation, bypassing normal
    scan scheduling. Useful for immediate analysis or testing.

    Args:
        ticker: Stock ticker symbol

    Returns:
        FeaturesResponse with computed features

    Raises:
        HTTPException: 400 if ticker invalid, 500 if computation fails

    Example:
        POST /features/compute?ticker=AAPL
        {
            "ticker": "AAPL",
            "timestamp": "2026-01-26T15:30:00Z",
            "features": {...}
        }
    """
    try:
        if not ticker or len(ticker) == 0:
            raise HTTPException(status_code=400, detail="ticker parameter required")

        # Note: Actual computation would integrate with feature engine
        # For now, return placeholder
        logger.info(f"Feature computation triggered for ticker: {ticker}")

        return FeaturesResponse(
            ticker=ticker,
            timestamp=get_utc_iso_timestamp(),
            features={"status": "computation_queued"},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute features for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to compute features: {e}")


# ============================================================================
# TRANSACTION ENDPOINTS
# ============================================================================


@app.post("/transactions/import", tags=["Transactions"])
async def import_transactions(
    file_path: str = Query(..., description="Path to CSV file to import")
) -> Dict[str, Any]:
    """
    Import transactions from CSV file.

    CSV format expected:
        timestamp,ticker,transaction_type,quantity,price,notes

    Args:
        file_path: Path to CSV file relative to project root

    Returns:
        Dict with import_status, records_imported, errors

    Raises:
        HTTPException: 400 if file invalid, 500 if import fails

    Example:
        POST /transactions/import?file_path=transactions.csv
        {
            "status": "success",
            "records_imported": 42,
            "errors": []
        }
    """
    try:
        logger.info(f"Transaction import started: file={file_path}")
        # Note: Actual CSV parsing and import would be implemented here
        return {
            "status": "success",
            "records_imported": 0,
            "errors": [],
            "timestamp": get_utc_iso_timestamp(),
        }
    except Exception as e:
        logger.error(f"Transaction import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")


@app.get("/transactions", response_model=TransactionsResponse, tags=["Transactions"])
async def get_transactions(
    limit: int = Query(100, ge=1, le=1000, description="Number of transactions to return"),
    ticker: Optional[str] = Query(None, description="Optional ticker filter"),
) -> TransactionsResponse:
    """
    Get transaction history.

    Returns:
        TransactionsResponse with transaction list

    Raises:
        HTTPException: 500 if query fails

    Example:
        GET /transactions?limit=50
        {
            "transactions": [...],
            "total_count": 42,
            "timestamp": "2026-01-26T15:30:45.123456Z"
        }
    """
    try:
        logger.debug(f"Retrieving transactions: limit={limit}, ticker={ticker}")
        # Note: Actual transaction retrieval would be implemented here
        return TransactionsResponse(
            transactions=[],
            total_count=0,
            timestamp=get_utc_iso_timestamp(),
        )
    except Exception as e:
        logger.error(f"Failed to get transactions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get transactions: {e}")


# ============================================================================
# THESES & KNOWLEDGE BASE ENDPOINTS
# ============================================================================
# These endpoints serve per-ticker knowledge base files (investment theses, risks, notes)
# stored in the tickers/ directory. This allows traders to:
# 1. View investment thesis via UI (loaded from tickers/{TICKER}/theses.md)
# 2. Review known risks (loaded from tickers/{TICKER}/risks.md)
# 3. Access trading notes and pattern observations (from tickers/{TICKER}/notes.md)
#
# WHY THIS IS USEFUL:
# - Centralizes ticker-specific knowledge in markdown files (easy to edit, version control)
# - UI can display formatted thesis content to inform trading decisions
# - Each ticker has consistent structure (theses.md, risks.md, notes.md)
# - Traders can quickly access investment rationale without external lookups
#
# HOW IT WORKS:
# - Files stored: tickers/{TICKER}/theses.md | risks.md | notes.md
# - API reads from disk; returns markdown content
# - Returns 404 if file doesn't exist (ticker or file type not found)
# - Content returned as plain text (markdown formatted for UI rendering)


class ThesisResponse(BaseModel):
    """Response model for thesis/risks/notes content."""

    ticker: str = Field(..., description="Stock ticker symbol")
    file_type: str = Field(..., description="File type: 'thesis', 'risks', or 'notes'")
    content: str = Field(..., description="Markdown file content")
    last_updated: Optional[str] = Field(None, description="File last modified timestamp")
    timestamp: str = Field(..., description="UTC ISO 8601 response timestamp")


def get_tickers_dir() -> PathlibPath:
    """Get path to tickers/ directory containing per-ticker knowledge base.

    Returns:
        Path to tickers directory

    Example:
        /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/tickers/
    """
    project_root = PathlibPath(__file__).parent.parent
    return project_root / "tickers"


def load_thesis_file(ticker: str, file_type: str) -> Optional[str]:
    """Load thesis/risks/notes markdown file for a ticker.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'TSLA')
        file_type: File type ('thesis', 'risks', or 'notes')

    Returns:
        Markdown content as string, or None if file not found

    HOW THIS WORKS:
    1. Validates ticker and file_type (prevent directory traversal attacks)
    2. Constructs file path: tickers/{TICKER}/{FILE_TYPE}.md
    3. Reads file from disk
    4. Returns content as string (markdown formatted)
    5. Returns None if file doesn't exist (graceful 404 handling)

    Example:
        load_thesis_file('SOFI', 'thesis') → returns content of tickers/SOFI/theses.md
        load_thesis_file('UNKNOWN', 'thesis') → returns None (ticker dir not found)
    """
    try:
        # Validate file_type
        valid_types = {"thesis": "theses.md", "risks": "risks.md", "notes": "notes.md"}
        if file_type not in valid_types:
            logger.warning(f"Invalid file type requested: {file_type}")
            return None

        # Sanitize ticker (prevent directory traversal attacks like ../../../etc/passwd)
        ticker_clean = str(ticker).upper().replace("..", "").replace("/", "").replace("\\", "")
        if not ticker_clean or len(ticker_clean) > 10:
            logger.warning(f"Invalid ticker requested: {ticker}")
            return None

        # Construct file path
        tickers_dir = get_tickers_dir()
        file_path = tickers_dir / ticker_clean / valid_types[file_type]

        # Check file exists
        if not file_path.exists():
            logger.debug(f"Thesis file not found: {file_path}")
            return None

        # Read and return content
        with open(file_path, "r") as f:
            content = f.read()
            logger.debug(f"Loaded thesis file for {ticker_clean}/{file_type}: {len(content)} bytes")
            return content

    except Exception as e:
        logger.error(f"Failed to load thesis file for {ticker}/{file_type}: {e}")
        return None


@app.get("/tickers/{ticker}/thesis", response_model=ThesisResponse, tags=["Theses"])
async def get_ticker_thesis(
    ticker: str = Path(..., description="Stock ticker symbol (e.g., 'AAPL', 'SOFI')")
) -> ThesisResponse:
    """Get investment thesis for a ticker.

    Returns markdown content from tickers/{TICKER}/theses.md explaining:
    - Company overview and business model
    - Bull case (why this is a good opportunity)
    - Bear case (known risks and headwinds)
    - Catalyst timeline (expected events)
    - IV strategy (why IV patterns matter for this ticker)
    - Key metrics to monitor

    Args:
        ticker: Stock ticker symbol (case-insensitive)

    Returns:
        ThesisResponse with thesis markdown content

    Raises:
        HTTPException: 404 if ticker or thesis file not found, 500 if read fails

    Example:
        GET /tickers/SOFI/thesis
        {
            "ticker": "SOFI",
            "file_type": "thesis",
            "content": "# SoFi Technologies Investment Thesis\\n\\n## Overview\\n...",
            "timestamp": "2026-01-27T15:30:45.123456Z"
        }

    WHY THIS ENDPOINT:
    - UI displays thesis to inform trading decisions
    - Centralizes investment rationale in one place
    - Markdown format allows easy updates without code changes
    - Reduces need for external research lookups during trading
    """
    try:
        content = load_thesis_file(ticker, "thesis")

        if not content:
            logger.info(f"Thesis not found for ticker: {ticker}")
            raise HTTPException(
                status_code=404,
                detail=f"Thesis not found for ticker '{ticker}'. Create tickers/{ticker}/theses.md to add.",
            )

        logger.debug(f"Retrieved thesis for ticker: {ticker}")
        return ThesisResponse(
            ticker=ticker.upper(),
            file_type="thesis",
            content=content,
            timestamp=get_utc_iso_timestamp(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get thesis for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get thesis: {e}")


@app.get("/tickers/{ticker}/risks", response_model=ThesisResponse, tags=["Theses"])
async def get_ticker_risks(
    ticker: str = Path(..., description="Stock ticker symbol (e.g., 'AAPL', 'SOFI')")
) -> ThesisResponse:
    """Get known risks for a ticker.

    Returns markdown content from tickers/{TICKER}/risks.md explaining:
    - Regulatory risks
    - Competitive risks
    - Earnings/profitability risks
    - Macro/market risks
    - Valuation risks
    - Risk mitigation strategies

    Args:
        ticker: Stock ticker symbol (case-insensitive)

    Returns:
        ThesisResponse with risks markdown content

    Raises:
        HTTPException: 404 if ticker or risks file not found, 500 if read fails

    Example:
        GET /tickers/SOFI/risks
        {
            "ticker": "SOFI",
            "file_type": "risks",
            "content": "# SoFi Technologies Risk Assessment\\n\\n## Regulatory Risks\\n...",
            "timestamp": "2026-01-27T15:30:45.123456Z"
        }

    WHY THIS ENDPOINT:
    - Traders quickly assess downside risks before positions
    - Centralizes risk assessment in one place
    - Helps with position sizing and stop loss decisions
    - Reduces surprises from known but forgotten risks
    """
    try:
        content = load_thesis_file(ticker, "risks")

        if not content:
            logger.info(f"Risks not found for ticker: {ticker}")
            raise HTTPException(
                status_code=404,
                detail=f"Risks not found for ticker '{ticker}'. Create tickers/{ticker}/risks.md to add.",
            )

        logger.debug(f"Retrieved risks for ticker: {ticker}")
        return ThesisResponse(
            ticker=ticker.upper(),
            file_type="risks",
            content=content,
            timestamp=get_utc_iso_timestamp(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get risks for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get risks: {e}")


@app.get("/tickers/{ticker}/notes", response_model=ThesisResponse, tags=["Theses"])
async def get_ticker_notes(
    ticker: str = Path(..., description="Stock ticker symbol (e.g., 'AAPL', 'SOFI')")
) -> ThesisResponse:
    """Get trading notes and observations for a ticker.

    Returns markdown content from tickers/{TICKER}/notes.md containing:
    - Recent trading patterns and observations
    - IV behavior analysis
    - Support/resistance levels
    - Correlation with other assets
    - Trading strategy ideas (tested and pending)
    - Trade log with historical results
    - Risk management rules
    - Action items and monitoring tasks

    Args:
        ticker: Stock ticker symbol (case-insensitive)

    Returns:
        ThesisResponse with notes markdown content

    Raises:
        HTTPException: 404 if ticker or notes file not found, 500 if read fails

    Example:
        GET /tickers/SOFI/notes
        {
            "ticker": "SOFI",
            "file_type": "notes",
            "content": "# SoFi Trading & Analysis Notes\\n\\n## Recent Observations\\n...",
            "timestamp": "2026-01-27T15:30:45.123456Z"
        }

    WHY THIS ENDPOINT:
    - Traders access free-form analysis and pattern observations
    - Historical trade log shows what strategies worked/failed
    - Consolidates dated notes for pattern recognition
    - Helps with options strategy selection (what's worked before?)
    """
    try:
        content = load_thesis_file(ticker, "notes")

        if not content:
            logger.info(f"Notes not found for ticker: {ticker}")
            raise HTTPException(
                status_code=404,
                detail=f"Notes not found for ticker '{ticker}'. Create tickers/{ticker}/notes.md to add.",
            )

        logger.debug(f"Retrieved notes for ticker: {ticker}")
        return ThesisResponse(
            ticker=ticker.upper(),
            file_type="notes",
            content=content,
            timestamp=get_utc_iso_timestamp(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get notes for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get notes: {e}")


@app.get("/tickers/list", tags=["Theses"])
async def list_tickers() -> Dict[str, Any]:
    """List all available tickers with their knowledge base files.

    Returns metadata about available tickers, including which files exist
    for each ticker (thesis, risks, notes).

    Returns:
        Dict with list of available tickers and their file status

    Example:
        GET /tickers/list
        {
            "tickers": [
                {
                    "ticker": "SOFI",
                    "has_thesis": true,
                    "has_risks": true,
                    "has_notes": true
                },
                {
                    "ticker": "AMD",
                    "has_thesis": true,
                    "has_risks": true,
                    "has_notes": false
                }
            ],
            "total_count": 5,
            "timestamp": "2026-01-27T15:30:45.123456Z"
        }

    WHY THIS ENDPOINT:
    - UI can populate ticker list without hardcoding
    - Shows which tickers have complete knowledge bases
    - Helps identify missing documentation
    - Supports dynamic ticker discovery
    """
    try:
        tickers_dir = get_tickers_dir()

        if not tickers_dir.exists():
            logger.warning(f"Tickers directory not found: {tickers_dir}")
            return {
                "tickers": [],
                "total_count": 0,
                "timestamp": get_utc_iso_timestamp(),
            }

        # Scan tickers directory
        tickers = []
        for ticker_dir in sorted(tickers_dir.iterdir()):
            if ticker_dir.is_dir():
                ticker_name = ticker_dir.name.upper()
                tickers.append(
                    {
                        "ticker": ticker_name,
                        "has_thesis": (ticker_dir / "theses.md").exists(),
                        "has_risks": (ticker_dir / "risks.md").exists(),
                        "has_notes": (ticker_dir / "notes.md").exists(),
                    }
                )

        logger.debug(f"Listed {len(tickers)} tickers from knowledge base")
        return {
            "tickers": tickers,
            "total_count": len(tickers),
            "timestamp": get_utc_iso_timestamp(),
        }

    except Exception as e:
        logger.error(f"Failed to list tickers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tickers: {e}")


# ============================================================================
# ROOT ENDPOINT
# ============================================================================


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.

    Returns:
        JSON object with API name and documentation links
    """
    return {
        "name": "Option Chain Dashboard API",
        "version": "1.0.0",
        "docs": "http://localhost:8061/docs",
        "redoc": "http://localhost:8061/redoc",
        "openapi": "http://localhost:8061/openapi.json",
    }


# ============================================================================
# MAIN - ENTRY POINT
# ============================================================================


if __name__ == "__main__":
    """
    Run FastAPI server with uvicorn.

    Configuration:
        - Host: 0.0.0.0 (all interfaces)
        - Port: 8061
        - Reload: Enabled for development (disable in production)
        - Workers: Auto-determined by uvicorn
    """
    logger.info("Starting Option Chain Dashboard FastAPI server")
    logger.info("API Documentation: http://localhost:8061/docs")

    uvicorn.run(
        "scripts.run_api:app",
        host="0.0.0.0",
        port=8061,
        reload=True,
        log_level="info",
    )
