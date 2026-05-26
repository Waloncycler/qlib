import json
import time
import subprocess
from pathlib import Path

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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return None
    except Exception as e:
        print("Exception:", e)
        return None

def main():
    topics_file = Path("/Users/walox/qlib/data/cn_stock/hierarchical/signals/zizizaizai_topics.json")
    if not topics_file.exists():
        print(f"Error: {topics_file} not found.")
        return
        
    with open(topics_file, "r", encoding="utf-8") as f:
        topics = json.load(f)
        
    klines_data = {}
    
    # Check if we already have partial data to resume
    out_file = topics_file.parent / "zizizaizai_klines.json"
    if out_file.exists():
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                klines_data = json.load(f)
        except:
            klines_data = {}

    for i, topic in enumerate(topics):
        t_id = str(topic.get("id"))
        t_name = topic.get("name")
        
        print(f"[{i+1}/{len(topics)}] Fetching klines for topic ID {t_id} ({t_name})...")
        
        url = f"https://api.zizizaizai.com/v3/topic/table/{t_id}/kline"
        data = run_curl(url)
        
        if data and data.get("code") == 20000:
            klines_data[t_id] = data["data"]
            print(f"  Got {len(data['data'])} daily records.")
            
            # Save incrementally to avoid losing data on crash
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(klines_data, f, ensure_ascii=False)
        else:
            print(f"  Failed to fetch klines for {t_id}")
            
        time.sleep(1) # Be nice and avoid timeouts

    print(f"Successfully finished all klines.")

if __name__ == "__main__":
    main()
