import json
import time
import subprocess
from pathlib import Path
import os
import sys

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
    for attempt in range(1, 4):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data and (data.get("code") == 20000 or "data" in data):
                    return data
            print(f"  Attempt {attempt} failed, retrying...")
        except Exception as e:
            print(f"  Attempt {attempt} exception: {e}")
        if attempt < 3:
            time.sleep(attempt * 3) # Sleep 3s, 6s
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
        
        url = f"https://api.zizizaizai.com/v3/topic/table/{t_id}/kline"
        data = run_curl(url)
        
        if data and data.get("code") == 20000:
            with lock:
                klines_data[t_id] = data["data"]
                # Save incrementally to avoid losing data on crash (Atomic Write)
                tmp_file = str(out_file) + ".tmp"
                with open(tmp_file, "w", encoding="utf-8") as f:
                    json.dump(klines_data, f, ensure_ascii=False)
                os.replace(tmp_file, out_file)
            print(f"  Got {len(data['data'])} daily records for {t_name}.")
        else:
            print(f"  Failed to fetch klines for {t_id}")
            
    # Allow passing max_workers via arguments, default 3
    max_workers = 3
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

    print(f"Successfully finished all klines.")

if __name__ == "__main__":
    main()
