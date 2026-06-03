import yaml
import sys
import requests
from pathlib import Path
from pprint import pprint

sys.path.append(str(Path('/Users/walox/qlib/scripts/data_collector/cn_stock')))
from adapters.research import IwencaiAdapter

config = {}
with open('/Users/walox/qlib/scripts/data_collector/cn_stock/secret.yaml', 'r') as f:
    config = yaml.safe_load(f)

adapter = IwencaiAdapter(config)

queries = [
    "2021年1月4日上涨家数，下跌家数，涨停家数，跌停家数",
    "2021年1月4日A股中位数PE，中位数PB，中位数换手率",
]

for q in queries:
    print(f"\nQuery: {q}")
    res = adapter.query2data(q)
    if res:
        print(f"Data length: {len(res)}")
        if len(res) > 0:
            pprint(res[0])
    else:
        print("No data")
