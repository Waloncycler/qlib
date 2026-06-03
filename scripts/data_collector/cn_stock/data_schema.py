import pandas as pd
from loguru import logger

MARKET_SENTIMENT_REQUIRED_COLS = {
    "date", "up_count", "down_count", "flat_count", "suspended_count",
    "limit_up_count", "real_limit_up_count", "st_limit_up_count",
    "limit_down_count", "real_limit_down_count", "st_limit_down_count",
    "sentiment_score", "up_down_ratio",
    "broken_limit_up_count", "broken_limit_up_rate",
    "highest_consecutive_limit_up", "consecutive_limit_up_2_count",
    "consecutive_limit_up_3_plus_count", "yesterday_limit_up_avg_return"
}

def validate_market_sentiment(df: pd.DataFrame) -> bool:
    """
    Validates that the market sentiment DataFrame contains all required core columns.
    Returns True if valid, False otherwise.
    """
    missing = MARKET_SENTIMENT_REQUIRED_COLS - set(df.columns)
    if missing:
        logger.warning(f"Market Sentiment Schema Validation Failed! Missing columns: {missing}")
        return False
    return True

def validate_klines(data: list) -> bool:
    """
    Validates that kline data is a list of dictionaries with required fields.
    """
    if not isinstance(data, list):
        logger.warning("KLine Schema Validation Failed: Data is not a list")
        return False
        
    if len(data) > 0:
        first = data[0]
        required = {"trade_date", "open", "close", "high", "low", "volume"}
        missing = required - set(first.keys())
        if missing:
            logger.warning(f"KLine Schema Validation Failed: Missing fields {missing}")
            return False
            
    return True
