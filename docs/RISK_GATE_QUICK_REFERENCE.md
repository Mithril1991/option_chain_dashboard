# RiskGate Quick Reference

## Import

```python
from functions.risk.gate import RiskGate, AccountState, AccountPosition
from functions.config.settings import get_settings
```

## Quick Start

```python
# Initialize
config = get_settings()
gate = RiskGate(config)

# Check opportunity
passes, reason = gate.passes_risk_gate(alert, ticker)

# Monitor portfolio
summary = gate.get_portfolio_summary()
```

## Class Reference

### AccountPosition
```python
pos = AccountPosition(ticker, quantity, entry_price, current_price)
pos.position_value      # Current market value
pos.unrealized_pnl      # Profit/loss
```

### AccountState
```python
account = AccountState(
    margin_available=50000.0,
    cash_available=100000.0,
    positions={"AAPL": position}
)
account.total_portfolio_value
account.get_position_value(ticker)
account.get_concentration_pct(ticker)
```

### RiskGate
```python
gate = RiskGate(config)

# Main method
passes, reason = gate.passes_risk_gate(alert, ticker)
# Returns: (True, None) or (False, "reason string")

# Portfolio metrics
summary = gate.get_portfolio_summary()
# Returns: {margin_available, cash_available, margin_pct_used, 
#           cash_pct_used, total_portfolio_value, 
#           concentration_by_ticker, timestamp_utc}
```

## Gate Details

| Gate | Check | Default Limit | Config Key |
|------|-------|---------------|-----------|
| MARGIN | Required margin < available | 50% | risk.margin_gate_threshold_pct |
| CASH | Required cash < available | 50% | risk.cash_gate_threshold_pct |
| CONCENTRATION | Position size < limit | 5% | risk.max_concentration_pct |

## Common Patterns

### Check before trading
```python
alert = detector.detect_safe(features)
if alert and gate.passes_risk_gate(alert, ticker)[0]:
    execute_trade(alert, ticker)
```

### Monitor risk levels
```python
summary = gate.get_portfolio_summary()
if summary['margin_pct_used'] > 70:
    logger.warning("Margin usage high")
```

### Get concentration limits
```python
for ticker, conc in summary['concentration_by_ticker'].items():
    if conc > 5:
        logger.warning(f"{ticker} exceeds 5% limit")
```

## Return Values

### passes_risk_gate()
```python
(True, None)           # All gates passed
(False, "reason")      # Gate failed, provides reason string
```

### get_portfolio_summary()
```python
{
    'margin_available': 50000.0,      # float
    'cash_available': 100000.0,        # float
    'margin_pct_used': 35.2,           # float, 0-100
    'cash_pct_used': 28.5,             # float, 0-100
    'total_portfolio_value': 46000.0,  # float
    'concentration_by_ticker': {       # Dict[str, float]
        'AAPL': 33.70,
        'GOOGL': 15.76
    },
    'timestamp_utc': '2026-01-26T15:30:45.123Z'  # str, ISO 8601
}
```

## Error Cases

```python
# Invalid alert
gate.passes_risk_gate("not alert", "AAPL")  
# Raises: ValueError("alert must be AlertCandidate...")

# Invalid ticker
gate.passes_risk_gate(alert, "")
# Raises: ValueError("ticker must be non-empty string...")

# Invalid config
RiskGate("not config")
# Raises: ValueError("config must be AppConfig instance...")
```

## Default Configuration

```python
max_concentration_pct = 5.0        # %
margin_gate_threshold_pct = 50.0   # %
cash_gate_threshold_pct = 50.0     # %
```

## Testing

```bash
# All tests
pytest tests/tech/unit/test_risk_gate.py -v

# Specific class
pytest tests/tech/unit/test_risk_gate.py::TestRiskGate -v

# With coverage
pytest tests/tech/unit/test_risk_gate.py --cov=functions.risk
```

## Common Issues

| Problem | Solution |
|---------|----------|
| "No account configured" warning | Add account to AppConfig or use defaults |
| Gate always passes | Check if limits are 0 (no limits enforced) |
| Concentration calculation off | Verify positions dict has AccountPosition objects |
| Margin/cash estimates wrong | Check metrics dict has premium_estimate, strike_estimate, quantity |

## See Also

- Full documentation: `/docs/RISK_GATE_IMPLEMENTATION.md`
- Implementation: `/functions/risk/gate.py`
- Tests: `/tests/tech/unit/test_risk_gate.py`
- Detectors: `/functions/detect/base.py`
