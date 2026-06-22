import json
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

from api.core_config import DATA_DIR

router = APIRouter(prefix="/api/user/starred_stocks", tags=["UserPrefs"])

STARRED_FILE = DATA_DIR / "starred_stocks.json"

class ToggleRequest(BaseModel):
    symbol: str

def load_starred():
    if not STARRED_FILE.exists():
        return []
    try:
        with open(STARRED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_starred(data):
    # Ensure directory exists
    STARRED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STARRED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@router.get("")
def get_starred_stocks():
    return {"starred": load_starred()}

@router.post("/toggle")
def toggle_starred_stock(req: ToggleRequest):
    starred = load_starred()
    symbol = req.symbol
    if symbol in starred:
        starred.remove(symbol)
        action = "removed"
    else:
        starred.append(symbol)
        action = "added"
    
    save_starred(starred)
    return {"status": "success", "action": action, "symbol": symbol, "starred": starred}
