import yaml
import sys
from pathlib import Path
from pprint import pprint

sys.path.append(str(Path('/Users/walox/qlib/scripts/data_collector/cn_stock')))
from adapters.research import IwencaiAdapter

config = {}
with open('/Users/walox/qlib/scripts/data_collector/cn_stock/secret.yaml', 'r') as f:
    config = yaml.safe_load(f)

adapter = IwencaiAdapter(config)

queries = [
    "2021年1月4日涨停家数，跌停家数，连板家数",
    "2021年1月4日A股中位数PE，中位数PB"
]

for q in queries:
    print(f"\nQuery: {q}")
    res = adapter.query2data(q)
    pprint(res[:2] if res else "No data")

