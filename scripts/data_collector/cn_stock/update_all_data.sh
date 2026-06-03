#!/bin/bash
set -e

cd /Users/walox/qlib

echo "Starting unified database and sentiment update..."
.venv/bin/python scripts/data_collector/cn_stock/update_all_data.py
