import os
import json
import time
import subprocess
from pathlib import Path

_GLOBAL_TOKEN = None

def get_token():
    global _GLOBAL_TOKEN
    if _GLOBAL_TOKEN:
        return _GLOBAL_TOKEN
        
    token = os.environ.get("ZIZIZAIZAI_TOKEN")
    if not token:
        # Fallback to local config if running standalone
        import yaml
        config_path = Path(__file__).parent / "secret.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                import requests
                email = config.get("zizi_email")
                password = config.get("zizi_password")
                if email and password:
                    res = requests.post("https://api.zizizaizai.com/v2/login/email/login", 
                                      json={"email": email, "password": password},
                                      headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"})
                    if res.status_code == 200:
                        data = res.json()
                        token = data.get("data", {}).get("access_token") or data.get("token")
    _GLOBAL_TOKEN = token
    return token

def run_curl(url):
    token = get_token()

    if not token:
        print("Error: No ZIZIZAIZAI_TOKEN found in environment.")
        return None

    cmd = [
        "curl", "-s",
        "-H", f"authorization: Bearer {token}",
        "-H", "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)",
        "-H", "accept: application/json, text/plain, */*",
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
        time.sleep(attempt * 2)
    return None

def fetch_reports():
    print("Fetching Zizizaizai AI Morning Reports list...")
    list_url = "https://api.zizizaizai.com/v3/ai-report/list?type=morning&page=1&page_size=20"
    list_data = run_curl(list_url)
    
    if not list_data or list_data.get("code") != 20000:
        print("Failed to fetch reports list.")
        return
        
    items = list_data.get("data", {}).get("items", [])
    if not items:
        print("No items found.")
        return
        
    print(f"Found {len(items)} reports. Fetching details...")
    
    # Load existing to avoid redundant fetches
    out_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "cn_stock" / "hierarchical" / "signals"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "zizizaizai_reports.json"
    
    reports_map = {}
    if out_file.exists():
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    for r in loaded:
                        reports_map[str(r.get("id"))] = r
                else:
                    reports_map = loaded
        except Exception as e:
            print(f"Could not load existing reports: {e}")
            
    for item in items:
        r_id = str(item.get("id"))
        if r_id in reports_map and "content" in reports_map[r_id]:
            continue
            
        print(f"Fetching details for report {r_id} ({item.get('title')})...")
        detail_url = f"https://api.zizizaizai.com/v3/ai-report/detail/{r_id}"
        detail_data = run_curl(detail_url)
        
        if detail_data and detail_data.get("code") == 20000:
            reports_map[r_id] = detail_data.get("data", {})
        else:
            print(f"Failed to fetch details for {r_id}")
            # Still save the summary if detail fails
            reports_map[r_id] = item
            
        time.sleep(1) # Be nice to the API
        
    import re
    def extract_stock_pool(content):
        if not content: return []
        
        pool = []
        segments = content.split("概念：")
        
        for i in range(1, len(segments)):
            segment = segments[i]
            # First line of segment is usually the concept title, followed by <br>
            parts = segment.split("<br>", 1)
            raw_title = parts[0]
            
            # Extract just the name before Chinese dashes or brackets
            concept_match = re.match(r'^([^——【]+)', raw_title)
            concept_name = concept_match.group(1).strip() if concept_match else "Uncategorized"
            
            # Check if this is a newly added concept (usually marked with 【新...】)
            is_new = "【新" in raw_title
            
            pattern = r'\[([^\]]+)\]'
            matches = re.findall(pattern, segment)
            
            if not matches:
                continue
                
            core_part = segment
            other_part = ""
            if "其他股票:" in segment:
                sp = segment.split("其他股票:")
                core_part = sp[0]
                other_part = sp[1]
                
            def get_stocks(text_part):
                p = r'\[([^\]]+)\]'
                m = re.findall(p, text_part)
                res = []
                seen_set = set()
                for match_content in m:
                    # extract name and code from inside the bracket
                    name_match = re.search(r'^([\u4e00-\u9fa5A-Za-z]+)', match_content.strip())
                    code_match = re.search(r'(\d{6})', match_content)
                    
                    name = name_match.group(1) if name_match else match_content.strip()
                    code = code_match.group(1) if code_match else ""
                    
                    if code:
                        if code.startswith('6'):
                            symbol = f"SH{code}"
                        elif code.startswith('0') or code.startswith('3'):
                            symbol = f"SZ{code}"
                        elif code.startswith('8') or code.startswith('4'):
                            symbol = f"BJ{code}"
                        else:
                            symbol = code
                    else:
                        symbol = name
                        
                    if symbol not in seen_set:
                        seen_set.add(symbol)
                        res.append({"name": name, "code": code, "symbol": symbol})
                return res

            core_stocks = get_stocks(core_part)
            other_stocks = get_stocks(other_part)
            
            if core_stocks or other_stocks:
                pool.append({
                    "concept": concept_name,
                    "is_new": is_new,
                    "core_stocks": core_stocks,
                    "other_stocks": other_stocks
                })
                
        return pool

    # Convert map to sorted list by ID desc (latest first)
    sorted_reports = [reports_map[k] for k in sorted(reports_map.keys(), key=lambda x: int(x), reverse=True)]
    
    # Attach extracted stock pool
    for report in sorted_reports:
        if "content" in report:
            report["stock_pool"] = extract_stock_pool(report["content"])
        else:
            report["stock_pool"] = []
    
    # Overwrite the map format with list format for easier frontend processing
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(sorted_reports, f, ensure_ascii=False)
        
    print(f"Successfully saved {len(sorted_reports)} reports to {out_file}")

if __name__ == "__main__":
    fetch_reports()
