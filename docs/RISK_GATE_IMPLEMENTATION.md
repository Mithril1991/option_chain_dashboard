# RiskGate Implementation Guide

## Overview

The **RiskGate** class provides portfolio-level risk enforcement for trading opportunities. It validates opportunities against three configurable risk gates before they're approved for trading:

1. **MARGIN_GATE**: Validates margin requirement against available margin
2. **CASH_GATE**: Validates cash requirement for secured strategies (CSP/Wheel)
3. **CONCENTRATION_GATE**: Validates position size against portfolio limits

## Architecture

### Class Hierarchy

```
RiskGate
├── AccountState (account management)
│   └── AccountPosition (individual positions)
└── Risk Gate Methods
    ├── _check_margin_gate()
    ├── _check_cash_gate()
    └── _check_concentration_gate()
```

### Data Flow

```
AlertCandidate
      ↓
RiskGate.passes_risk_gate()
      ↓
[MARGIN_GATE] → fails? → (False, reason)
      ↓
[CASH_GATE] → fails? → (False, reason)
      ↓
[CONCENTRATION_GATE] → fails? → (False, reason)
      ↓
All pass → (True, None)
```

## Components

### 1. AccountPosition Class

Represents a single position in the trading account.

**Attributes:**
- `ticker`: Stock ticker symbol
- `quantity`: Number of shares (positive=long, negative=short)
- `entry_price`: Price at which position was entered
- `current_price`: Current market price

**Properties:**
- `position_value`: Current market value of position
- `unrealized_pnl`: Profit/loss on position

**Example:**
```python
from functions.risk.gate import AccountPosition

pos = AccountPosition("AAPL", 100, 150.0, 155.0)
print(f"Position value: ${pos.position_value}")  # $15,500
print(f"Unrealized P&L: ${pos.unrealized_pnl}")  # $500
```

### 2. AccountState Class

Represents the current state of a trading account.

**Attributes:**
- `margin_available` (float): Available buying power for margin
- `cash_available` (float): Available cash not tied up in positions
- `positions` (Dict[str, AccountPosition]): Map of ticker → position

**Methods:**
- `total_portfolio_value`: Calculate total value from all positions
- `get_position_value(ticker)`: Get value of specific position
- `get_concentration_pct(ticker)`: Get position as % of portfolio

**Example:**
```python
from functions.risk.gate import AccountState, AccountPosition

pos1 = AccountPosition("AAPL", 100, 150.0, 155.0)
pos2 = AccountPosition("GOOGL", 50, 140.0, 145.0)

account = AccountState(
    margin_available=50000.0,
    cash_available=100000.0,
    positions={"AAPL": pos1, "GOOGL": pos2}
)

print(f"Portfolio value: ${account.total_portfolio_value}")
print(f"AAPL concentration: {account.get_concentration_pct('AAPL')}%")
```

### 3. RiskGate Class

Main class for portfolio-level risk enforcement.

**Constructor:**
```python
def __init__(self, config: AppConfig)
```

Initializes with AppConfig that should contain account state. If account not configured, creates default (no limits enforced).

**Example:**
```python
from functions.config.settings import get_settings
from functions.risk.gate import RiskGate

config = get_settings()
gate = RiskGate(config)
```

## Methods

### passes_risk_gate()

**Signature:**
```python
def passes_risk_gate(
    self,
    alert: AlertCandidate,
    ticker: str
) -> tuple[bool, Optional[str]]
```

**Purpose:** Check if opportunity passes all portfolio risk gates

**Parameters:**
- `alert`: AlertCandidate opportunity to validate
- `ticker`: Stock ticker symbol

**Returns:**
- `(True, None)` if all gates pass
- `(False, reason_string)` if any gate fails

**Example:**
```python
from functions.detect.base import AlertCandidate

alert = AlertCandidate(
    detector_name="VolumeSpikeDetector",
    score=75.0,
    strategies=["Long Call Spread"],
    metrics={"premium_estimate": 1.5},
    explanation={
        "summary": "Unusual volume spike detected",
        "reason": "Volume increased 5x average",
        "trigger": "Call volume exceeded threshold"
    },
    confidence="high"
)

passes, reason = gate.passes_risk_gate(alert, "AAPL")
if passes:
    print("Opportunity approved!")
else:
    print(f"Rejected: {reason}")
```

### _check_margin_gate()

**Signature:**
```python
def _check_margin_gate(
    self,
    alert: AlertCandidate,
    ticker: str
) -> tuple[bool, str]
```

**Purpose:** Validate margin requirement against available margin

**Logic:**
1. Extract strategy from `alert.strategies[0]`
2. Estimate margin requirement:
   - **For spreads** (contain "Spread"): `debit_amount / position_size`
   - **For others**: `premium * 100 * 0.5` (conservative 50% rule)
3. Compare to `account.margin_available`
4. Fail if margin used > 50% threshold (configurable)

**Configuration:**
- Key: `risk.margin_gate_threshold_pct`
- Default: 50.0 (50%)

**Example:**
```python
passes, reason = gate._check_margin_gate(alert, "AAPL")
# Returns:
# (True, "Margin gate passed: Long Call Spread requires $250 (0.5% of $50,000 available)")
# or
# (False, "Margin gate FAILED for AAPL: Bull Call Spread requires $25,000 (50.0% of available), exceeds 50% threshold")
```

### _check_cash_gate()

**Signature:**
```python
def _check_cash_gate(
    self,
    alert: AlertCandidate,
    ticker: str
) -> tuple[bool, str]
```

**Purpose:** Validate cash requirement for secured strategies

**Logic:**
1. Check if strategy requires cash (CSP, Wheel)
2. If not cash-requiring: return `(True, "Cash gate passed (doesn't require cash)")`
3. If requires cash, estimate requirement:
   - **CSP/Wheel**: `strike * 100 * qty` (100 shares per contract)
4. Compare to `account.cash_available`
5. Fail if cash used > 50% threshold (configurable)

**Configuration:**
- Key: `risk.cash_gate_threshold_pct`
- Default: 50.0 (50%)

**Cash-Requiring Strategies:**
- "Cash Secured Put"
- "CSP"
- "Wheel"

**Example:**
```python
alert_csp = AlertCandidate(
    detector_name="TestDetector",
    score=75.0,
    strategies=["Cash Secured Put"],
    metrics={"strike_estimate": 150.0, "quantity": 2},
    explanation={"summary": "...", "reason": "...", "trigger": "..."},
    confidence="high"
)

passes, reason = gate._check_cash_gate(alert_csp, "AAPL")
# Returns:
# (True, "Cash gate passed: Cash Secured Put requires $30,000 (30.0% of $100,000 available)")
# or
# (False, "Cash gate FAILED for AAPL: Wheel requires $50,000 (50.0% of available), exceeds 50% threshold")
```

### _check_concentration_gate()

**Signature:**
```python
def _check_concentration_gate(self, ticker: str) -> tuple[bool, str]
```

**Purpose:** Validate position doesn't exceed concentration limits

**Logic:**
1. Calculate concentration: `position_value / total_portfolio_value * 100`
2. Compare to `max_concentration_pct` config (default 5%)
3. Fail if concentration > limit

**Configuration:**
- Key: `risk.max_concentration_pct`
- Default: 5.0 (5%)

**Note:** Checks EXISTING position concentration. For NEW positions, caller should estimate and factor in.

**Example:**
```python
passes, reason = gate._check_concentration_gate("AAPL")
# Returns:
# (True, "Concentration gate passed: AAPL is 3.2% of portfolio (limit: 5%)")
# or
# (False, "Concentration gate FAILED for AAPL: 8.5% of portfolio exceeds 5% limit")
```

### get_portfolio_summary()

**Signature:**
```python
def get_portfolio_summary(self) -> Dict[str, Any]
```

**Purpose:** Generate comprehensive portfolio summary for dashboard

**Returns:** Dictionary with:
- `margin_available` (float): Available buying power
- `cash_available` (float): Available cash
- `margin_pct_used` (float): % of margin in use
- `cash_pct_used` (float): % of cash in use
- `total_portfolio_value` (float): Sum of all positions
- `concentration_by_ticker` (Dict[str, float]): % of portfolio by ticker
- `timestamp_utc` (str): ISO 8601 UTC timestamp

**Example:**
```python
summary = gate.get_portfolio_summary()

print(f"Portfolio value: ${summary['total_portfolio_value']:.2f}")
print(f"Margin used: {summary['margin_pct_used']:.1f}%")
print(f"Cash used: {summary['cash_pct_used']:.1f}%")

for ticker, conc_pct in summary['concentration_by_ticker'].items():
    print(f"  {ticker}: {conc_pct:.2f}%")

# Output:
# Portfolio value: $46,000.00
# Margin used: 35.2%
# Cash used: 28.5%
#   AAPL: 33.70%
#   GOOGL: 15.76%
#   MSFT: 50.54%
```

## Configuration

RiskGate uses configuration values with safe defaults:

```python
# Default configuration (if not set in AppConfig)
max_concentration_pct = 5.0      # Maximum position size as % of portfolio
margin_gate_threshold_pct = 50.0 # Fail if margin used > 50%
cash_gate_threshold_pct = 50.0   # Fail if cash used > 50%
```

## Usage Examples

### Basic Risk Gate Check

```python
from functions.config.settings import get_settings
from functions.risk.gate import RiskGate
from functions.detect.base import AlertCandidate

config = get_settings()
gate = RiskGate(config)

# Get alert from detector
alert = AlertCandidate(...)

# Check if opportunity passes gates
passes, reason = gate.passes_risk_gate(alert, "AAPL")

if passes:
    print("Opportunity approved for trading!")
else:
    print(f"Opportunity rejected: {reason}")
```

### Monitoring Portfolio Risk

```python
# Get current portfolio state
summary = gate.get_portfolio_summary()

# Check margin utilization
if summary['margin_pct_used'] > 70:
    print("WARNING: Margin usage > 70%")

# Check for concentrated positions
for ticker, conc_pct in summary['concentration_by_ticker'].items():
    if conc_pct > 10:
        print(f"WARNING: {ticker} is {conc_pct:.1f}% of portfolio")
```

### Building Risk-Aware Trading System

```python
def evaluate_opportunity(alert: AlertCandidate, ticker: str) -> bool:
    """
    Evaluate if opportunity should be executed.

    Args:
        alert: Trading opportunity from detector
        ticker: Stock symbol

    Returns:
        True if opportunity passes all risk gates
    """
    config = get_settings()
    gate = RiskGate(config)

    # Check risk gates
    passes, reason = gate.passes_risk_gate(alert, ticker)

    if not passes:
        logger.warning(f"Opportunity rejected for {ticker}: {reason}")
        return False

    # Check portfolio health
    summary = gate.get_portfolio_summary()
    if summary['margin_pct_used'] > 80:
        logger.warning(f"Portfolio margin too high: {summary['margin_pct_used']}%")
        return False

    # Additional checks...
    return True
```

## Testing

Unit tests are provided in `/tests/tech/unit/test_risk_gate.py`:

```bash
# Run all RiskGate tests
pytest tests/tech/unit/test_risk_gate.py -v

# Run specific test
pytest tests/tech/unit/test_risk_gate.py::TestAccountPosition -v

# Run with coverage
pytest tests/tech/unit/test_risk_gate.py --cov=functions.risk
```

**Test Coverage:**
- AccountPosition creation and calculations
- AccountState aggregation and concentration
- Margin gate logic
- Cash gate logic (CSP, Wheel)
- Concentration gate logic
- Portfolio summary generation
- Integration scenarios with realistic portfolios

## Logging

RiskGate logs all gate decisions at INFO level for trading audit trail:

```
2026-01-26T15:30:45.123Z [INFO] functions.risk.gate:__init__:... - Initializing RiskGate
2026-01-26T15:30:46.456Z [INFO] functions.risk.gate:passes_risk_gate:... - Checking risk gates for AAPL - VolumeSpikeDetector (score=75.0, strategies=['Long Call Spread'])
2026-01-26T15:30:46.789Z [INFO] functions.risk.gate:passes_risk_gate:... - All risk gates PASSED for AAPL
```

## Error Handling

All methods handle missing data gracefully:

1. **No account configured**: Uses default (margin_available=0, cash_available=0)
2. **Missing position**: Returns 0.0 for concentration
3. **Invalid metrics**: Uses sensible defaults (premium_estimate=1.0, quantity=1)
4. **Config not found**: Uses built-in defaults (5%, 50%, 50%)

## Performance

All methods are O(n) where n is number of positions:
- `passes_risk_gate()`: 3 gate checks, linear in positions
- `get_portfolio_summary()`: Single scan of all positions
- Memory usage: Constant + size of position dictionary

## Future Enhancements

Potential improvements for future releases:

1. **Dynamic threshold adjustment**: Adjust gates based on market conditions
2. **Strategy-specific margins**: Use actual margin requirements from broker
3. **Greeks-based risk**: Use option Greeks for portfolio-level Greeks
4. **Scenario analysis**: Simulate portfolio under different market moves
5. **Risk metrics**: Add VaR, stress testing, historical simulation
6. **Broker integration**: Pull live margin and buying power from broker API

## Files

- **Implementation**: `/functions/risk/gate.py` (600+ lines)
- **Tests**: `/tests/tech/unit/test_risk_gate.py` (400+ lines)
- **Module exports**: `/functions/risk/__init__.py`

## Related Documentation

- [Detector System](../FOUNDATION_MODULES.md#detector-system)
- [AlertCandidate](../functions/detect/base.py)
- [Configuration System](../functions/config/models.py)
