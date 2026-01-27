"""
Abstract base classes and registry for anomaly/pattern detection system.

This module provides the foundation for the detection system, defining the core
interfaces and mechanisms that all detectors must implement.

Core Components:
    - AlertCandidate: Dataclass representing a detection result that passed risk gates
    - DetectorPlugin: Abstract base class for all detector implementations
    - DetectorRegistry: Singleton registry managing detector lifecycle and lookup

Design Patterns:
    - Plugin Architecture: Detectors register themselves and are discovered dynamically
    - Singleton Registry: Single shared registry instance across application
    - Safe Execution: detect_safe() wrapper catches exceptions and never crashes caller
    - Configuration Isolation: Each detector defines its own config.yaml key

Risk Gate Requirement:
    All AlertCandidate scores must be >= 60 to pass risk gates and be considered
    valid trading opportunities. Scores below 60 indicate insufficiently qualified
    opportunities and are filtered out at portfolio level.

Usage:
    from functions.detect.base import DetectorPlugin, DetectorRegistry, AlertCandidate
    from functions.compute.feature_engine import FeatureSet

    class VolumeSpikeDet(DetectorPlugin):
        @property
        def name(self) -> str:
            return "VolumeSpikeDetector"

        @property
        def description(self) -> str:
            return "Detects unusual volume spikes in options chains"

        def get_config_key(self) -> str:
            return "detectors.volume_spike"

        def detect(self, features: FeatureSet) -> Optional[AlertCandidate]:
            # Implementation
            pass

    # Register detector
    registry = DetectorRegistry.get_registry()
    registry.register(VolumeSpikeDet)

    # Get all detectors
    for detector_class in registry.get_all_detectors():
        detector = detector_class()
        alert = detector.detect_safe(features)
        if alert:
            print(f"Alert from {detector.name}: {alert.explanation}")

Configuration Structure:
    Detectors are configured via config.yaml with keys like:
    - detectors.volume_spike:
        enabled: true
        thresholds:
          pct: 150.0
    - detectors.volatility_expansion:
        enabled: true
        thresholds:
          pct: 25.0

    Each detector is responsible for reading its config via get_config_key().
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Type, Any

from functions.util.logging_setup import get_logger
from functions.compute.feature_engine import FeatureSet
from functions.config.models import AppConfig

logger = get_logger(__name__)


# ============================================================================
# ALERT CANDIDATE DATACLASS
# ============================================================================


@dataclass
class AlertCandidate:
    """
    Represents a detection result that passed risk gates and is actionable.

    An AlertCandidate is created when a detector identifies a potential trading
    opportunity that meets or exceeds all risk thresholds. The score field
    determines portfolio-level filtering and ranking.

    Risk Gate Rule:
        score >= 60 is required to pass risk gates. Scores below 60 indicate
        the opportunity does not meet minimum risk/reward or probability standards.

    Attributes:
        detector_name (str):
            Class name of the detector that generated this alert.
            Example: "VolumeSpikeDetector", "UnusualActivityDetector"
            Used for tracking alert origin and filtering by detector type.

        score (float):
            Numerical score from 0-100 representing the quality/strength of the alert.
            - Score < 60: Fails risk gates, filtered at portfolio level
            - 60 <= Score < 75: Passes gates, medium confidence opportunity
            - 75 <= Score < 90: Strong opportunity
            - 90+: Very strong opportunity

            Typically calculated as weighted sum of:
            - Severity/magnitude of detection (e.g., how extreme is volume spike)
            - Confidence in the detection
            - Risk/reward ratio for proposed strategies
            - Liquidity and tradability assessment

        metrics (Dict[str, Any]):
            Key performance indicators that triggered the alert.
            Used for alert summaries, ranking, and debugging.

            Example for volume spike:
            {
                "current_volume": 500000,
                "avg_volume": 100000,
                "volume_ratio": 5.0,
                "spike_pct": 400.0,
                "z_score": 3.2
            }

            Example for volatility expansion:
            {
                "current_iv": 0.45,
                "historical_iv_20d": 0.30,
                "iv_ratio": 1.5,
                "expansion_pct": 50.0,
                "vol_percentile": 85
            }

        explanation (Dict[str, Any]):
            Human-readable explanation data for the alert.
            Used by LLM explainers and dashboards to communicate findings.

            Must contain:
                - "summary" (str): 1-2 sentence explanation of what was detected
                - "reason" (str): Why this matters for trading (risk/opportunity)
                - "trigger" (str): Which metric crossed which threshold
                - Additional context as needed (e.g., recent price action, earnings)

            Example:
            {
                "summary": "Unusual volume spike in front-month calls (5x average)",
                "reason": "High volume can indicate institutional positioning or event catalyst",
                "trigger": "Call volume (500k) exceeded 4x threshold (100k avg)",
                "price_context": "Price near 52-week high",
                "earnings_days": 12
            }

        strategies (List[str]):
            Named strategies that could be used to trade this opportunity.
            Each string is a descriptive strategy name that traders would recognize.

            Common strategy names:
            - "Long Call Spread" (bullish, defined risk)
            - "Short Call Spread" (bearish, defined risk)
            - "Straddle" (volatility increase bet)
            - "Iron Condor" (range-bound bet)
            - "Call Ratio Spread" (complex, hedged)
            - "Protective Put" (downside hedge)
            - "Covered Call" (income generation)

            Strategy suggestions come from analyzing:
            - Detector type and the opportunity it found
            - Current volatility regime
            - Price momentum and technical levels
            - Available liquidity in options chain

        confidence (str):
            Confidence level of the detection result.
            Must be one of: "low", "medium", "high"

            Determines how much weight the alert gets in portfolio decisions:
            - "low": Experimental detection or weak signals, use cautiously
            - "medium": Standard detections with typical confidence levels
            - "high": Very reliable detection with strong supporting evidence

            Examples:
            - Volume spike at 8x average: "high"
            - Volume spike at 1.5x average: "low"
            - Volatility term structure inversion with 6+ expirations: "high"
            - Term structure inversion with only 2 expirations: "low"
    """

    detector_name: str
    # Class name of detector that generated this alert (e.g., "VolumeSpikeDetector")

    score: float
    # Alert quality score 0-100. Must be >= 60 to pass risk gates

    metrics: Dict[str, Any] = field(default_factory=dict)
    # Key metrics that triggered the alert (volume_ratio, spike_pct, etc.)

    explanation: Dict[str, Any] = field(default_factory=dict)
    # Human-readable explanation with "summary", "reason", "trigger" keys

    strategies: List[str] = field(default_factory=list)
    # Named strategies to consider (e.g., "Long Call Spread", "Iron Condor")

    confidence: str = field(default="medium")
    # Confidence level: "low", "medium", or "high"

    def __post_init__(self) -> None:
        """
        Validate AlertCandidate after initialization.

        Ensures:
        - detector_name is non-empty string
        - score is in valid range [0, 100]
        - confidence is one of the allowed values
        - metrics and explanation are dictionaries
        - strategies is a list of strings
        - score >= 60 for passing risk gates

        Raises:
            ValueError: If any validation fails
        """
        # Validate detector_name
        if not isinstance(self.detector_name, str) or not self.detector_name.strip():
            raise ValueError(
                f"detector_name must be non-empty string, got {self.detector_name}"
            )

        # Validate score
        if not isinstance(self.score, (int, float)):
            raise ValueError(
                f"score must be numeric, got {type(self.score).__name__}"
            )
        if not 0 <= self.score <= 100:
            raise ValueError(
                f"score must be between 0-100, got {self.score}"
            )
        if self.score < 60:
            logger.warning(
                f"AlertCandidate score {self.score} is below risk gate threshold (60). "
                f"This alert will be filtered at portfolio level."
            )

        # Validate confidence
        valid_confidence = {"low", "medium", "high"}
        if self.confidence not in valid_confidence:
            raise ValueError(
                f"confidence must be one of {valid_confidence}, got '{self.confidence}'"
            )

        # Validate metrics is dict
        if not isinstance(self.metrics, dict):
            raise ValueError(
                f"metrics must be dict, got {type(self.metrics).__name__}"
            )

        # Validate explanation is dict
        if not isinstance(self.explanation, dict):
            raise ValueError(
                f"explanation must be dict, got {type(self.explanation).__name__}"
            )

        # Validate explanation has required keys
        required_explanation_keys = {"summary", "reason", "trigger"}
        missing_keys = required_explanation_keys - set(self.explanation.keys())
        if missing_keys:
            raise ValueError(
                f"explanation missing required keys: {missing_keys}"
            )

        # Validate strategies is list of strings
        if not isinstance(self.strategies, list):
            raise ValueError(
                f"strategies must be list, got {type(self.strategies).__name__}"
            )
        for strategy in self.strategies:
            if not isinstance(strategy, str):
                raise ValueError(
                    f"all strategies must be strings, got {type(strategy).__name__}"
                )


# ============================================================================
# DETECTOR PLUGIN ABSTRACT BASE CLASS
# ============================================================================


class DetectorPlugin(ABC):
    """
    Abstract base class for all anomaly/pattern detectors.

    Detectors analyze market data features and identify potential trading
    opportunities based on detected patterns, anomalies, or market conditions.

    Each detector must implement:
    1. name property: Human-readable detector name
    2. description property: What this detector does
    3. get_config_key(): Config key for this detector's settings
    4. detect(): Core detection logic (can return None if no alert)

    The detect_safe() method provides exception handling and logging.

    Abstract Methods:
        - name: Returns detector name (e.g., "VolumeSpikeDetector")
        - description: Returns what detector does
        - get_config_key(): Returns config.yaml key (e.g., "detectors.volume_spike")
        - detect(): Analyzes features, returns AlertCandidate or None

    Example Implementation:
        class VolumeSpikeDet(DetectorPlugin):
            @property
            def name(self) -> str:
                return "VolumeSpikeDetector"

            @property
            def description(self) -> str:
                return "Detects unusual volume spikes"

            def get_config_key(self) -> str:
                return "detectors.volume_spike"

            def detect(self, features: FeatureSet) -> Optional[AlertCandidate]:
                # Get current volume from features
                vol = features.options_front.get("volume", 0)
                # Compare to historical average
                # If spike detected, return AlertCandidate
                # Otherwise return None
                return AlertCandidate(...) or None

    Error Handling:
        The detect_safe() wrapper ensures that all exceptions are caught,
        logged, and never propagated to the caller. This guarantees that
        a single broken detector doesn't crash the entire system.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the detector's name.

        Returns:
            str: Human-readable detector name
                Example: "VolumeSpikeDetector", "VolatilityExpansionDetector"

        Note:
            This should return the class name or a stable identifier.
            Used for alert tracking, logging, and debugging.
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Get the detector's description.

        Returns:
            str: Brief description of what this detector identifies
                Example: "Detects unusual volume spikes in options chains"

        Note:
            Used for dashboard/documentation purposes.
        """
        pass

    @abstractmethod
    def get_config_key(self) -> str:
        """
        Get the configuration key for this detector.

        Returns:
            str: The key in config.yaml where this detector's settings are stored
                Example: "detectors.volume_spike"

        Note:
            Config at this key should follow the pattern:
            {
                "enabled": true/false,
                "thresholds": {...detector-specific settings...}
            }
        """
        pass

    @abstractmethod
    def detect(self, features: FeatureSet) -> Optional[AlertCandidate]:
        """
        Execute core detection logic on feature set.

        This is the main detector algorithm. It should analyze the provided
        FeatureSet and return an AlertCandidate if an opportunity is detected,
        or None if no alert is warranted.

        Args:
            features (FeatureSet): Comprehensive feature set for a ticker at a point in time.
                Contains price data, technicals, volatility, options metrics, etc.

        Returns:
            AlertCandidate: If detection succeeded and opportunity meets all thresholds.
                Must have score >= 60 to pass risk gates.
            None: If no detection or detection does not meet thresholds.

        Raises:
            Should not raise exceptions. If something goes wrong, log and return None.
            Exception handling is done by detect_safe() wrapper.

        Implementation Notes:
            - Use config.yaml via get_config_key() for detector parameters
            - Log detection process for debugging (DEBUG level) and major events (INFO)
            - Return None if insufficient data to make decision
            - Always populate explanation field in AlertCandidate
        """
        pass

    def detect_safe(self, features: FeatureSet) -> Optional[AlertCandidate]:
        """
        Execute detection with exception handling and logging.

        This wrapper calls detect() and ensures that:
        1. All exceptions are caught and logged
        2. Errors never propagate to caller
        3. System remains stable even if detector fails
        4. Failed detections return None gracefully

        This method should be called by orchestration code, not detect()
        directly. It's the "safe" entry point to the detection system.

        Args:
            features (FeatureSet): Feature set to analyze

        Returns:
            AlertCandidate: If detection succeeded and alert is valid
            None: If detection failed or no alert triggered

        Example:
            >>> from functions.detect.base import DetectorRegistry
            >>> registry = DetectorRegistry.get_registry()
            >>> for detector_class in registry.get_all_detectors():
            ...     detector = detector_class()
            ...     alert = detector.detect_safe(features)  # Never crashes
            ...     if alert:
            ...         process_alert(alert)
        """
        try:
            logger.debug(f"Starting detection: {self.name}")

            # Call the actual detection logic
            result = self.detect(features)

            # Validate result is None or AlertCandidate
            if result is not None:
                if not isinstance(result, AlertCandidate):
                    logger.error(
                        f"Detector {self.name} returned invalid type {type(result).__name__}. "
                        f"Expected AlertCandidate or None."
                    )
                    return None

                logger.info(
                    f"Detection successful from {self.name}: score={result.score}, "
                    f"confidence={result.confidence}"
                )
                return result
            else:
                logger.debug(f"No detection from {self.name}")
                return None

        except Exception as e:
            logger.error(
                f"Exception in detector {self.name}: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            return None


# ============================================================================
# DETECTOR REGISTRY (SINGLETON)
# ============================================================================


class DetectorRegistry:
    """
    Singleton registry for managing detector lifecycle and discovery.

    The registry is responsible for:
    1. Recording detector classes when they're registered
    2. Instantiating detectors on demand
    3. Providing access to all available detectors
    4. Preventing duplicate registrations

    This uses the singleton pattern to ensure a single registry instance
    across the entire application.

    Usage:
        # Get the singleton registry
        registry = DetectorRegistry.get_registry()

        # Register a detector class
        registry.register(VolumeSpikeDetector)
        registry.register(VolatilityExpansionDetector)

        # Get all detector instances
        for detector_class in registry.get_all_detectors():
            detector = detector_class()
            alert = detector.detect_safe(features)

        # Get specific detector
        detector = registry.get_detector("VolumeSpikeDetector")
        if detector:
            alert = detector.detect(features)

    Thread Safety:
        Current implementation is not thread-safe. In production, use
        threading.Lock or similar synchronization if needed.
    """

    _instance: Optional['DetectorRegistry'] = None
    _detectors: Dict[str, Type[DetectorPlugin]] = {}

    def __new__(cls) -> 'DetectorRegistry':
        """Enforce singleton pattern - only one registry instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            logger.debug("Created new DetectorRegistry singleton instance")
        return cls._instance

    @classmethod
    def register(cls, detector_class: Type[DetectorPlugin]) -> None:
        """
        Register a detector class with the registry.

        This class method allows detectors to register themselves at import time,
        enabling automatic discovery.

        Args:
            detector_class (Type[DetectorPlugin]): The detector class to register
                Must be a subclass of DetectorPlugin
                Must implement all abstract methods (name, description, get_config_key, detect)

        Raises:
            TypeError: If detector_class is not a DetectorPlugin subclass
            ValueError: If detector_class is already registered (duplicate)

        Example:
            @DetectorRegistry.register
            class VolumeSpikeDetector(DetectorPlugin):
                @property
                def name(self) -> str:
                    return "VolumeSpikeDetector"
                # ... rest of implementation

            # Alternative: register after definition
            DetectorRegistry.register(VolumeSpikeDetector)

        Note:
            The detector_class is stored, not instantiated. Instances are
            created on demand via get_detector() or get_all_detectors().
        """
        # Validate it's a DetectorPlugin subclass
        if not issubclass(detector_class, DetectorPlugin):
            raise TypeError(
                f"Detector class must be a DetectorPlugin subclass, "
                f"got {detector_class.__name__}"
            )

        # Get the detector name (need temporary instance)
        try:
            temp_instance = detector_class()
            detector_name = temp_instance.name
        except Exception as e:
            raise ValueError(
                f"Failed to instantiate {detector_class.__name__} for name lookup: {e}"
            ) from e

        # Check for duplicates
        if detector_name in cls._detectors:
            existing = cls._detectors[detector_name]
            if existing is detector_class:
                logger.warning(
                    f"Detector {detector_name} already registered (duplicate)"
                )
                return
            else:
                raise ValueError(
                    f"Detector name collision: {detector_name} registered twice "
                    f"({existing.__name__} and {detector_class.__name__})"
                )

        # Register the detector
        cls._detectors[detector_name] = detector_class
        logger.info(f"Registered detector: {detector_name}")

    @classmethod
    def get_detector(cls, name: str) -> Optional[DetectorPlugin]:
        """
        Get a detector instance by name.

        Looks up the detector class in the registry and instantiates it.

        Args:
            name (str): The detector name to look up
                Example: "VolumeSpikeDetector"

        Returns:
            DetectorPlugin: An instance of the requested detector class
            None: If detector not found

        Raises:
            Exception: If detector class cannot be instantiated

        Example:
            >>> registry = DetectorRegistry.get_registry()
            >>> detector = registry.get_detector("VolumeSpikeDetector")
            >>> if detector:
            ...     alert = detector.detect_safe(features)
        """
        if name not in cls._detectors:
            logger.warning(f"Detector not found: {name}")
            return None

        try:
            detector_class = cls._detectors[name]
            instance = detector_class()
            logger.debug(f"Instantiated detector: {name}")
            return instance
        except Exception as e:
            logger.error(f"Failed to instantiate detector {name}: {e}", exc_info=True)
            return None

    @classmethod
    def get_all_detectors(cls) -> List[Type[DetectorPlugin]]:
        """
        Get all registered detector classes.

        Returns:
            List[Type[DetectorPlugin]]: List of detector classes registered in the system
                Returns empty list if no detectors registered

        Note:
            This returns the classes, not instances. Caller should instantiate
            as needed:

            for detector_class in registry.get_all_detectors():
                detector = detector_class()
                alert = detector.detect_safe(features)

        Example:
            >>> registry = DetectorRegistry.get_registry()
            >>> detectors = registry.get_all_detectors()
            >>> print(f"Found {len(detectors)} detectors")
            >>> for detector_class in detectors:
            ...     print(f"  - {detector_class.__name__}")
        """
        return list(cls._detectors.values())

    @classmethod
    def get_registry(cls) -> 'DetectorRegistry':
        """
        Get the singleton DetectorRegistry instance.

        This is the recommended way to access the registry. It ensures
        only one instance exists throughout the application.

        Returns:
            DetectorRegistry: The singleton instance

        Example:
            >>> from functions.detect.base import DetectorRegistry
            >>> registry = DetectorRegistry.get_registry()
            >>> registry.register(MyDetector)
            >>> detectors = registry.get_all_detectors()
        """
        return cls()

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered detectors from the registry.

        Useful for testing to reset registry state between tests.
        Should not be used in production code.

        Warning:
            This is for testing only. In production, use with caution.
        """
        cls._detectors.clear()
        logger.debug("Cleared all detectors from registry")

# ============================================================================
# MODULE-LEVEL CONVENIENCE FUNCTION
# ============================================================================


def get_registry() -> DetectorRegistry:
    """
    Get the singleton DetectorRegistry instance.

    This is a module-level convenience function that wraps DetectorRegistry.get_registry().

    Returns:
        DetectorRegistry: The singleton instance

    Example:
        >>> from functions.detect import get_registry
        >>> registry = get_registry()
        >>> detectors = registry.get_all_detectors()
    """
    return DetectorRegistry.get_registry()
