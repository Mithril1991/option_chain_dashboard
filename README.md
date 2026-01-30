# Option Chain Dashboard

A comprehensive financial analytics platform for analyzing options chains, computing Greeks, detecting patterns, and building trading strategies.

## Features

- **Options Chain Analysis**: Fetch and analyze real-time options data from Yahoo Finance
- **Greeks Computation**: Calculate Delta, Gamma, Vega, Theta, and Rho for options
- **Pattern Detection**: Identify unusual options activity and market opportunities
- **Risk Assessment**: Evaluate portfolio risk with multi-leg strategy analysis
- **Strategy Builder**: Construct and backtest complex multi-leg options strategies
- **Interactive Dashboard**: React UI for data visualization and exploration
- **REST API**: FastAPI backend for programmatic access
- **Demo Mode**: Test with simulated data without market data subscriptions

## Tech Stack

- **Frontend**: React with TypeScript for interactive web interface
- **Backend**: FastAPI with async support
- **Data**: Yahoo Finance API, DuckDB for local caching
- **Math**: SciPy for options pricing and Greeks calculations
- **Data Processing**: Pandas, NumPy

## Documentation

All project documentation, reports, and guides are indexed in `docs/index.md`.

## Installation

### Prerequisites

- Python 3.10+
- Virtual environment (venv or similar)

### Setup

```bash
# Clone or navigate to project directory
cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard

# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template and configure
cp .env.example .env
# Edit .env with your settings (API keys, backend URL, etc.)
```

## Running the Application

### Backend API (FastAPI)

```bash
# From project root directory with venv activated
python -m uvicorn functions.api.main:app --host 0.0.0.0 --port 8061 --reload
```

The API will be available at: `http://localhost:8061`

**API Documentation**: `http://localhost:8061/docs` (Swagger UI)

### Frontend Dashboard (React)

The React frontend is a separate project that connects to the FastAPI backend.

**Frontend Repository**: See `frontend/` directory or related React project documentation

The dashboard will be available at: `http://localhost:8060`

## Configuration

All configuration is managed through environment variables in the `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_MODE` | `true` | Use mock data instead of real Yahoo Finance data |
| `BACKEND_URL` | `http://localhost:8061` | URL of the backend API server |
| `LOG_LEVEL` | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `RISK_FREE_RATE` | `0.05` | Risk-free rate for options pricing (5% default) |
| `ANTHROPIC_API_KEY` | `` | Optional: Claude API key for AI explanations |
| `OPENAI_API_KEY` | `` | Optional: OpenAI API key for explanations |

## Port Configuration

- **React Dashboard**: `8060`
- **FastAPI Backend**: `8061`

Ensure these ports are available on your system. To use different ports, modify the startup commands above.

## Project Structure

```
option_chain_dashboard/
├── functions/              # Core business logic
│   ├── api/               # FastAPI backend
│   ├── market/            # Market data fetching
│   ├── compute/           # Options Greeks calculations
│   ├── detect/            # Pattern detection
│   ├── strategy/          # Strategy analysis
│   ├── risk/              # Risk calculations
│   ├── scoring/           # Opportunity scoring
│   ├── explain/           # LLM explanations
│   ├── config/            # Configuration management
│   ├── db/                # Database operations
│   └── util/              # Utilities (logging, etc.)
├── frontend/              # React frontend (separate project)
├── tests/                 # Test suite (unit, integration, contracts)
├── scripts/               # Utility scripts
├── docs/                  # Documentation index and guides
├── data/                  # Cached option chain data
├── historical_data/       # Historical market data
├── tickers/               # Stock ticker lists
├── logs/                  # Application logs
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
└── README.md              # This file
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=functions tests/

# Run specific test category
pytest tests/tech/unit/        # Unit tests
pytest tests/tech/integration/ # Integration tests
pytest tests/user_pov/         # User-perspective tests
```

## Logging

Logs are stored in the `logs/` directory with rotating file handlers:

- **Log File**: `option_chain_dashboard.log`
- **Max File Size**: 10MB per file
- **Backups Retained**: 5 previous log files
- **Format**: ISO 8601 timestamps with UTC timezone

## Development

### Code Organization

- **functions/**: Core business logic with clear separation of concerns
- **frontend/**: React TypeScript frontend (separate project on port 8060)
- **tests/**: Comprehensive test coverage
- **scripts/**: Administrative and utility scripts

### Key Design Principles

- Modular architecture with single responsibility per module
- Async support for I/O-heavy operations (API calls, database)
- Comprehensive error handling and logging
- Type hints throughout codebase (Pydantic models)
- Configuration via environment variables

### Adding New Features

1. Add core logic in `functions/` subdirectory
2. Add API endpoints in `functions/api/`
3. Add UI components in React frontend (separate project)
4. Add tests in `tests/` following same structure
5. Update documentation as needed

## Troubleshooting

### Backend won't start

- Ensure port 8061 is not in use: `lsof -i :8061`
- Check `.env` file is properly configured
- Verify virtual environment is activated
- Check logs: `tail -f logs/option_chain_dashboard.log`

### Dashboard connection fails

- Verify `BACKEND_URL` in `.env` matches running backend
- Ensure backend is running on configured port
- Check firewall/network settings
- Verify both services are on same network (for remote connections)

### No market data

- Check `DEMO_MODE` setting in `.env`
- If using real data: verify internet connection and Yahoo Finance accessibility
- Check `LOG_LEVEL=DEBUG` for detailed error information

## Contributing

When contributing, please:
1. Follow existing code style and structure
2. Add type hints to all functions
3. Write tests for new functionality
4. Update documentation
5. Run `pytest` before submitting changes

## License

[Add license information if applicable]

## Support

For issues or questions, check the documentation in the `docs/` directory or review test cases for usage examples.
