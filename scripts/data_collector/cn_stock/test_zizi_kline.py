import subprocess
import json

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
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return res.stdout
    except:
        pass
    return None

endpoints = [
    "/v3/topic/kline/57",
    "/v3/topic/klines/57",
    "/v3/topic/chart/57",
    "/v3/topic/history/57",
    "/v3/topic/quotes/57",
    "/v3/topic/stocks/57",
    "/v3/topic/table/57/kline"
]

for ep in endpoints:
    url = f"https://api.zizizaizai.com{ep}"
    print(f"Testing {url}...")
    out = run_curl(url)
    if out and len(out) > 50:
        print(f"Found! Response snippet: {out[:200]}")
    elif out:
        print(f"Response: {out}")
    else:
        print("Failed")
