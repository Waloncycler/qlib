import json
import yaml
import requests
import time
from pathlib import Path

def login():
    with open("secret.yaml") as f:
        config = yaml.safe_load(f)
    email = config.get("zizi_email")
    password = config.get("zizi_password")
    url = "https://api.zizizaizai.com/v2/login/email/login"
    payload = {"email": email, "password": password}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quant.zizizaizai.com/login",
        "Origin": "https://quant.zizizaizai.com",
        "Content-Type": "application/json"
    }
    for attempt in range(1, 5):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 20000:
                    return data["data"]["token"]
        except:
            pass
        time.sleep(2)
    return None

def fix_topics():
    token = login()
    if not token:
        print("Login failed")
        return
        
    klines_file = Path("../../data/cn_stock/hierarchical/signals/zizizaizai_klines.json")
    with open(klines_file, "r") as f:
        klines = json.load(f)
        
    # Re-fetch 109 and other skipped topics just to be sure
    for tid in ["109", "11", "9", "6"]:
        url = f"https://api.zizizaizai.com/v3/topic/table/{tid}/kline"
        print(f"Fetching {tid}...")
        r = requests.get(url, headers={"authorization": f"Bearer {token}", "user-agent": "Mozilla/5.0"})
        if r.status_code == 200:
            data = r.json()
            if data.get("code") == 20000:
                klines[tid] = data.get("data", [])
                print(f"Successfully fetched {len(klines[tid])} records for {tid}")
            else:
                print(f"Bad code for {tid}: {data}")
        else:
            print(f"Status {r.status_code} for {tid}")
            
    with open(klines_file, "w", encoding="utf-8") as f:
        json.dump(klines, f, ensure_ascii=False)
        
if __name__ == "__main__":
    fix_topics()
