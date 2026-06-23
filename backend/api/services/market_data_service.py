import json
import requests
import time
from loguru import logger
import urllib3
from functools import lru_cache

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@lru_cache(maxsize=100)
def _fetch_sina_history_cached(tencent_code: str):
    """Internal cached function to fetch 5000 bars of 5-min data from Sina."""
    return _fetch_sina_history_no_cache(tencent_code)

def _fetch_sina_history_no_cache(tencent_code: str):
    sina_url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={tencent_code}&scale=5&datalen=5000"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(sina_url, headers=headers, timeout=10, verify=False)
        if res.status_code == 200:
            data = res.json()
            if data and isinstance(data, list) and len(data) > 0:
                return data
            logger.warning(f"Sina returned empty data for {tencent_code}")
        else:
            logger.error(f"Sina API error {res.status_code} for {tencent_code}")
    except Exception as e:
        logger.error(f"Error fetching Sina history for {tencent_code}: {e}")
    return None


def _get_pre_close_for_date(symbol: str, target_date: str):
    try:
        daily_data = fetch_daily_data(symbol, datalen=30)
        # Find the last trading day before target_date
        pre_close = None
        for item in daily_data:
            if item['date'] < target_date:
                pre_close = item['price'] # price is close
            elif item['date'] >= target_date:
                break
        return pre_close
    except Exception:
        return None

def fetch_intraday_data(symbol: str, date: str) -> list:
    """Fetches historical 1-minute intraday data from Tencent, or 5-min from Sina if historical."""
    # date format expected by Tencent is YYYYMMDD
    date_str = date.replace("-", "")
    tencent_code = symbol.lower()
    url = f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={tencent_code}&date={date_str}"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    data = None
    try:
        res = requests.get(url, headers=headers, timeout=5, verify=False)
        if res.status_code == 200:
            data = res.json()
    except Exception as e:
        logger.error(f"Tencent minute query failed for {tencent_code}: {e}")
    
    # 1. Try to use Tencent data if it matches the requested date (usually today or last trading day)
    if data and data.get("code") == 0 and data.get("data") and tencent_code in data["data"]:
        tencent_data = data["data"][tencent_code].get("data", {})
        returned_date = tencent_data.get("date", "")
        qt = data["data"][tencent_code].get("qt", {}).get(tencent_code, [])
        pre_close = float(qt[4]) if len(qt) > 4 else None
        
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
                        "volume": vol,
                        "pre_close": pre_close
                    })
            if parsed:
                return parsed
            
    # 2. Fallback to Sina 5-minute historical K-line data for past dates
    # We use a non-cached fetch first if we want to be sure, but let's stick to cached for performance
    # and just ensure we don't cache failures.
    sina_data = _fetch_sina_history_cached(tencent_code)
    
    # If cache gave us None, try one more time without cache in case it was a transient failure
    if sina_data is None:
        sina_data = _fetch_sina_history_no_cache(tencent_code)

    if sina_data:
        parsed = []
        pre_close = _get_pre_close_for_date(symbol, date)
        for item in sina_data:
            day_str = item.get("day", "")
            if day_str.startswith(date):
                time_str = day_str.split(" ")[1][:5] # e.g. "09:35"
                point = {
                    "time": time_str,
                    "price": float(item.get("close", 0)),
                    "volume": float(item.get("volume", 0)) / 100.0 # Convert shares to lots to match Tencent
                }
                if pre_close is not None:
                    point["pre_close"] = pre_close
                parsed.append(point)
        if parsed:
            return parsed

    return []

def fetch_daily_data(symbol: str, datalen: int = 30) -> list:
    """Fetches daily K-line data from Sina."""
    tencent_code = symbol.lower()
    # scale=240 means daily
    sina_url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={tencent_code}&scale=240&datalen={datalen}"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(sina_url, headers=headers, timeout=5, verify=False)
        if res.status_code == 200:
            sina_data = res.json()
            parsed = []
            for item in sina_data:
                parsed.append({
                    "date": item.get("day", "").split(" ")[0],
                    "price": float(item.get("close", 0)),
                    "volume": float(item.get("volume", 0)) / 100.0,
                    "high": float(item.get("high", 0)),
                    "low": float(item.get("low", 0)),
                    "open": float(item.get("open", 0))
                })
            return parsed
    except Exception as e:
        logger.error(f"Error fetching daily data for {symbol}: {e}")
    
    return []
