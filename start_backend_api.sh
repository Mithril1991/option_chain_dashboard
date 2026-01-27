#!/bin/bash
cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard
source venv/bin/activate
python -m uvicorn scripts.run_api:app --host 0.0.0.0 --port 8061 --log-level info
