# ExplanationGenerator Usage Guide

## Quick Start

The `ExplanationGenerator` class provides deterministic, template-based explanations for trading alerts without requiring LLM calls.

### Basic Usage

```python
from functions.explain.template_explain import ExplanationGenerator
from functions.config.models import AppConfig
from functions.detect.base import AlertCandidate
from functions.compute.feature_engine import FeatureSet

# Initialize
config = AppConfig()
generator = ExplanationGenerator(config)

# Generate explanation
explanation = generator.generate_explanation(
    alert=alert_candidate,
    ticker="AAPL",
    features=feature_set
)

# Access explanation components
print(explanation["summary"])
print(explanation["rationale"])
print(f"Risk factors: {explanation['risk_factors']}")
print(f"Opportunities: {explanation['opportunities']}")
print(f"Timeframe: {explanation['timeframe']}")
```

## Output Structure

All explanations return a dictionary with the following keys:

```python
{
    "summary": str,                          # 1-2 sentence overview of the opportunity
    "rationale": str,                        # Why this matters for trading
    "key_metrics": List[Dict],              # List of {metric, value, unit} dicts
    "directional_bias": str,                 # "bullish", "bearish", or "neutral"
    "risk_factors": List[str],              # Risk factors to consider
    "opportunities": List[str],             # Suggested trading opportunities
    "timeframe": str,                        # Suggested holding period (e.g., "2-4 weeks")
    "next_monitoring_points": List[str],    # What to watch going forward
    "timestamp": str,                       # UTC ISO format timestamp with Z suffix
}
```

## Supported Detectors

The ExplanationGenerator has specific logic for each detector type:

### 1. LowIVDetector
When IV percentile is at historically low levels, indicating compressed option premiums.

**Example Output:**
```python
{
    "summary": "AAPL trading at historically low implied volatility (20th percentile)...",
    "directional_bias": "neutral",
    "opportunities": ["Long Straddle", "Calendar Spread", "Bull Call Spread"],
    "risk_factors": [
        "IV can compress further (theta decay accelerates)",
        "Low IV may indicate absent catalysts",
        "Thesis may not pan out if market reprices higher"
    ]
}
```

### 2. RichPremiumDetector
When IV percentile is at historically high levels, indicating elevated option prices.

**Example Output:**
```python
{
    "summary": "AAPL implied volatility at 80th percentile...",
    "directional_bias": "bullish or bearish (depends on position direction)",
    "opportunities": ["Bull Call Spreads", "Bear Put Spreads", "Long Calls/Puts"],
    "risk_factors": [
        "Position assigned if incorrect directional bet",
        "IV crush can hurt long premium positions",
        "Theta decay works against long premium buyers"
    ]
}
```

### 3. EarningsCrushDetector
When earnings event approaches with elevated IV for the event.

**Example Output:**
```python
{
    "summary": "AAPL approaching earnings with elevated IV (7 days to earnings)...",
    "directional_bias": "neutral (unless post-earnings direction is known)",
    "opportunities": ["Short Straddle", "Short Iron Condor"],
    "risk_factors": [
        "Post-earnings gap moves can be large",
        "IV crush timing varies (not always immediate)",
        "Liquidity can drop after earnings announcement"
    ]
}
```

### 4. TermKinkDetector
When term structure shows abnormal patterns (contango/backwardation).

**Example Output:**
```python
{
    "summary": "AAPL term structure abnormal (IV ratio: 1.15)...",
    "directional_bias": "neutral (term structure agnostic to direction)",
    "opportunities": ["Calendar Spreads", "Diagonal Spreads"],
    "risk_factors": [
        "Term structure can normalize quickly",
        "Cost of carry can change unexpectedly"
    ]
}
```

### 5. SkewAnomalyDetector
When put/call skew indicates directional market conviction.

**Example Output:**
```python
{
    "summary": "AAPL put/call skew imbalanced...",
    "directional_bias": "bullish",  # based on skew direction
    "opportunities": ["Bull Call Spreads", "Bull Put Spreads"],
    "risk_factors": [
        "Skew can reverse quickly",
        "Market can prove wrong on skew-implied direction"
    ]
}
```

### 6. RegimeShiftDetector
When technical regime changes (golden cross, death cross, support bounce).

**Example Output:**
```python
{
    "summary": "AAPL entering new technical regime: golden_cross...",
    "directional_bias": "bullish",  # for golden cross
    "opportunities": ["Long Call Spreads", "Bull Call Spreads"],
    "risk_factors": [
        "False breakouts can occur",
        "Whipsaw moves around key levels",
        "Reversion to mean before trend confirms"
    ]
}
```

## Utility Methods

### _format_metric(name: str, value: float, unit: str = "") -> Dict

Formats a metric for display, handling None and NaN values gracefully.

```python
metric = generator._format_metric("IV Percentile", 35.5, "%")
# Returns: {"metric": "IV Percentile", "value": 35.5, "unit": "%"}

# Handles None/NaN gracefully
metric = generator._format_metric("Missing Value", None)
# Returns: {}
```

### _get_metric_value(features: FeatureSet, path: str) -> Optional[float]

Accesses nested metric values using dotted path notation.

```python
# Access technicals
rsi = generator._get_metric_value(features, "technicals.rsi")

# Access IV metrics
iv_pct = generator._get_metric_value(features, "iv_metrics.iv_percentile")

# Access options data
iv_front = generator._get_metric_value(features, "options_front.atm_iv")

# Invalid paths return None
unknown = generator._get_metric_value(features, "invalid.path")
```

## Integration with Other Modules

### With Detection System
```python
from functions.detect.base import AlertCandidate, DetectorRegistry

# Get detector results
registry = DetectorRegistry.get_registry()
for detector_class in registry.get_all_detectors():
    detector = detector_class()
    alert = detector.detect_safe(features)

    if alert:
        # Enrich with explanation
        explanation = generator.generate_explanation(alert, ticker, features)
        print(f"{alert.detector_name}: {explanation['summary']}")
```

### With Dashboard/API
```python
# Return enriched alert with explanation for API response
alert_with_explanation = {
    "detector": alert.detector_name,
    "score": alert.score,
    "confidence": alert.confidence,
    "explanation": generator.generate_explanation(alert, ticker, features),
    "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
}

# Return as JSON to dashboard
return jsonify(alert_with_explanation)
```

## Error Handling

The ExplanationGenerator gracefully handles:

1. **Missing Data**: Omits sections rather than crashing
2. **None Values**: Empty dicts for unavailable metrics
3. **NaN Values**: Skipped in metric calculations
4. **Unknown Detectors**: Falls back to generic explanation using alert data
5. **Invalid Paths**: Returns None for _get_metric_value calls

Example:
```python
# Even if IV metrics are missing, explanation still generated
explanation = generator.generate_explanation(alert, ticker, features)
# risk_factors included, key_metrics partially populated
```

## Performance Characteristics

- **Time Complexity**: O(1) per explanation (template lookups only)
- **Space Complexity**: O(n) where n is size of features dict
- **No External Calls**: All logic self-contained, no API/LLM calls
- **Deterministic**: Same inputs always produce identical outputs
- **Thread-Safe**: No mutable shared state

## Testing

Run the test suite:

```bash
./venv/bin/python -m pytest tests/tech/unit/test_template_explain.py -v
```

Tests cover:
- Initialization and validation
- All detector-specific explanations
- Utility methods
- Edge cases (None, NaN, missing data)
- Complete workflows

## Configuration

Currently uses default AppConfig. Future versions can support:

```python
class ExplanationConfig(BaseModel):
    """Configuration for explanation templates and thresholds."""

    # Custom templates per detector
    low_iv_template: str = "default"

    # Custom thresholds
    confidence_thresholds: Dict[str, float] = {}

    # Custom opportunity lists
    custom_opportunities: Dict[str, List[str]] = {}
```

## Future Enhancements

Potential improvements:

1. **Configurable Templates**: Customize explanation text per deployment
2. **Confidence Scoring**: Rate explanation confidence based on data completeness
3. **Risk Scoring**: Quantify risk factors on 0-100 scale
4. **Opportunity Weighting**: Rank suggested strategies by suitability
5. **Multi-Language Support**: Generate explanations in multiple languages
6. **Historical Context**: Reference recent market regime changes
7. **Portfolio Context**: Account for existing positions when explaining alerts

## Examples

See `/mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard/tests/tech/unit/test_template_explain.py` for comprehensive usage examples.

## Additional Resources

- **Main Implementation**: `functions/explain/template_explain.py`
- **API Integration**: `functions/api/endpoints/` (to be implemented)
- **Dashboard Integration**: Frontend React components (separate repository)
- **Detector System**: `functions/detect/`
- **Feature Engine**: `functions/compute/feature_engine.py`
