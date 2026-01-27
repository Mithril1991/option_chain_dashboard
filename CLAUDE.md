# CLAUDE.md - Option Chain Dashboard Development Guide

This document provides development guidance for Claude Code working on the Option Chain Dashboard project.

## Project Overview

The **Option Chain Dashboard** is a financial analytics platform that combines market data fetching, options pricing calculations, pattern detection, and risk analysis in a unified web-based system.

**Purpose**: Enable traders and analysts to analyze options chains, detect trading opportunities, and build/backtest complex multi-leg strategies.

**Status**: Active development

## Architecture Overview

### Layered Architecture

```
┌─────────────────────────────────────┐
│   React Dashboard (frontend/)       │  Port 8060
├─────────────────────────────────────┤
│   FastAPI Backend (functions/api/)  │  Port 8061
├─────────────────────────────────────┤
│   Business Logic (functions/*)      │
├─────────────────────────────────────┤
│   External APIs & Data Stores       │
│   (Yahoo Finance, DuckDB, Files)    │
└─────────────────────────────────────┘
```

### Function Modules (Core Business Logic)

Each module has clear responsibility:

- **`functions/market/`**: Market data fetching (Yahoo Finance API)
- **`functions/compute/`**: Options Greeks calculations (Delta, Gamma, Vega, Theta, Rho)
- **`functions/detect/`**: Pattern detection in options chains
- **`functions/strategy/`**: Multi-leg strategy analysis and backtesting
- **`functions/risk/`**: Portfolio risk assessment
- **`functions/scoring/`**: Opportunity scoring and ranking
- **`functions/explain/`**: LLM-powered explanations (Claude/OpenAI)
- **`functions/db/`**: Database operations (DuckDB)
- **`functions/config/`**: Configuration management (Pydantic)
- **`functions/util/`**: Logging, helpers, validators
- **`functions/api/`**: FastAPI endpoints and request/response models

### Data Flow

```
User Input (UI) → React Dashboard
                     ↓
                  API Calls
                     ↓
              FastAPI Backend
                     ↓
        Business Logic (functions/*)
                     ↓
    Market Data APIs + Local Database
```

## Key Design Decisions

### 1. **Separation of Concerns**
- **Rationale**: Each module focuses on one domain (market data, computation, UI)
- **Benefit**: Easy to test, modify, and scale individual components
- **Implementation**: Strict module boundaries with clear interfaces

### 2. **Environment-based Configuration**
- **Rationale**: Support multiple environments (dev, test, prod) without code changes
- **Benefit**: Secure (no secrets in code), flexible (runtime configuration)
- **Implementation**: `.env` files loaded via `pydantic-settings`

### 3. **Demo Mode Toggle**
- **Rationale**: Enable testing without live market data or API subscriptions
- **Benefit**: Faster development, lower testing costs, reduced API rate limits
- **Implementation**: DEMO_MODE flag switches between real and mock data providers

### 4. **Async/Await for I/O Operations**
- **Rationale**: Improve performance for API calls and database operations
- **Benefit**: Better responsiveness, handle concurrent requests
- **Implementation**: FastAPI native support + async database drivers

### 5. **Type Hints Throughout**
- **Rationale**: Catch errors early, improve IDE support, self-documenting code
- **Benefit**: Fewer runtime errors, easier onboarding, better refactoring
- **Implementation**: All functions have complete type annotations + Pydantic models

### 6. **DuckDB for Local Caching**
- **Rationale**: Options data doesn't change intra-minute; cache to reduce API calls
- **Benefit**: Faster dashboard loads, reduced dependencies on external APIs
- **Implementation**: TTL-based caching in `functions/db/`

## Working with the Codebase

### Before Starting Work

1. **Read project instructions**: This file + README.md
2. **Understand the request**: What feature/bug is being addressed?
3. **Check existing code**: Search for similar patterns in codebase
4. **Review tests**: Tests show how components should be used

### Development Workflow

1. **Create feature branch** (if using git):
   ```bash
   git checkout -b feature/description
   ```

2. **Make changes**:
   - Keep changes focused and atomic
   - Follow existing code style and naming conventions
   - Add type hints to all functions
   - Update docstrings for public methods

3. **Test locally**:
   ```bash
   pytest tests/                    # All tests
   pytest tests/tech/unit/          # Unit tests only
   pytest --cov=functions tests/    # With coverage
   ```

4. **Run the application**:
   ```bash
   # Terminal 1: Backend
   python -m uvicorn functions.api.main:app --host 0.0.0.0 --port 8061 --reload

   # Terminal 2: React Frontend (separate project)
   cd frontend && npm start  # or follow React project setup
   ```

5. **Manual testing**: Use dashboard to verify functionality end-to-end

6. **Commit and push** (if applicable)

### Code Style and Conventions

**Naming**:
- Classes: PascalCase (`OptionChain`, `GreeksCalculator`)
- Functions/variables: snake_case (`calculate_greeks`, `implied_volatility`)
- Constants: UPPER_SNAKE_CASE (`DEFAULT_RISK_FREE_RATE`)

**Organization**:
- One main class per file
- Related utilities in same module
- Keep files under 500 lines (split if larger)

**Documentation**:
```python
def calculate_delta(spot: float, strike: float, risk_free_rate: float) -> float:
    """Calculate option delta using Black-Scholes model.

    Args:
        spot: Current price of underlying asset
        strike: Strike price of option
        risk_free_rate: Risk-free interest rate (0.05 = 5%)

    Returns:
        Delta value between -1 and 1

    Raises:
        ValueError: If inputs are invalid
    """
```

**Type Hints**:
```python
from typing import Optional, List
from pydantic import BaseModel

class Option(BaseModel):
    symbol: str
    strike: float
    expiration: datetime
    bid: float
    ask: float

def get_options(symbols: List[str], expiration: Optional[datetime] = None) -> List[Option]:
    pass
```

### Adding New Features

#### New API Endpoint

1. Create handler in `functions/api/endpoints/` or `functions/api/main.py`
2. Define request/response models in `functions/api/models.py`
3. Add route decorator and docstring:
   ```python
   @router.get("/api/options/{symbol}")
   async def get_options(symbol: str) -> List[OptionData]:
       """Fetch options chain for given symbol."""
       # Implementation
   ```
4. Add tests in `tests/tech/integration/test_api.py`
5. Document in README if user-facing

#### New Business Logic Module

1. Create directory under `functions/newmodule/`
2. Create `__init__.py` with public exports
3. Create module file(s) with main logic:
   ```python
   from functions.util.logging_setup import get_logger

   logger = get_logger(__name__)

   class NewFeature:
       def __init__(self):
           logger.info("Initializing NewFeature")

       def process(self, data: dict) -> dict:
           """Process data and return results."""
   ```
4. Create tests in matching test directory structure
5. Integrate with API/UI as needed

#### New UI Component (React Frontend)

The React frontend is maintained in a separate repository/directory. To add new components:

1. Create component file in React project structure
2. Use React hooks and state management (Context API, Redux, etc.)
3. Call FastAPI endpoints via fetch or axios:
   ```javascript
   const response = await fetch(`${BACKEND_URL}/api/options/AAPL`);
   const data = await response.json();
   ```
4. Add loading and error states using React patterns
5. Refer to React frontend documentation for component guidelines

**Note**: Backend development focuses on `functions/` and FastAPI routes. Frontend development is a separate concern.

### Testing Strategy

**Three Test Levels**:

1. **Unit Tests** (`tests/tech/unit/`): Test individual functions in isolation
   ```bash
   pytest tests/tech/unit/
   ```

2. **Integration Tests** (`tests/tech/integration/`): Test module interactions
   ```bash
   pytest tests/tech/integration/
   ```

3. **Contract Tests** (`tests/tech/contracts/`): Test API contracts
   ```bash
   pytest tests/tech/contracts/
   ```

4. **User-Perspective Tests** (`tests/user_pov/`): End-to-end scenario tests
   ```bash
   pytest tests/user_pov/
   ```

**Writing Tests**:
```python
import pytest
from functions.compute.greeks import GreeksCalculator

class TestGreeksCalculator:
    def setup_method(self):
        """Run before each test."""
        self.calc = GreeksCalculator()

    def test_delta_at_the_money(self):
        """Delta should be ~0.5 for ATM options."""
        delta = self.calc.calculate_delta(
            spot=100, strike=100, time_to_expiry=0.25
        )
        assert 0.45 < delta < 0.55

    @pytest.mark.asyncio
    async def test_fetch_market_data(self):
        """Test async market data fetching."""
        data = await fetch_option_chain("AAPL")
        assert len(data) > 0
        assert "bid" in data[0]
```

## Common Tasks

### Debugging

1. **Check logs**:
   ```bash
   tail -f logs/option_chain_dashboard.log
   ```

2. **Set DEBUG logging**:
   ```bash
   # In .env
   LOG_LEVEL=DEBUG
   # Or in code
   setup_logging(log_level="DEBUG")
   ```

3. **Use print statements in tests**:
   ```bash
   pytest -s tests/  # Shows print output
   ```

### Running with Mock Data

```bash
# In .env
DEMO_MODE=true
LOG_LEVEL=DEBUG
RISK_FREE_RATE=0.05
```

All market data fetching will return synthetic data.

### Profiling Performance

```python
import time

start = time.time()
# Code to profile
elapsed = time.time() - start
logger.info(f"Operation took {elapsed:.2f} seconds")
```

### Database Inspection

```bash
# DuckDB stores data in data/ directory
# Query with DuckDB CLI (if installed)
duckdb data/cache.db "SELECT * FROM options LIMIT 10;"
```

## Important Conventions

1. **Always use relative imports from project root**:
   ✅ `from functions.market import fetch_options`
   ❌ `from ..market import fetch_options`

2. **Configuration via environment only**:
   ✅ `risk_free_rate = float(os.getenv("RISK_FREE_RATE", "0.05"))`
   ❌ `risk_free_rate = 0.05  # hardcoded`

3. **Log all state changes and errors**:
   ```python
   logger.info(f"Calculating Greeks for {symbol}")
   try:
       result = calculate(data)
       logger.debug(f"Result: {result}")
       return result
   except Exception as e:
       logger.error(f"Calculation failed: {e}")
       raise
   ```

4. **Validate inputs early**:
   ```python
   if not isinstance(price, (int, float)) or price <= 0:
       raise ValueError(f"Price must be positive number, got {price}")
   ```

5. **Use Pydantic for data validation**:
   ```python
   from pydantic import BaseModel, Field

   class Option(BaseModel):
       symbol: str = Field(..., min_length=1)
       strike: float = Field(..., gt=0)
       bid: float = Field(..., ge=0)
   ```

## Troubleshooting During Development

| Problem | Solution |
|---------|----------|
| "Module not found" error | Ensure you're running from project root; check PYTHONPATH |
| API returns 500 error | Check backend logs with `tail -f logs/option_chain_dashboard.log` |
| Dashboard can't connect to backend | Verify `BACKEND_URL` in `.env` and backend is running |
| Tests fail with import errors | Activate venv: `source venv/bin/activate` |
| Slow response times | Check `LOG_LEVEL=DEBUG`; profile with timing logs |
| Database errors | Check `data/` directory exists; verify DuckDB permissions |

## Git Workflow (if applicable)

```bash
# Create feature branch
git checkout -b feature/new-feature

# Make changes
git add functions/path/to/file.py

# Run tests before commit
pytest tests/

# Commit with clear message
git commit -m "Add new feature for XYZ"

# Push and create PR
git push origin feature/new-feature
```

## Resources

- **Options Pricing**: See `functions/compute/` - Uses Black-Scholes model
- **API Documentation**: `http://localhost:8061/docs` (Swagger UI)
- **Configuration**: `.env.example` - All settings documented with examples
- **Logging**: `functions/util/logging_setup.py` - UTC timestamps, rotating files
- **Tests**: `tests/` - Examples of proper testing patterns

## Questions or Issues?

- Check existing code for similar patterns
- Review test files for usage examples
- Check `.env.example` for configuration options
- See logs directory for diagnostic information
