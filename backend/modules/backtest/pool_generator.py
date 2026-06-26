import json
import glob
from loguru import logger
from core.config import DATA_DIR, WORKSPACE_DIR, resolver
from modules.market.adapters.base import to_qlib_symbol

def get_topic_universe():
    """
    Reads the historical topics and reports JSON files,
    and extracts all unique stock symbols that have ever been mentioned.
    This creates a focused "Topic Universe" for the Qlib model to train on,
    drastically reducing noise from the entire A-share market.
    Returns:
        (unique_symbols, min_date, max_date)
    """
    signals_dir = DATA_DIR / "signals"
    topics_file = signals_dir / "zizizaizai_topics.json"
    reports_file = signals_dir / "zizizaizai_reports.json"
    
    unique_symbols = set()
    dates = []
    
    # Parse Topics
    if topics_file.exists():
        try:
            with open(topics_file, 'r', encoding='utf-8') as f:
                topics_data = json.load(f)
                for item in topics_data:
                    # extract date if available
                    if "created_time" in item and item["created_time"]:
                        dates.append(item["created_time"].split(" ")[0])
                    elif "date" in item and item["date"]:
                        dates.append(item["date"].split(" ")[0])
        except Exception as e:
            logger.error(f"Failed to parse topics file: {e}")
            
    # Parse Reports (which is more structured)
    if reports_file.exists():
        try:
            with open(reports_file, 'r', encoding='utf-8') as f:
                reports_data = json.load(f)
                for item in reports_data:
                    if "created_time" in item and item["created_time"]:
                        dates.append(item["created_time"].split(" ")[0])
                    elif "date" in item and item["date"]:
                        dates.append(item["date"].split(" ")[0])
                        
                    if "stock_pool" in item and isinstance(item["stock_pool"], list):
                        for pool in item["stock_pool"]:
                            for stock in pool.get("core_stocks", []):
                                if "symbol" in stock and stock["symbol"]:
                                    unique_symbols.add(stock["symbol"])
                                elif "code" in stock and stock["code"]:
                                    # Very basic heuristic if code exists but no symbol
                                    code = str(stock["code"])
                                    prefix = "SH" if code.startswith("6") else "SZ"
                                    unique_symbols.add(f"{prefix}{code}")
                            
                            for stock in pool.get("other_stocks", []):
                                if "symbol" in stock and stock["symbol"]:
                                    unique_symbols.add(stock["symbol"])
                                elif "code" in stock and stock["code"]:
                                    code = str(stock["code"])
                                    prefix = "SH" if code.startswith("6") else "SZ"
                                    unique_symbols.add(f"{prefix}{code}")
        except Exception as e:
            logger.error(f"Failed to parse reports file: {e}")

    min_date = min(dates) if dates else "2024-01-01"
    max_date = max(dates) if dates else "2024-07-04"
    
    # Sort for deterministic output
    return list(sorted(unique_symbols)), min_date, max_date

def apply_curated_overrides(daily_pools: dict) -> dict:
    """
    Override daily pools with curated stock pools from stock_pools/ directory.

    For each date that has a curated pool file (stock_pool_{date}.json),
    the AI report pool is replaced entirely by the curated picks.
    This ensures today's trades match the manually curated Top Picks,
    while preserving all historical backtest data unchanged.

    Args:
        daily_pools: {date -> {symbol -> {weight_type, is_new, concept, name}}}

    Returns:
        The same dict, with applicable dates overridden.
    """
    stock_pools_dir = WORKSPACE_DIR / "data" / "cn_stock" / "stock_pools"
    if not stock_pools_dir.exists():
        return daily_pools

    pool_files = sorted(glob.glob(str(stock_pools_dir / "stock_pool_*.json")))
    for fpath in pool_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                pool_data = json.load(f)
            raw_date = pool_data.get("date", "")
            if not raw_date:
                continue
            date = raw_date.split(" ")[0]
            curated = {}
            for stock in pool_data.get("stocks", []):
                sym = to_qlib_symbol(stock.get("code", ""))
                if sym and not sym.startswith("BJ"):
                    curated[sym] = {
                        "weight_type": "core",
                        "is_new": False,
                        "concept": stock.get("theme", "Unknown"),
                        "name": stock.get("name", ""),
                    }
            if curated:
                daily_pools[date] = curated
                logger.info(f"Overrode pool for {date} with curated {len(curated)} stocks")
        except Exception as e:
            logger.error(f"Error parsing curated pool {fpath}: {e}")

    return daily_pools


if __name__ == "__main__":
    universe, min_d, max_d = get_topic_universe()
    if isinstance(universe, list):
        print(f"Extracted {len(universe)} symbols from {min_d} to {max_d}. Sample: {universe[:10]}")
