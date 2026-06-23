import akshare as ak
import pandas as pd
from datetime import datetime

def is_trading_day(date_str: str = None) -> bool:
    """
    Checks if a given date string (YYYY-MM-DD) is a trading day in A-shares.
    If no date is provided, uses today's date.
    """
    if date_str is None:
        date_str = datetime.today().strftime("%Y-%m-%d")
        
    try:
        # Load trade dates for current year from AKShare
        year = date_str[:4]
        # trade_cal = ak.tool_trade_date_hist_sina()  # Historical and future dates from Sina
        # Using a reliable akshare source for trade calendar
        cal_df = ak.tool_trade_date_hist_sina()
        trade_dates = pd.to_datetime(cal_df['trade_date']).dt.strftime("%Y-%m-%d").tolist()
        return date_str in trade_dates
    except Exception as e:
        print(f"Warning: Failed to fetch trading calendar: {e}")
        # Fallback: check if it's a weekday
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.weekday() < 5  # 0-4 is Mon-Fri

if __name__ == "__main__":
    today = datetime.today().strftime("%Y-%m-%d")
    print(f"Is today ({today}) a trading day? {is_trading_day()}")
