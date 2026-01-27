"""
Detector plugin system for identifying option chain anomalies and opportunities.

This module provides a registry-based plugin architecture for detecting various
market conditions and anomalies in option chains. Each detector analyzes specific
features and generates alerts when conditions are met.

Detectors available:
    - LowIVDetector: Identifies low implied volatility opportunities
    - RichPremiumDetector: Finds rich option premiums
    - EarningsCrushDetector: Detects potential earnings-related IV crush
    - TermKinkDetector: Identifies term structure anomalies
    - SkewAnomalyDetector: Detects skew reversals and anomalies
    - RegimeShiftDetector: Identifies volatility regime changes

Usage:
    >>> from functions.detect import get_registry
    >>> registry = get_registry()
    >>> alerts = []
    >>> for detector in registry.get_all_detectors():
    ...     detected = detector.detect(features)
    ...     alerts.extend(detected)
    >>> print(f"Found {len(alerts)} alerts")

Auto-registration:
    All detector plugins are automatically registered when this module is imported.
    New detectors can be added by creating a class that inherits from DetectorPlugin
    and implementing the required methods.
"""

from .base import AlertCandidate, DetectorPlugin, DetectorRegistry, get_registry
from .low_iv_detector import LowIVDetector
from .rich_premium_detector import RichPremiumDetector
from .earnings_crush_detector import EarningsCrushDetector
from .term_kink_detector import TermKinkDetector
from .skew_anomaly_detector import SkewAnomalyDetector
from .regime_shift_detector import RegimeShiftDetector

__all__ = [
    # Base classes and utilities
    "AlertCandidate",
    "DetectorPlugin",
    "DetectorRegistry",
    "get_registry",
    # Detector implementations
    "LowIVDetector",
    "RichPremiumDetector",
    "EarningsCrushDetector",
    "TermKinkDetector",
    "SkewAnomalyDetector",
    "RegimeShiftDetector",
]
