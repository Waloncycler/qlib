import json
import re
import requests
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from loguru import logger

from api.core_config import DATA_DIR, resolver, iwencai_adapter
from api.services.market_data_service import fetch_intraday_data

router = APIRouter()

class SearchRequest(BaseModel):
    query: str

@router.post("/api/iwencai/search")
def iwencai_search(req: SearchRequest):
    """NL search via iWencai"""
    try:
        df = iwencai_adapter.fetch_iwencai(req.query)
        if df.empty:
            return {"status": "success", "data": []}
        df = df.fillna("")
        records = df.to_dict(orient="records")
        return {"status": "success", "data": records}
    except Exception as e:
        logger.error(f"Error calling iWencai: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/stock/{symbol}/fetch")
def fetch_realtime_stock(symbol: str, layer: str = None):
    """Triggers real-time fetching for a single stock."""
    try:
        success = resolver.resolve_single_stock(symbol, layer=layer)
        if success:
            return {"status": "success", "message": f"Data for {symbol} is up to date."}
        else:
            raise HTTPException(status_code=500, detail="Failed to fetch data")
    except Exception as e:
        logger.error(f"Error fetching stock {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/data/topics")
def get_topics():
    """Returns topics JSON and latest Klines JSON"""
    topic_file = DATA_DIR / "signals/zizizaizai_topics.json"
    kline_file = DATA_DIR / "signals/zizizaizai_klines.json"
    
    data = {"topics": [], "klines": {}}
    if topic_file.exists():
        with open(topic_file, "r", encoding="utf-8") as f:
            data["topics"] = json.load(f)
            
    if kline_file.exists():
        with open(kline_file, "r", encoding="utf-8") as f:
            data["klines"] = json.load(f)
            
    return data

@router.get("/api/data/reports")
def get_reports():
    """Returns the parsed AI morning reports JSON"""
    report_file = DATA_DIR / "signals/zizizaizai_reports.json"
    if report_file.exists():
        with open(report_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@router.get("/api/data/{layer}/{filename}")
def get_data_file(layer: str, filename: str):
    """Serves a static data file (CSV or JSON) from the hierarchical data directory."""
    file_path = DATA_DIR / layer / filename
    
    if not file_path.exists():
        if filename.endswith(".json"):
            return Response(content="[]", media_type="application/json")
        else:
            return Response(content="", media_type="text/csv")
        
    return FileResponse(path=file_path, filename=filename)

@router.get("/api/stock/{symbol}/intraday/{date}")
def get_intraday_data(symbol: str, date: str):
    """Fetches historical 1-minute or 5-min intraday data."""
    try:
        parsed = fetch_intraday_data(symbol, date)
        return {"status": "success", "data": parsed}
    except Exception as e:
        logger.error(f"Error fetching intraday for {symbol}: {e}")
        return {"status": "success", "data": []}

@router.get("/api/resolve_symbol/{query}")
def resolve_symbol(query: str):
    query = query.strip()
    
    # If it already looks like SH600519 or SZ000001
    if len(query) >= 6 and any(query.upper().startswith(prefix) for prefix in ["SH", "SZ", "BJ"]):
        return {"symbol": query.upper()}
        
    # If it is purely a 6-digit number, prepend SH/SZ
    if query.isdigit() and len(query) == 6:
        if query.startswith("6"): return {"symbol": f"SH{query}"}
        if query.startswith("0") or query.startswith("3"): return {"symbol": f"SZ{query}"}
        if query.startswith("4") or query.startswith("8") or query.startswith("9"): return {"symbol": f"BJ{query}"}
        
    # Use Tencent Smartbox API for Chinese name or pinyin autocomplete
    try:
        url = f"https://smartbox.gtimg.cn/s3/?q={query}&t=all"
        res = requests.get(url, timeout=5)
        text = res.text
        match = re.search(r'v_hint="([^"]+)"', text)
        if match:
            results = match.group(1).split('^')
            for r in results:
                parts = r.split('~')
                if len(parts) >= 2:
                    market = parts[0].upper()
                    code = parts[1]
                    if market in ["SH", "SZ", "BJ"]:
                        return {"symbol": f"{market}{code}"}
    except Exception as e:
        logger.error(f"Tencent search failed: {e}")
        
    # Fallback to Eastmoney Smartbox API (better for BSE and newer stocks)
    try:
        url = f"https://searchapi.eastmoney.com/api/suggest/get?input={query}&type=14&token=D43BF722C8E33BDC906FB84D85E326E8"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        if "QuotationCodeTable" in data and data["QuotationCodeTable"].get("Data"):
            first_match = data["QuotationCodeTable"]["Data"][0]
            code = first_match["Code"]
            if code.startswith("6"): return {"symbol": f"SH{code}"}
            if code.startswith("0") or code.startswith("3"): return {"symbol": f"SZ{code}"}
            if code.startswith("4") or code.startswith("8") or code.startswith("9"): return {"symbol": f"BJ{code}"}
    except Exception as e:
        logger.error(f"Eastmoney search failed: {e}")
        
    raise HTTPException(status_code=404, detail="Stock not found")
