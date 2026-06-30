import akshare as ak
import pandas as pd
from datetime import datetime
from loguru import logger

# Module-level cache: populated once per process lifetime.
# ak.tool_trade_date_hist_sina() returns full historical + current-year dates,
# so a single fetch is sufficient for the entire day.
_trade_dates_cache: set | None = None


def _load_trade_dates() -> set:
    """Fetch and cache all A-share trading dates. Falls back to weekday check on failure."""
    global _trade_dates_cache
    if _trade_dates_cache is not None:
        return _trade_dates_cache

    try:
        from core.config import global_v8_lock
        with global_v8_lock:
            cal_df = ak.tool_trade_date_hist_sina()
        _trade_dates_cache = set(
            pd.to_datetime(cal_df['trade_date']).dt.strftime("%Y-%m-%d").tolist()
        )
        logger.debug(f"Trading calendar loaded: {len(_trade_dates_cache)} dates cached.")
    except Exception as e:
        logger.warning(f"Failed to fetch trading calendar: {e}. Using weekday fallback.")
        _trade_dates_cache = set()  # empty set signals fallback mode

    return _trade_dates_cache


def is_trading_day(date_str: str | None = None) -> bool:
    """
    Checks if a given date string (YYYY-MM-DD) is a trading day in A-shares.
    If no date is provided, uses today's date.
    """
    if date_str is None:
        date_str = datetime.today().strftime("%Y-%m-%d")

    dates = _load_trade_dates()
    if dates:
        return date_str in dates

    # Fallback: check if it's a weekday
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.weekday() < 5  # 0-4 is Mon-Fri


def is_trading_hours() -> bool:
    """Check if current time is within A-share trading session (09:15 - 15:30 on weekdays)."""
    now = datetime.now()
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    hour_min = now.hour * 100 + now.minute
    return 915 <= hour_min <= 1530


if __name__ == "__main__":
    today = datetime.today().strftime("%Y-%m-%d")
    print(f"Is today ({today}) a trading day? {is_trading_day()}")
