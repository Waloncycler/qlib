import subprocess
import json
import os

import os
TOKEN = os.environ.get("ZIZIZAIZAI_TOKEN", "your_token_here")

def run_curl(url):
    cmd = [
        "curl", "-s",
        "-H", f"authorization: Bearer {TOKEN}",
        "-H", "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "-H", "accept: application/json, text/plain, */*",
        "-H", "origin: https://quant.zizizaizai.com",
        "-H", "referer: https://quant.zizizaizai.com/",
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return None

data = run_curl("https://api.zizizaizai.com/v3/topic/tables?page=1&limit=2&brief=1")
print(json.dumps(data, ensure_ascii=False))
