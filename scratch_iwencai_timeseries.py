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
    "2021年1月每天的涨停家数",
    "2021年1月A股每日中位数PE",
    "2021年1月每天涨停"
]

for q in queries:
    print(f"\nQuery: {q}")
    headers = {
        "Authorization": f"Bearer {adapter.api_key}",
        "Content-Type": "application/json",
        **adapter._claw_headers(skill_id="data-query"),
    }
    payload = {
        "query": q,
        "page": "1",
        "limit": "10",
        "is_cache": "1",
        "expand_index": "true",
    }
    r = requests.post(f"{adapter.base_url}/v1/query2data", json=payload, headers=headers, timeout=30)
    data = r.json()
    print("Keys in data:", data.keys())
    if 'datas' in data:
        print(f"Data length: {len(data['datas'])}")
        if len(data['datas']) > 0:
            pprint(data['datas'][0])
    else:
        print("No datas in response")
