from fastapi import APIRouter, HTTPException, Query
import json
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel
from loguru import logger
from api.services.backtest_service import get_backtest_metrics_and_curve, run_single_stock_backtest

router = APIRouter()

class SingleBacktestRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str

@router.get("/api/backtest/results")
def get_backtest_results_route():
    """Returns the latest backtest metrics and curve."""
    try:
        data = get_backtest_metrics_and_curve()
        return {"status": "success", "data": data}
    except Exception as e:
        logger.error(f"Error fetching backtest results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/backtest/single")
def run_single_stock_backtest_route(req: SingleBacktestRequest):
    try:
        return run_single_stock_backtest(req.symbol, req.start_date, req.end_date)
    except Exception as e:
        logger.error(f"Error running single backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))

DATA_DIR = Path(__file__).resolve().parents[5] / "data" / "cn_stock" / "hierarchical"

@router.get("/api/backtest/pool/dates")
def get_available_pool_dates():
    """Returns a list of dates that have available strategy pool data (AI reports)."""
    dates = set()
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
                    # try extract YYYYMMDD from title
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

    # 2. Process Market Topics (Latest Snapshot)
    topics_path = DATA_DIR / "signals" / "zizizaizai_topics.json"
    if topics_path.exists():
        try:
            with open(topics_path, "r", encoding="utf-8") as f:
                topics = json.load(f)
            
            grouped_topics = {}
            for topic in topics:
                concept_name = topic.get("name", "Unknown Topic")
                rows = topic.get("rows", [])
                
                stocks = []
                for row in rows:
                    stock_name = row.get("个股", "")
                    if stock_name:
                        stocks.append({"name": stock_name, "code": "", "symbol": ""})
                
                if stocks:
                    grouped_topics[concept_name] = stocks
            
            # Convert grouped topics to array format
            for concept, stocks in grouped_topics.items():
                result["sources"]["market_topics"].append({
                    "concept": concept,
                    "is_new": False,
                    "core_stocks": stocks, # Treat all as core for topics
                    "other_stocks": []
                })
        except Exception as e:
            logger.error(f"Error reading topics: {e}")

    return result
