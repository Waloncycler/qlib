import json
import subprocess
from pathlib import Path

import os
TOKEN = os.environ.get("ZIZIZAIZAI_TOKEN", "your_token_here")

def run_curl(url):
    cmd = [
        "curl", "-s",
        "-H", f"authorization: Bearer {TOKEN}",
        "-H", "user-agent: Mozilla/5.0",
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print("Exception:", e)
    return None

url = "https://api.zizizaizai.com/v3/topic/table/57/kline"
print(f"Testing fetch from {url}...")
data = run_curl(url)
if data:
    print(f"Success! Status code: {data.get('code')}")
    if data.get("code") == 20000:
        print(f"Got {len(data.get('data', []))} records.")
else:
    print("Failed or None")
