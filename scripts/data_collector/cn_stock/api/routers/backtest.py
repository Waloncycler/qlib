from fastapi import APIRouter, HTTPException
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
