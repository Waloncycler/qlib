import os
import yaml
import requests
import json
from pathlib import Path

def get_token():
    config_path = Path("secret.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
        
    email = config.get("zizi_email")
    password = config.get("zizi_password")
    
    url = "https://api.zizizaizai.com/v2/login/email/login"
    payload = {"email": email, "password": password}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "Referer": "https://quant.zizizaizai.com/login",
        "Origin": "https://quant.zizizaizai.com"
    }
    
    res = requests.post(url, json=payload, headers=headers, timeout=30)
    data = res.json()
    return data.get("data", {}).get("access_token") or data.get("data", {}).get("token") or data.get("token")

def fetch_109():
    token = get_token()
    if not token:
        print("Failed to get token")
        return
        
    print("Got token")
    # Also fetch 11 just in case it failed too
    k_file = Path("/Users/walox/qlib/data/cn_stock/hierarchical/signals/zizizaizai_klines.json")
    with open(k_file, "r") as f:
        all_klines = json.load(f)
        
    for tid in ["109", "11", "9", "6"]:
        url = f"https://api.zizizaizai.com/v3/topic/table/{tid}/kline"
        headers = {
            "authorization": f"Bearer {token}",
            "user-agent": "Mozilla/5.0",
            "accept": "application/json",
            "origin": "https://quant.zizizaizai.com",
            "referer": "https://quant.zizizaizai.com/"
        }
        r = requests.get(url, headers=headers)
        data = r.json()
        if data.get("code") == 20000:
            k_data = data.get("data", [])
            print(f"Got {len(k_data)} records for {tid}")
            all_klines[tid] = k_data
            
    with open(k_file, "w", encoding="utf-8") as f:
        json.dump(all_klines, f, ensure_ascii=False)
    print("Saved to zizizaizai_klines.json")

if __name__ == "__main__":
    fetch_109()
