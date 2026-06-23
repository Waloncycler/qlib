from fastapi import APIRouter, HTTPException
from loguru import logger
from modules.audit.service import generate_risk_audit

router = APIRouter()

@router.post("/api/stock/audit/{symbol}")
def ymos_risk_audit(symbol: str):
    """Generates a YMOS Risk Audit report using OpenAI API."""
    try:
        report = generate_risk_audit(symbol)
        return {"status": "success", "report": report}
    except Exception as e:
        logger.error(f"Error generating audit for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
