import yaml
import sys
import requests
import json
from pathlib import Path
from pprint import pprint

sys.path.append(str(Path('/Users/walox/qlib/scripts/data_collector/cn_stock')))
from adapters.research import IwencaiAdapter

config = {}
with open('/Users/walox/qlib/scripts/data_collector/cn_stock/secret.yaml', 'r') as f:
    config = yaml.safe_load(f)

adapter = IwencaiAdapter(config)

query = "2021年1月4日涨停"

headers = {
    "Authorization": f"Bearer {adapter.api_key}",
    "Content-Type": "application/json",
    **adapter._claw_headers(skill_id="data-query"),
}
payload = {
    "query": query,
    "page": "1",
    "limit": "1",
    "is_cache": "1",
    "expand_index": "true",
}

r = requests.post(f"{adapter.base_url}/v1/query2data", json=payload, headers=headers, timeout=30)
data = r.json()
print("Keys in data:", data.keys())
if 'total' in data:
    print("Total:", data['total'])
elif 'data' in data and isinstance(data['data'], dict) and 'total' in data['data']:
    print("Total in data:", data['data']['total'])
else:
    pprint({k: v for k, v in data.items() if k != 'datas'})

