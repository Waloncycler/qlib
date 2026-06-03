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
    "2021年1月4日两市涨停家数",
    "2021年1月4日涨停",
    "2021年1月4日涨停股票",
]

for q in queries:
    print(f"\nQuery: {q}")
    res = adapter.query2data(q)
    if res:
        print(f"Got {len(res)} results. First row:")
        pprint(res[0])
    else:
        print("No data")
