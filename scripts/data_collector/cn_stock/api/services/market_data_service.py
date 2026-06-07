import json
import requests
import time
from loguru import logger
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_intraday_data(symbol: str, date: str) -> list:
    """Fetches historical 1-minute intraday data from Tencent, or 5-min from Sina if historical."""
    # date format expected by Tencent is YYYYMMDD
    date_str = date.replace("-", "")
    tencent_code = symbol.lower()
    url = f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={tencent_code}&date={date_str}"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    data = None
    for attempt in range(1, 4):
        try:
            res = requests.get(url, headers=headers, timeout=5, verify=False)
            if res.status_code == 200:
                data = res.json()
                break
        except Exception as e:
            if attempt < 3:
                time.sleep(1)
    
    # 1. Try to use Tencent data if it matches the requested date (usually today or last trading day)
    if data and data.get("code") == 0 and data.get("data") and tencent_code in data["data"]:
        tencent_data = data["data"][tencent_code].get("data", {})
        returned_date = tencent_data.get("date", "")
        
        if returned_date == date_str:
            minute_data = tencent_data.get("data", [])
            parsed = []
            prev_cum_vol = 0
            for item in minute_data:
                parts = item.split(" ")
                if len(parts) >= 3:
                    cum_vol = float(parts[2])
                    vol = cum_vol - prev_cum_vol
                    prev_cum_vol = cum_vol
                    parsed.append({
                        "time": f"{parts[0][:2]}:{parts[0][2:]}",
                        "price": float(parts[1]),
                        "volume": vol
                    })
            return parsed
            
    # 2. Fallback to Sina 5-minute historical K-line data for past dates
    # datalen=1000 5-min candles is about 20 trading days of history
    sina_url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={tencent_code}&scale=5&datalen=1000"
    sina_res = requests.get(sina_url, headers=headers, timeout=5, verify=False)
    if sina_res.status_code == 200:
        sina_data = sina_res.json()
        parsed = []
        for item in sina_data:
            day_str = item.get("day", "")
            if day_str.startswith(date):
                time_str = day_str.split(" ")[1][:5] # e.g. "09:35"
                parsed.append({
                    "time": time_str,
                    "price": float(item.get("close", 0)),
                    "volume": float(item.get("volume", 0)) / 100.0 # Convert shares to lots to match Tencent
                })
        if parsed:
            return parsed

    return []
