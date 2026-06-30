import json
import time
import subprocess
from pathlib import Path
import os
import sys

# Ensure backend/ is on sys.path for the shared auth module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from modules.intelligence.zizizaizai.auth import get_token

TOKEN = get_token() or ""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_session():
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=2, status_forcelist=[429, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def fetch_kline(url, session):
    headers = {
        "authorization": f"Bearer {TOKEN}",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "accept": "application/json, text/plain, */*",
        "origin": "https://quant.zizizaizai.com",
        "referer": "https://quant.zizizaizai.com/"
    }
    for attempt in range(1, 4):
        try:
            res = session.get(url, headers=headers, timeout=20)
            if res.status_code == 200:
                data = res.json()
                if data and (data.get("code") == 20000 or "data" in data):
                    return data
            print(f"  Attempt {attempt} failed (Status: {res.status_code}), retrying...")
        except requests.exceptions.RequestException as e:
            print(f"  Attempt {attempt} exception: {e}")
        if attempt < 3:
            time.sleep(attempt * 2)
    return None

def main():
    topics_file = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "cn_stock" / "hierarchical" / "signals" / "zizizaizai_topics.json"
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

    import datetime
    force_update = "--force" in sys.argv or "-f" in sys.argv

    # Read latest date from market_sentiment.csv
    latest_market_date = None
    sentiment_file = topics_file.parent / "market_sentiment.csv"
    if sentiment_file.exists():
        try:
            with open(sentiment_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if len(lines) > 1:
                    headers = lines[0].strip().split(",")
                    date_idx = headers.index("date") if "date" in headers else 0
                    dates = []
                    for line in lines[1:]:
                        parts = line.strip().split(",")
                        if len(parts) > date_idx:
                            dates.append(parts[date_idx])
                    if dates:
                        latest_market_date = max(dates)
        except Exception as e:
            print("Error parsing market_sentiment.csv:", e)
            
    if not latest_market_date:
        latest_market_date = datetime.date.today().strftime("%Y-%m-%d")
        
    print(f"Latest market trading date identified: {latest_market_date}")

    import concurrent.futures
    import threading
    
    lock = threading.Lock()
    
    session = get_session()
    
    def process_topic(topic, idx, total):
        t_id = str(topic.get("id"))
        t_name = topic.get("name")
        
        # Smart skip logic: check if last K-line record is equal to or newer than latest_market_date
        has_latest = False
        with lock:
            if not force_update and t_id in klines_data and klines_data[t_id]:
                last_record = klines_data[t_id][-1]
                last_date = last_record.get("trade_date")
                if last_date and latest_market_date and last_date >= latest_market_date:
                    has_latest = True

        if has_latest:
            print(f"[{idx+1}/{total}] Skipping topic ID {t_id} ({t_name}), already up-to-date.")
            return
            
        print(f"[{idx+1}/{total}] Fetching klines for topic ID {t_id} ({t_name})...")
        
        t_key = topic.get("unique_key", t_id)
        url = f"https://api.zizizaizai.com/v3/topic/table/{t_key}/kline"
        data = fetch_kline(url, session)
        
        if data and data.get("code") == 20000:
            with lock:
                klines_data[t_id] = data["data"]
            print(f"  Got {len(data['data'])} daily records for {t_name}.")
        else:
            print(f"  Failed to fetch klines for {t_id}")
            
        time.sleep(3.5)  # Respect 20 req/min limit
            
    # Allow passing max-workers via arguments, default 2 to stay within rate limits
    max_workers = 2
    for arg in sys.argv:
        if arg.startswith("--max-workers="):
            try:
                max_workers = int(arg.split("=")[1])
            except ValueError:
                pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_topic, topic, i, len(topics)) for i, topic in enumerate(topics)]
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Exception during fetching: {e}")

    # Save once at the end
    print(f"Saving all klines to {out_file}...")
    tmp_file = str(out_file) + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(klines_data, f, ensure_ascii=False)
    os.replace(tmp_file, out_file)

    print(f"Successfully finished all klines.")

if __name__ == "__main__":
    main()
