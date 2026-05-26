#!/bin/bash
set -e

cd /Users/walox/qlib

echo "====================================="
echo "1. Fetching Zizizaizai Topics..."
echo "====================================="
.venv/bin/python scripts/data_collector/cn_stock/fetch_zizizaizai_topics.py

echo ""
echo "====================================="
echo "2. Fetching Zizizaizai K-Lines..."
echo "====================================="
.venv/bin/python scripts/data_collector/cn_stock/fetch_zizizaizai_klines.py

echo ""
echo "====================================="
echo "Update Complete!"
echo "====================================="
