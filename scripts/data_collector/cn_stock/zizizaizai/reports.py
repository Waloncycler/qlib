import os
import json
import time
import subprocess
from pathlib import Path
import re
import html

_GLOBAL_TOKEN = None
_STOCK_MAP = None

def get_stock_map():
    global _STOCK_MAP
    if _STOCK_MAP is not None:
        return _STOCK_MAP
    
    _STOCK_MAP = {}
    
    def fetch_akshare():
        import akshare as ak
        df = ak.stock_info_a_code_name()
        for _, row in df.iterrows():
            code = str(row['code'])
            name = str(row['name']).replace(' ', '')
            _STOCK_MAP[name] = code
            if name.endswith('A') or name.endswith('B'):
                _STOCK_MAP[name[:-1]] = code

    def fetch_eastmoney():
        import requests
        url = "http://82.push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10000&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048&fields=f12,f14"
        res = requests.get(url, timeout=10)
        data = res.json()
        for item in data.get("data", {}).get("diff", []):
            code = str(item.get("f12"))
            name = str(item.get("f14")).replace(' ', '')
            _STOCK_MAP[name] = code
            if name.endswith('A') or name.endswith('B'):
                _STOCK_MAP[name[:-1]] = code

    for attempt in range(3):
        try:
            fetch_akshare()
            if _STOCK_MAP: break
        except Exception as e:
            print(f"akshare fetch failed: {e}")
            time.sleep(2)
            
    if not _STOCK_MAP:
        try:
            fetch_eastmoney()
        except Exception as e:
            print(f"eastmoney fetch failed: {e}")
            
    return _STOCK_MAP

def get_token():
    global _GLOBAL_TOKEN
    if _GLOBAL_TOKEN: return _GLOBAL_TOKEN
    token = os.environ.get("ZIZIZAIZAI_TOKEN")
    if not token:
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "secret.yaml"
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
    if not token: return None
    cmd = ["curl", "-s", "-H", f"authorization: Bearer {token}", 
           "-H", "user-agent: Mozilla/5.0", "-H", "accept: application/json", url]
    for attempt in range(1, 4):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data and (data.get("code") == 20000 or "data" in data):
                    return data
        except: pass
        time.sleep(attempt * 2)
    return None

def extract_stock_pool(content):
    if not content: return []
    
    cangjie_match = re.search(r'data-clipboard-cangjie="([^"]+)"', content)
    if cangjie_match:
        try:
            raw_json = html.unescape(cangjie_match.group(1))
            nodes = json.loads(raw_json)
            def extract_cangjie_text(node):
                if isinstance(node, str): return node
                if isinstance(node, list):
                    tag = node[0] if len(node) > 0 else ""
                    children_text = "".join([extract_cangjie_text(n) for n in node[2:]])
                    if tag in ["p", "div", "root", "li", "h1", "h2", "h3"]: return children_text + "\n"
                    return children_text
                if isinstance(node, dict):
                    if "text" in node: return node["text"]
                    for k in ["value", "leaf"]:
                        if k in node and isinstance(node[k], str): return node[k]
                return ""
            content = extract_cangjie_text(nodes)
        except:
            content = re.sub(r'<[^>]+>', '\n', content)
    else:
        if isinstance(content, str) and (content.strip().startswith('[[') or content.strip().startswith('[{')):
            try:
                nodes = json.loads(content)
                def extract_generic_text(node):
                    if isinstance(node, str): return node
                    if isinstance(node, list): return "\n".join([extract_generic_text(n) for n in node])
                    if isinstance(node, dict):
                        if "text" in node: return node["text"]
                        if "children" in node: return "\n".join([extract_generic_text(n) for n in node["children"]])
                        for k in ["value", "leaf"]:
                             if k in node and isinstance(node[k], str): return node[k]
                    return ""
                content = extract_generic_text(nodes)
            except: pass
        content = re.sub(r'<[^>]+>', '\n', content)

    content = re.sub(r' +', ' ', content)
    content = re.sub(r'\n+', '\n', content)
    
    STOP_WORDS = {
        "公司", "标的", "个股", "上市公司", "概念", "板块", "领域", "行业", "厂商", "供应商", 
        "相关", "产业链", "解决方案", "项目", "预期", "需求", "环节", "等", "及", "以及", 
        "暂无", "明确", "关注", "建议", "核心", "潜力", "其他", "部分", "很多", "不少",
        "战略", "新材料", "算力", "芯片", "科技", "创新", "量子", "生物", "制造", "氢能", "核聚变",
        "两岸", "贸易", "基建", "军工", "区域", "对台", "福建"
    }

    def is_valid_stock_name(name):
        if not name or len(name) < 2 or len(name) > 8: return False
        if len(name) > 5 and any(sw in name for sw in STOP_WORDS): return False
        if name in ["核心股票", "其他股票", "潜力标的", "标的", "无"]: return False
        return True

    def extract_stocks(text):
        stocks = []
        seen = set()
        stock_map = get_stock_map()
        
        for line in text.split('\n'):
            line = line.strip()
            if not line: continue
            
            # 1. Bracketed format
            brackets = re.findall(r'\[([^\]]+)\]', line)
            if brackets:
                for b in brackets:
                    name_m = re.search(r'([\u4e00-\u9fa5A-Za-z0-9]{2,})', b)
                    code_m = re.search(r'(\d{6})', b)
                    name = name_m.group(1) if name_m else b.strip()
                    code = code_m.group(1) if code_m else ""
                    
                    if not code and stock_map:
                        code = stock_map.get(name, "")
                        
                    if not code: continue  # STRICT: Must have a stock code
                    
                    symbol = name
                    if code:
                        if code.startswith('6') or code.startswith('9'): symbol = f"SH{code}"
                        elif code.startswith('0') or code.startswith('3'): symbol = f"SZ{code}"
                        elif code.startswith('8') or code.startswith('4'): symbol = f"BJ{code}"
                    if symbol not in seen:
                        seen.add(symbol)
                        stocks.append({"name": name, "code": code, "symbol": symbol})
                continue
            
            # 2. Comma separated lists (fallback)
            clean_line = re.sub(r'^(?:核心股票|其他股票|潜力标的|标的)[：:]\s*', '', line)
            candidates = re.split(r'[、,，\s]+', clean_line)
            for cand in candidates:
                cand = cand.strip()
                if not cand or len(cand) < 2 or len(cand) > 8: continue
                if not re.search(r'[\u4e00-\u9fa5]', cand) and not re.match(r'^\d{6}$', cand): continue
                
                name_m = re.search(r'^([\u4e00-\u9fa5A-Za-z0-9]+)', cand)
                code_m = re.search(r'(\d{6})', cand)
                name = name_m.group(1) if name_m else cand
                code = code_m.group(1) if code_m else ""
                
                if not code and stock_map:
                    code = stock_map.get(name, "")
                    
                if not code: continue  # STRICT: Must have a stock code
                
                symbol = name
                if code:
                    if code.startswith('6') or code.startswith('9'): symbol = f"SH{code}"
                    elif code.startswith('0') or code.startswith('3'): symbol = f"SZ{code}"
                    elif code.startswith('8') or code.startswith('4'): symbol = f"BJ{code}"
                if symbol not in seen:
                    seen.add(symbol)
                    stocks.append({"name": name, "code": code, "symbol": symbol})
        return stocks

    pool = []
    segments = re.split(r'概念[：:]', content)
    
    for i in range(1, len(segments)):
        segment = segments[i].strip()
        if not segment: continue
        
        lines = [l.strip() for l in segment.split('\n') if l.strip()]
        if not lines: continue
        
        concept_parts = []
        header_pattern = r'核心逻辑|催化事件|潜力标的|核心股票|其他股票|标的'
        
        first_line = lines[0]
        m_header = re.search(header_pattern, first_line)
        if m_header:
            concept_name = first_line[:m_header.start()].strip()
        else:
            for line in lines:
                if re.search(header_pattern, line): break
                concept_parts.append(line)
            concept_name = " ".join(concept_parts)
            
        concept_match = re.match(r'^([^——【（(]+)', concept_name)
        concept_name = concept_match.group(1).strip() if concept_match else concept_name.strip()
        if not concept_name or len(concept_name) < 2: concept_name = "未命名题材"
        
        is_new = "【新" in lines[0] or "【新" in concept_name

        # Find core and other blocks within the segment
        core_stocks = []
        other_stocks = []
        
        # Logic: 
        # "核心股票" -> everything until "其他股票" or end
        # "其他股票" -> everything until end
        # If none of above, maybe "潜力标的" -> everything until end
        
        m_core = re.search(r'(?:核心股票|潜力标的)[：:](.*?)(?=(?:\n其他股票|\n概念|$))', segment, re.S)
        if m_core:
            core_stocks = extract_stocks(m_core.group(1))
            
        m_other = re.search(r'其他股票[：:](.*?)(?=(?:\n概念|$))', segment, re.S)
        if m_other:
            other_stocks = extract_stocks(m_other.group(1))

        core_symbols = {s["symbol"] for s in core_stocks}
        other_stocks = [s for s in other_stocks if s["symbol"] not in core_symbols]
        
        if core_stocks or other_stocks:
            pool.append({
                "concept": concept_name,
                "is_new": is_new,
                "core_stocks": core_stocks,
                "other_stocks": other_stocks
            })
            
    pool.sort(key=lambda x: not x.get("is_new", False))
    return pool

def fetch_reports(max_pages=20):
    all_items = []
    print(f"Fetching Zizizaizai AI Morning Reports list (up to {max_pages} pages)...")
    for page in range(1, max_pages + 1):
        list_url = f"https://api.zizizaizai.com/v3/ai-report/list?type=morning&page={page}&page_size=50"
        list_data = run_curl(list_url)
        if not list_data or list_data.get("code") != 20000: break
        items = list_data.get("data", {}).get("items", [])
        if not items: break
        all_items.extend(items)
        print(f"  Page {page}: found {len(items)} items.")
        last_item_date = items[-1].get("created_time", "")
        if last_item_date and "2024-" in last_item_date: break
        time.sleep(1)

    if not all_items: return
    out_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "cn_stock" / "hierarchical" / "signals"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "zizizaizai_reports.json"
    
    reports_map = {}
    if out_file.exists():
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                for r in loaded: reports_map[str(r.get("id"))] = r
        except: pass
            
    for item in all_items:
        r_id = str(item.get("id"))
        if r_id in reports_map and "content" in reports_map[r_id]:
            report = reports_map[r_id]
            report["stock_pool"] = extract_stock_pool(report.get("content", ""))
            continue
        print(f"Fetching details for report {r_id}...")
        detail_url = f"https://api.zizizaizai.com/v3/ai-report/detail/{r_id}"
        detail_data = run_curl(detail_url)
        if detail_data and detail_data.get("code") == 20000:
            reports_map[r_id] = detail_data.get("data", {})
        else: reports_map[r_id] = item
        time.sleep(1) 

    sorted_reports = [reports_map[k] for k in sorted(reports_map.keys(), key=lambda x: int(x), reverse=True)]
    for report in sorted_reports:
        if "content" in report: report["stock_pool"] = extract_stock_pool(report["content"])
        else: report["stock_pool"] = []
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(sorted_reports, f, ensure_ascii=False)
    print(f"Successfully saved {len(sorted_reports)} reports to {out_file}")

if __name__ == "__main__":
    fetch_reports()
