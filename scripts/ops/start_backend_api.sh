#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"
source venv/bin/activate
python -m uvicorn scripts.run_api:app --host 0.0.0.0 --port 8061 --log-level info
