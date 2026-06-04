import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
import os
from pathlib import Path

TOKEN = os.environ.get("ZIZIZAIZAI_TOKEN", "your_token_here")

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "authorization": f"Bearer {TOKEN}",
    "origin": "https://quant.zizizaizai.com",
    "referer": "https://quant.zizizaizai.com/",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def get_session():
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=1, status_forcelist=[502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def fetch_topics():
    topics = []
    page = 1
    limit = 20
    session = get_session()
    while True:
        url = f"https://api.zizizaizai.com/v3/topic/tables?page={page}&limit={limit}&brief=1"
        print(f"Fetching page {page}...")
        try:
            res = session.get(url, headers=HEADERS, timeout=20)
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch page {page}: {e}")
            break
        if res.status_code != 200:
            print(f"Error {res.status_code}: {res.text}")
            break
        data = res.json()
        if data.get("code") != 20000:
            print(f"API Error: {data}")
            break
        
        items = data["data"].get("items", [])
        if not items:
            break
            
        topics.extend(items)
        
        total = data["data"].get("total", 0)
        if len(topics) >= total:
            break
            
        page += 1
        time.sleep(0.5)
        
    return topics

def fetch_topic_details(topic_id, session):
    url = f"https://api.zizizaizai.com/v3/topic/table/{topic_id}"
    try:
        res = session.get(url, headers=HEADERS, timeout=20)
        if res.status_code == 200:
            data = res.json()
            if data.get("code") == 20000:
                return data["data"]
    except requests.exceptions.RequestException as e:
        print(f"  Timeout/Error for topic {topic_id}: {e}")
    return None

def main():
    print("Starting to fetch topics...")
    topics = fetch_topics()
    print(f"Fetched {len(topics)} topics. Now fetching details...")
    
    full_data = []
    session = get_session()
    for i, topic in enumerate(topics):
        t_id = topic["id"]
        print(f"[{i+1}/{len(topics)}] Fetching details for topic ID {t_id} ({topic['name']})...")
        details = fetch_topic_details(t_id, session)
        if details:
            full_data.append(details)
        else:
            print(f"Failed to fetch details for {t_id}")
        time.sleep(0.3)  # Be nice to the API
        
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
