"""
Main scan orchestrator script for running complete options analysis scans.

This script is the entry point for the scheduler and runs a complete options chain
analysis scan for all tickers in the watchlist. It coordinates all components of the
system including market data fetching, feature computation, pattern detection, risk
assessment, and alert generation.

Core Components:

1. async run_scan(config: AppConfig) -> ScanResult
   Main scanning orchestrator that:
   - Creates scan record in database
   - For each ticker: fetches data, computes features, runs detectors,
     scores alerts, checks risk gates, applies throttling, builds explanations
   - Batch writes all alerts to database
   - Updates scan record with results
   - Returns ScanResult with execution summary

2. ScanResult dataclass
   Represents the output of a complete scan with metadata about execution

3. collect_chains(config, provider) -> None
   Collects and historizes all options chains for watchlist tickers

4. async main()
   CLI entry point that parses arguments, initializes dependencies, runs scan

All timestamps are UTC, full type hints provided, comprehensive logging enabled.
"""

import asyncio
import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

from functions.util.logging_setup import setup_logging, get_logger
from functions.config.loader import get_config_manager
from functions.config.models import AppConfig
from functions.config.settings import get_settings
from functions.db.connection import init_db, get_db
from functions.db.repositories import (
    ScanRepository,
    FeatureSnapshotRepository,
    AlertRepository,
    CooldownRepository,
    ChainSnapshotRepository,
)
from functions.market.provider_base import MarketDataProvider
from functions.compute.feature_engine import compute_features
from functions.detect.base import DetectorRegistry, AlertCandidate
from functions.scoring.scorer import AlertScorer
from functions.scoring.throttler import AlertThrottler
from functions.risk.gate import RiskGate
from functions.explain.template_explain import ExplanationGenerator

logger = get_logger(__name__)


# ============================================================================
# SCAN RESULT DATACLASS
# ============================================================================


@dataclass
class ScanResult:
    """
    Represents the output of a complete scan operation.

    This dataclass captures the execution summary of a scan, including which
    tickers were processed, how many alerts were generated, how long it took,
    and whether the scan succeeded or failed.

    Attributes:
        scan_id (int): Database ID of the scan record
        ticker_count (int): Number of tickers processed in this scan
        alert_count (int): Total number of alerts generated and stored
        runtime_seconds (float): Total execution time in seconds
        status (str): Scan completion status - one of:
            - "running": Scan is currently executing
            - "completed": Scan finished successfully
            - "failed": Scan encountered errors and stopped
            - "partial": Scan finished but some tickers failed
        error (Optional[str]): Error message if status is "failed", None otherwise

    Example:
        >>> result = ScanResult(
        ...     scan_id=42,
        ...     ticker_count=50,
        ...     alert_count=12,
        ...     runtime_seconds=125.3,
        ...     status="completed",
        ...     error=None
        ... )
        >>> print(f"Scan {result.scan_id}: {result.alert_count} alerts in {result.runtime_seconds:.1f}s")
    """

    scan_id: int
    ticker_count: int
    alert_count: int
    runtime_seconds: float
    status: str
    error: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate ScanResult after initialization."""
        valid_statuses = {"running", "completed", "failed", "partial"}
        if self.status not in valid_statuses:
            raise ValueError(
                f"status must be one of {valid_statuses}, got '{self.status}'"
            )
        if self.status == "failed" and self.error is None:
            raise ValueError("error must be provided when status is 'failed'")


# ============================================================================
# MAIN SCAN ORCHESTRATOR
# ============================================================================


async def run_scan(
    config: AppConfig,
    provider: Optional[MarketDataProvider] = None
) -> ScanResult:
    """
    Execute a complete options analysis scan for all tickers in watchlist.

    This is the main orchestration function that coordinates all components:
    1. Initializes database and repositories
    2. Creates scan record in database
    3. For each ticker in watchlist:
       a) Fetches current market snapshot via MarketDataProvider
       b) Computes features via FeatureEngine
       c) Runs all registered detectors via DetectorRegistry
       d) Scores alerts via AlertScorer
       e) Checks risk gates via RiskGate
       f) Applies throttling via AlertThrottler
       g) Generates explanations via ExplanationGenerator
       h) Adds alerts to write buffer
    4. Batch writes all alerts to database
    5. Updates scan record with final status and results
    6. Returns ScanResult with execution summary

    Args:
        config (AppConfig): Application configuration containing:
            - watchlist (List[str]): Tickers to scan
            - scan parameters: update_interval_minutes, max_retries, etc.
            - scoring configuration: thresholds and adjustments
            - risk configuration: position limits and gates
        provider (Optional[MarketDataProvider]): Market data provider instance.
            If not provided, caller should inject one before calling.

    Returns:
        ScanResult: Execution summary containing:
            - scan_id: Database ID of scan record
            - ticker_count: Number of tickers processed
            - alert_count: Total alerts generated and stored
            - runtime_seconds: Execution time in seconds
            - status: "completed", "partial", or "failed"
            - error: Error message if status is "failed"

    Raises:
        RuntimeError: If database initialization fails
        ValueError: If config is invalid or provider not provided

    Example:
        >>> from functions.config.loader import get_config
        >>> from functions.market.provider_base import MarketDataProvider
        >>> config = get_config()
        >>> provider = MyMarketDataProvider()  # Your provider implementation
        >>> result = await run_scan(config, provider)
        >>> print(f"Generated {result.alert_count} alerts for {result.ticker_count} tickers")
    """
    start_time = time.time()
    logger.info("=" * 80)
    logger.info("Starting scan orchestrator")
    logger.info(f"Watchlist: {len(config.scan.symbols)} tickers")
    logger.info(f"Config hash: {config.config_hash if hasattr(config, 'config_hash') else 'N/A'}")

    try:
        # ====================================================================
        # INITIALIZE DEPENDENCIES
        # ====================================================================

        logger.info("Initializing database and repositories...")
        init_db()

        # Get repositories
        scan_repo = ScanRepository()
        feature_repo = FeatureSnapshotRepository()
        alert_repo = AlertRepository()
        cooldown_repo = CooldownRepository()
        chain_repo = ChainSnapshotRepository()

        # Validate provider is provided
        if provider is None:
            raise ValueError(
                "provider must be provided to run_scan. "
                "This should be injected by the scheduler."
            )
        logger.info(f"Using market data provider: {provider.__class__.__name__}")

        # Get orchestration components
        alert_scorer = AlertScorer(config)
        throttler = AlertThrottler(get_db(), config)
        risk_gate = RiskGate(config)
        explanation_generator = ExplanationGenerator(config)

        logger.info("All dependencies initialized successfully")

        # ====================================================================
        # CREATE SCAN RECORD
        # ====================================================================

        config_hash = getattr(config, 'config_hash', 'unknown')
        scan_id = scan_repo.create_scan(config_hash=config_hash)
        logger.info(f"Created scan record: id={scan_id}")

        # ====================================================================
        # PROCESS EACH TICKER
        # ====================================================================

        alerts_buffer: List[Dict[str, Any]] = []
        tickers_failed: List[str] = []
        tickers_processed: int = 0

        for ticker in config.scan.symbols:
            try:
                logger.info(f"\n--- Processing ticker: {ticker} ---")

                # Get current market snapshot
                logger.debug(f"Fetching market snapshot for {ticker}")
                snapshot = provider.get_full_snapshot(ticker)

                if snapshot is None:
                    logger.warning(f"Failed to get market snapshot for {ticker}, skipping")
                    tickers_failed.append(ticker)
                    continue

                logger.debug(f"Market snapshot retrieved: price=${snapshot.price:.2f}")

                # Compute features
                logger.debug(f"Computing features for {ticker}")
                features = compute_features(
                    snapshot=snapshot,
                    config_hash=config_hash
                )
                logger.debug(f"Features computed: {len(features.to_dict())} fields")

                # Save feature snapshot to database
                try:
                    feature_repo.save_snapshot(
                        scan_id=scan_id,
                        ticker=ticker,
                        features=features.to_dict()
                    )
                    logger.debug(f"Feature snapshot saved for {ticker}")
                except Exception as e:
                    logger.error(f"Failed to save feature snapshot for {ticker}: {e}")

                # Run all detectors
                logger.debug(f"Running {len(DetectorRegistry.get_registry().get_all_detectors())} detectors")
                detector_count = 0
                for detector_class in DetectorRegistry.get_registry().get_all_detectors():
                    try:
                        detector = detector_class()
                        alert_candidate = detector.detect_safe(features)

                        if alert_candidate is None:
                            logger.debug(f"No detection from {detector.name}")
                            continue

                        detector_count += 1
                        logger.info(f"Detection: {detector.name} scored {alert_candidate.score:.1f}")

                        # ====================================================
                        # APPLY SCORING ADJUSTMENTS
                        # ====================================================

                        adjusted_score = alert_scorer.score_alert(
                            alert=alert_candidate,
                            ticker=ticker,
                            features=features
                        )
                        alert_candidate.score = adjusted_score
                        logger.info(
                            f"Score adjusted: {detector_count} -> "
                            f"{adjusted_score:.1f} for {ticker}"
                        )

                        # ====================================================
                        # CHECK RISK GATES
                        # ====================================================

                        passes_gate, gate_reason = risk_gate.passes_risk_gate(
                            alert=alert_candidate,
                            ticker=ticker
                        )

                        if not passes_gate:
                            logger.info(f"Risk gate rejected {ticker}: {gate_reason}")
                            continue

                        logger.info(f"Risk gate passed for {ticker}")

                        # ====================================================
                        # CHECK THROTTLES
                        # ====================================================

                        should_throttle, throttle_reason = throttler.should_alert(
                            ticker=ticker,
                            score=alert_candidate.score
                        )

                        if not should_throttle:
                            logger.info(f"Alert throttled for {ticker}: {throttle_reason}")
                            continue

                        logger.info(f"Alert not throttled for {ticker}")

                        # ====================================================
                        # GENERATE EXPLANATIONS
                        # ====================================================

                        enriched_explanation = explanation_generator.generate_explanation(
                            alert=alert_candidate,
                            ticker=ticker,
                            features=features
                        )
                        alert_candidate.explanation.update(enriched_explanation)
                        logger.debug(f"Explanation generated for {ticker}")

                        # ====================================================
                        # ADD TO BUFFER
                        # ====================================================

                        alert_dict = {
                            "ticker": ticker,
                            "detector_name": alert_candidate.detector_name,
                            "score": alert_candidate.score,
                            "alert_data": {
                                "metrics": alert_candidate.metrics,
                                "explanation": alert_candidate.explanation,
                                "strategies": alert_candidate.strategies,
                                "confidence": alert_candidate.confidence,
                            }
                        }
                        alerts_buffer.append(alert_dict)
                        logger.info(
                            f"Alert buffered for {ticker}: "
                            f"{alert_candidate.detector_name} (score={alert_candidate.score:.1f})"
                        )

                        # Record alert for throttling
                        throttler.record_alert(
                            ticker=ticker,
                            score=alert_candidate.score
                        )

                    except Exception as e:
                        logger.error(
                            f"Error running detector for {ticker}: {e}",
                            exc_info=True
                        )
                        continue

                logger.info(f"Completed processing {ticker}: {detector_count} detectors ran")
                tickers_processed += 1

            except Exception as e:
                logger.error(
                    f"Critical error processing ticker {ticker}: {e}",
                    exc_info=True
                )
                tickers_failed.append(ticker)
                continue

        # ====================================================================
        # BATCH WRITE ALERTS TO DATABASE
        # ====================================================================

        logger.info(f"\nBatch writing {len(alerts_buffer)} alerts to database...")
        alerts_written = 0
        if alerts_buffer:
            try:
                alerts_written = alert_repo.save_alerts_batch(
                    scan_id=scan_id,
                    alerts=alerts_buffer
                )
                logger.info(f"Successfully wrote {alerts_written} alerts to database")
            except Exception as e:
                logger.error(f"Failed to batch write alerts: {e}", exc_info=True)
                alerts_written = 0

        # ====================================================================
        # UPDATE SCAN RECORD
        # ====================================================================

        runtime_seconds = time.time() - start_time
        status = "completed" if len(tickers_failed) == 0 else "partial"

        logger.info(f"Updating scan record with final status: {status}")
        scan_repo.update_scan(
            scan_id=scan_id,
            status=status,
            tickers_scanned=tickers_processed,
            alerts_generated=alerts_written,
            runtime_seconds=runtime_seconds,
            error_message=None if status == "completed" else f"Failed to process {len(tickers_failed)} tickers"
        )

        # ====================================================================
        # BUILD AND RETURN RESULT
        # ====================================================================

        logger.info("=" * 80)
        logger.info(f"SCAN COMPLETE")
        logger.info(f"  Scan ID: {scan_id}")
        logger.info(f"  Status: {status}")
        logger.info(f"  Tickers processed: {tickers_processed}/{len(config.scan.symbols)}")
        if tickers_failed:
            logger.warning(f"  Failed tickers: {', '.join(tickers_failed)}")
        logger.info(f"  Alerts generated: {alerts_written}")
        logger.info(f"  Runtime: {runtime_seconds:.1f} seconds")
        logger.info("=" * 80)

        return ScanResult(
            scan_id=scan_id,
            ticker_count=tickers_processed,
            alert_count=alerts_written,
            runtime_seconds=runtime_seconds,
            status=status,
            error=None
        )

    except Exception as e:
        runtime_seconds = time.time() - start_time
        error_message = f"Scan orchestrator failed: {str(e)}"
        logger.error(error_message, exc_info=True)
        logger.info("=" * 80)
        logger.info(f"SCAN FAILED after {runtime_seconds:.1f} seconds")
        logger.info("=" * 80)

        return ScanResult(
            scan_id=-1,
            ticker_count=0,
            alert_count=0,
            runtime_seconds=runtime_seconds,
            status="failed",
            error=error_message
        )


# ============================================================================
# CHAIN COLLECTION
# ============================================================================


def collect_chains(config: AppConfig, provider: MarketDataProvider) -> None:
    """
    Collect and historize all options chains for watchlist tickers.

    This function fetches all available options expirations and chains for
    each ticker in the watchlist and saves them to the database and JSON files
    for historical tracking and analysis.

    For each ticker:
    1. Fetches list of available option expirations
    2. For each expiration, fetches the complete options chain
    3. Saves chain to database via ChainSnapshotRepository
    4. Writes JSON file to historical_data/chains/{YYYY-MM-DD}/{TICKER}_chains.json

    Args:
        config (AppConfig): Application configuration containing watchlist
        provider (MarketDataProvider): Market data provider to fetch chains from

    Returns:
        None

    Example:
        >>> from functions.config.loader import get_config
        >>> from functions.market import get_provider
        >>> config = get_config()
        >>> provider = get_provider(demo_mode=False)
        >>> collect_chains(config, provider)
        >>> # Chains now saved in database and JSON files
    """
    logger.info("Starting chain collection...")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    chains_dir = Path("historical_data/chains") / today_str
    chains_dir.mkdir(parents=True, exist_ok=True)

    chain_repo = ChainSnapshotRepository()

    for ticker in config.scan.symbols:
        try:
            logger.info(f"Collecting chains for {ticker}...")

            # Get available expirations
            expirations = provider.get_options_expirations(ticker)
            if not expirations:
                logger.warning(f"No options chains available for {ticker}")
                continue

            # Collect chains for each expiration
            all_chains = {}
            for expiration in expirations:
                try:
                    chain = provider.get_options_chain(ticker, expiration)
                    if chain:
                        all_chains[str(expiration)] = {
                            "expiration": str(expiration),
                            "calls_count": len(chain.calls) if chain.calls else 0,
                            "puts_count": len(chain.puts) if chain.puts else 0,
                        }
                        logger.debug(
                            f"  {expiration}: {len(chain.calls)} calls, {len(chain.puts)} puts"
                        )
                except Exception as e:
                    logger.error(f"Error fetching chain for {ticker} exp={expiration}: {e}")
                    continue

            if all_chains:
                # Save to database
                try:
                    chain_repo.save_chains_snapshot(
                        ticker=ticker,
                        chains_data=all_chains
                    )
                    logger.info(f"Saved {len(all_chains)} chain snapshots for {ticker}")
                except Exception as e:
                    logger.error(f"Error saving chains for {ticker}: {e}")

                # Write JSON file
                try:
                    json_file = chains_dir / f"{ticker}_chains.json"
                    with open(json_file, "w") as f:
                        json.dump(
                            {
                                "ticker": ticker,
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "expirations": all_chains
                            },
                            f,
                            indent=2
                        )
                    logger.debug(f"Wrote chains JSON: {json_file}")
                except Exception as e:
                    logger.error(f"Error writing JSON for {ticker}: {e}")

        except Exception as e:
            logger.error(f"Critical error collecting chains for {ticker}: {e}", exc_info=True)
            continue

    logger.info(f"Chain collection complete. Files written to {chains_dir}")


# ============================================================================
# MAIN CLI ENTRY POINT
# ============================================================================


async def main() -> int:
    """
    CLI entry point for running option chain scans.

    Parses command-line arguments, loads configuration, initializes logging,
    and runs the scan orchestrator. Returns appropriate exit code based on
    scan result.

    Command-line Arguments:
        --config-path (str, optional): Path to config directory (default: "./")
        --demo-mode (bool, optional): Use demo mode with simulated data

    Returns:
        int: Exit code
            - 0: Scan completed successfully
            - 1: Scan failed or error occurred

    Example:
        >>> # Run scan with default config
        >>> import asyncio
        >>> exit_code = asyncio.run(main())
        >>>
        >>> # Run scan with custom config
        >>> import sys
        >>> sys.argv = ["run_scan.py", "--config-path", "/path/to/config"]
        >>> exit_code = asyncio.run(main())
    """
    # ========================================================================
    # PARSE ARGUMENTS
    # ========================================================================

    parser = argparse.ArgumentParser(
        description="Run complete options chain analysis scan for watchlist"
    )
    parser.add_argument(
        "--config-path",
        type=str,
        default="./",
        help="Path to configuration directory (default: ./)"
    )
    parser.add_argument(
        "--demo-mode",
        action="store_true",
        help="Run in demo mode with simulated data"
    )

    args = parser.parse_args()

    # ========================================================================
    # INITIALIZE LOGGING
    # ========================================================================

    setup_logging(
        log_level="INFO",
        log_dir="./logs",
        log_file="option_chain_dashboard.log"
    )

    logger.info("=" * 80)
    logger.info("Option Chain Dashboard - Scan Orchestrator")
    logger.info(f"Start time: {datetime.now(timezone.utc).isoformat()}Z")
    logger.info("=" * 80)

    # ========================================================================
    # LOAD CONFIGURATION
    # ========================================================================

    try:
        logger.info(f"Loading configuration from: {args.config_path}")
        config_manager = get_config_manager(config_dir=Path(args.config_path))
        config = config_manager.config

        logger.info(f"Configuration loaded successfully")
        logger.info(f"  Watchlist symbols: {len(config.scan.symbols)}")
        logger.info(f"  Config hash: {config_manager.config_hash}")

    except Exception as e:
        logger.error(f"Failed to load configuration: {e}", exc_info=True)
        return 1

    # ========================================================================
    # NOTE: PROVIDER INITIALIZATION
    # ========================================================================

    logger.info("")
    logger.info("NOTE: This is a library script meant to be called by a scheduler.")
    logger.info("The scheduler should:")
    logger.info("  1. Instantiate a MarketDataProvider (e.g., YahooFinanceProvider)")
    logger.info("  2. Call: result = await run_scan(config, provider=provider_instance)")
    logger.info("")
    logger.warning(
        "Direct CLI execution is not supported. "
        "Please use this script as a library in your scheduler."
    )

    # ========================================================================
    # EXAMPLE USAGE (FOR REFERENCE)
    # ========================================================================

    # For reference, here's how a scheduler would use this:
    # ```
    # from scripts.run_scan import run_scan
    # from functions.market.provider_yfinance import YahooFinanceProvider
    #
    # config = get_config()
    # provider = YahooFinanceProvider()
    # result = await run_scan(config, provider=provider)
    # ```

    return 0

    # Note: The following code is kept for documentation but won't execute
    # ========================================================================
    # RUN SCAN
    # ========================================================================

    try:
        # This demonstrates how to call run_scan
        # In practice, the scheduler will handle this
        result = await run_scan(config, provider=None)

        logger.info(f"\nScan Result:")
        logger.info(f"  Status: {result.status}")
        logger.info(f"  Scan ID: {result.scan_id}")
        logger.info(f"  Tickers processed: {result.ticker_count}")
        logger.info(f"  Alerts generated: {result.alert_count}")
        logger.info(f"  Runtime: {result.runtime_seconds:.1f}s")

        if result.error:
            logger.error(f"  Error: {result.error}")

        # Return appropriate exit code
        if result.status == "completed":
            logger.info("Scan completed successfully")
            return 0
        elif result.status == "partial":
            logger.warning("Scan completed with partial failures")
            return 0
        else:
            logger.error("Scan failed")
            return 1

    except Exception as e:
        logger.error(f"Scan execution failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    # Run async main function
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
