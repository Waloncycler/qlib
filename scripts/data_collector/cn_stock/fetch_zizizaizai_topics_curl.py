import json
import time
import subprocess
import shlex
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"Curl error: {result.stderr}")
            return None
    except Exception as e:
        print(f"Exception running curl: {e}")
        return None

def fetch_topics():
    topics = []
    page = 1
    limit = 20
    while True:
        url = f"https://api.zizizaizai.com/v3/topic/tables?page={page}&limit={limit}&brief=1"
        print(f"Fetching page {page}...")
        data = run_curl(url)
        
        if not data or data.get("code") != 20000:
            print(f"API Error or no data: {data}")
            break
        
        items = data["data"].get("items", [])
        if not items:
            break
            
        topics.extend(items)
        total = data["data"].get("total", 0)
        
        print(f"  Got {len(items)} items. Total collected: {len(topics)}/{total}")
        
        if len(topics) >= total:
            break
            
        page += 1
        time.sleep(1)
        
    return topics

def fetch_topic_details(topic_id):
    url = f"https://api.zizizaizai.com/v3/topic/table/{topic_id}"
    data = run_curl(url)
    if data and data.get("code") == 20000:
        return data["data"]
    return None

def main():
    print("Starting to fetch topics via curl...")
    topics = fetch_topics()
    print(f"Fetched {len(topics)} topics. Now fetching details...")
    
    full_data = []
    for i, topic in enumerate(topics):
        t_id = topic["id"]
        print(f"[{i+1}/{len(topics)}] Fetching details for topic ID {t_id} ({topic['name']})...")
        details = fetch_topic_details(t_id)
        if details:
            full_data.append(details)
        else:
            print(f"Failed to fetch details for {t_id}")
        time.sleep(0.5)  # Be nice to the API
        
    save_dir = Path("/Users/walox/qlib/data/cn_stock/hierarchical/signals")
    save_dir.mkdir(parents=True, exist_ok=True)
    out_file = save_dir / "zizizaizai_topics.json"
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully saved {len(full_data)} topics with details to {out_file}")
    
    # Also create a simplified CSV of the rows
    import csv
    csv_file = save_dir / "zizizaizai_topic_stocks.csv"
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Topic_ID", "Topic_Name", "L1_Category", "L2_Category", "L3_Category", "Stock", "Relevance", "Source"])
        for topic in full_data:
            t_id = topic.get("id")
            t_name = topic.get("name")
            for row in topic.get("rows", []):
                writer.writerow([
                    t_id, 
                    t_name,
                    row.get("一级大类", ""),
                    row.get("二级小类", ""),
                    row.get("三级细分", ""),
                    row.get("个股", ""),
                    row.get("相关性", ""),
                    row.get("信息源", "")
                ])
    print(f"Successfully saved stock mapping to {csv_file}")

if __name__ == "__main__":
    main()
