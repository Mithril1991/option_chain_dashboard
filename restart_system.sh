#!/bin/bash
cd /mnt/shared_ubuntu/Claude/Projects/option_chain_dashboard
source venv/bin/activate
python main.py --demo-mode > logs/system.log 2>&1
