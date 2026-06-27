from fastapi import APIRouter, HTTPException, Query
import json
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel
from loguru import logger
from modules.backtest.service import (
    get_backtest_metrics_and_curve,
    run_single_stock_backtest,
    run_intelligent_backtest_service,
    get_signal_backtest_results,
    run_signal_backtest_service,
    run_data_download_service,
    get_leaderboard_service,
)
from core.config import DATA_DIR, WORKSPACE_DIR

router = APIRouter()

class SingleBacktestRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str

@router.get("/api/backtest/results")
def get_backtest_results_route(
    enable_ml_filter: bool = Query(False), 
    model_version: str = Query("v3_binary"), 
    top_k: int = Query(10), 
    enable_market_timing: bool = Query(True),
    vol: bool = Query(True),
    crash: bool = Query(False),
    boost: bool = Query(False)
):
    """Returns the latest signal backtest results (new default)."""
    try:
        data = get_signal_backtest_results(
            enable_ml_filter=enable_ml_filter, 
            model_version=model_version, 
            top_k=top_k, 
            enable_market_timing=enable_market_timing,
            enable_turnover_filter=vol,
            enable_crash_filter=crash,
            enable_selection_boost=boost
        )
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error fetching backtest results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/backtest/results/legacy")
def get_backtest_results_legacy_route():
    """Returns the latest Qlib-based backtest results (legacy)."""
    try:
        data = get_backtest_metrics_and_curve()
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error fetching legacy backtest results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/backtest/single")
def run_single_stock_backtest_route(req: SingleBacktestRequest):
    try:
        return run_single_stock_backtest(req.symbol, req.start_date, req.end_date)
    except Exception as e:
        logger.error(f"Error running single backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/backtest/intelligent")
def run_intelligent_backtest_route(
    enable_ml_filter: bool = Query(False), 
    model_version: str = Query("v3_binary"), 
    top_k: int = Query(10), 
    enable_market_timing: bool = Query(True),
    vol: bool = Query(True),
    crash: bool = Query(False),
    boost: bool = Query(False)
):
    """Run AI signal backtest (new default)."""
    try:
        result = run_signal_backtest_service(
            enable_ml_filter=enable_ml_filter, 
            model_version=model_version, 
            top_k=top_k, 
            enable_market_timing=enable_market_timing,
            enable_turnover_filter=vol,
            enable_crash_filter=crash,
            enable_selection_boost=boost
        )
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Error running signal backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/backtest/leaderboard")
def get_backtest_leaderboard_route():
    """Returns the leaderboard of all backtest strategies."""
    try:
        return get_leaderboard_service()
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/backtest/todays-picks")
def get_todays_picks_route(model_version: str = Query("v3_binary"), top_k: int = Query(10), use_composite: bool = Query(True)):
    """Get the ML filtered picks for today's AI pre-market report."""
    try:
        from modules.backtest.scoring import get_todays_picks_service
        return get_todays_picks_service(model_version=model_version, top_k=top_k, use_composite=use_composite)
    except Exception as e:
        logger.error(f"Error fetching today's picks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/backtest/download-data")
def download_data_route():
    """Download OHLCV data for all stocks in the AI report universe."""
    try:
        result = run_data_download_service()
        return result
    except Exception as e:
        logger.error(f"Error downloading data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/backtest/pool/dates")
def get_available_pool_dates():
    """Returns a list of dates that have available strategy pool data."""
    dates = set()
    
    # 1. Try to get dates from market sentiment (best indicator of trading days with data)
    sentiment_path = DATA_DIR / "signals" / "market_sentiment.csv"
    if sentiment_path.exists():
        try:
            import pandas as pd
            df = pd.read_csv(sentiment_path)
            if 'date' in df.columns:
                for d in df['date'].dropna():
                    dates.add(str(d).split(' ')[0])
        except Exception as e:
            logger.error(f"Error reading dates from sentiment: {e}")

    # 2. Try to get dates from AI reports
    reports_path = DATA_DIR / "signals" / "zizizaizai_reports.json"
    if reports_path.exists():
        try:
            with open(reports_path, "r", encoding="utf-8") as f:
                reports = json.load(f)
            for report in reports:
                if "created_time" in report:
                    d = report["created_time"].split(" ")[0]
                    dates.add(d)
                elif "title" in report:
                    import re
                    match = re.search(r"20\d{6}", report["title"])
                    if match:
                        d_raw = match.group(0)
                        d = f"{d_raw[:4]}-{d_raw[4:6]}-{d_raw[6:8]}"
                        dates.add(d)
        except Exception as e:
            logger.error(f"Error reading dates from reports: {e}")
            
    return {"dates": sorted(list(dates), reverse=True)}

@router.get("/api/backtest/pool")
def get_strategy_pool(date: str = Query(..., description="Date in YYYY-MM-DD format")):
    """
    Returns the combined strategy stock pool for a specific date.
    Combines AI Morning Reports (point in time) and Market Topics (latest snapshot).
    """
    try:
        # Validate date format
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    result = {
        "date": date,
        "sources": {
            "ai_reports": [],
            "market_topics": []
        }
    }

    # 1. Process AI Morning Reports
    reports_path = DATA_DIR / "signals" / "zizizaizai_reports.json"
    if reports_path.exists():
        try:
            with open(reports_path, "r", encoding="utf-8") as f:
                reports = json.load(f)
                
            # Find the report that matches the requested date
            target_report = None
            for report in reports:
                if "created_time" in report and report["created_time"].startswith(date):
                    target_report = report
                    break
                elif "title" in report and date.replace("-", "") in report["title"]:
                    target_report = report
                    break
            
            if target_report and "stock_pool" in target_report:
                # The stock_pool in reports is already well-structured
                result["sources"]["ai_reports"] = target_report["stock_pool"]
        except Exception as e:
            logger.error(f"Error reading reports: {e}")

    # 2. Process Market Topics (Filtered by date)
    topics_path = DATA_DIR / "signals" / "zizizaizai_topics.json"
    if topics_path.exists():
        try:
            with open(topics_path, "r", encoding="utf-8") as f:
                topics = json.load(f)
            
            # Formats to look for in topic name: (260608), (20260608), 260608, 20260608
            date_short = date.replace("-", "")[2:] # 260608
            date_long = date.replace("-", "") # 20260608
            
            grouped_topics = {}
            for topic in topics:
                concept_name = topic.get("name", "Unknown Topic")
                
                # Check if this topic belongs to the target date
                # We show topics that either have the date in name OR are marked as top topics (latest)
                # But to be precise for historical view, we prioritize name match
                is_date_match = date_short in concept_name or date_long in concept_name
                
                # If we are looking at the latest date in the system, we can show "is_top" topics too
                # But for now, let's stick to date match or recent topics
                if not is_date_match:
                    continue

                rows = topic.get("rows", [])
                
                stocks = []
                for row in rows:
                    stock_name = row.get("个股", "")
                    if stock_name:
                        # Try to find symbol/code from other sources or just keep name
                        stocks.append({"name": stock_name, "code": "", "symbol": ""})
                
                if stocks:
                    grouped_topics[concept_name] = stocks
            
            # If no date-specific topics found, maybe it's the latest date and we should show 'is_top' topics
            if not grouped_topics:
                for topic in topics:
                    if topic.get("is_top") == 1:
                        concept_name = topic.get("name", "Unknown Topic")
                        rows = topic.get("rows", [])
                        stocks = [{"name": r.get("个股", ""), "code": "", "symbol": ""} for r in rows if r.get("个股")]
                        if stocks:
                            grouped_topics[concept_name] = stocks

            # Convert grouped topics to array format
            for concept, stocks in grouped_topics.items():
                result["sources"]["market_topics"].append({
                    "concept": concept,
                    "is_new": False,
                    "core_stocks": stocks,
                    "other_stocks": []
                })
        except Exception as e:
            logger.error(f"Error reading topics: {e}")

    return result

from pydantic import BaseModel

class LiveQuotesRequest(BaseModel):
    symbols: list[str]

@router.post("/api/backtest/live-quotes")
def get_live_quotes(request: LiveQuotesRequest):
    """Get real-time intraday quotes from Tencent Finance."""
    try:
        from modules.backtest.live_quotes import get_live_quotes_service
        return get_live_quotes_service(request.symbols)
    except Exception as e:
        logger.error(f"Error fetching live quotes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Strategy Comparison API
# ============================================================

STRATEGY_COMPARISON_PATH = WORKSPACE_DIR / "data" / "cn_stock" / "predictions" / "strategy_comparison.json"


@router.get("/api/backtest/strategy-compare")
def get_strategy_comparison():
    """返回全量策略对比数据（按 Sharpe 降序）。"""
    try:
        if not STRATEGY_COMPARISON_PATH.exists():
            return {"status": "success", "data": []}
        with open(STRATEGY_COMPARISON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 按 sharpe 降序排列
        data.sort(key=lambda x: x.get("sharpe", 0), reverse=True)
        # 重新编号 id
        for i, item in enumerate(data):
            item["id"] = i + 1
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error reading strategy comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))


