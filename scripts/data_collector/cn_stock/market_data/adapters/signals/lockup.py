import logging
import pandas as pd
from datetime import datetime, timedelta
from market_data.adapters.base import BaseSourceAdapter, clean_symbol, eastmoney_datacenter

logger = logging.getLogger("CN_Stock_Adapters_Signals")

class LockupAdapter(BaseSourceAdapter):
    """Adapter for Lockup Release calendars (restricted stock unlock)."""

    def get_instrument_list(self) -> list:
        return []

    def fetch_symbol_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def get_lockup_expiry(self, symbol: str, trade_date: str, forward_days: int = 90) -> dict:
        code = clean_symbol(symbol)
        history_data = eastmoney_datacenter(
            "RPT_LIFT_STAGE",
            filter_str=f"(SECURITY_CODE=\"{code}\")",
            page_size=15,
            sort_columns="FREE_DATE",
            sort_types="-1",
        )
        history = []
        for row in history_data:
            history.append({
                "date": str(row.get("FREE_DATE", ""))[:10],
                "type": row.get("LIMITED_STOCK_TYPE", ""),
                "shares": row.get("FREE_SHARES_NUM", 0),
                "ratio": row.get("FREE_RATIO", 0.0),
            })

        end_date = datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)
        end_str = end_date.strftime("%Y-%m-%d")
        upcoming_data = eastmoney_datacenter(
            "RPT_LIFT_STAGE",
            filter_str=f"(SECURITY_CODE=\"{code}\")(FREE_DATE>='{trade_date}')(FREE_DATE<='{end_str}')",
            page_size=20,
            sort_columns="FREE_DATE",
            sort_types="1",
        )
        upcoming = []
        for row in upcoming_data:
            upcoming.append({
                "date": str(row.get("FREE_DATE", ""))[:10],
                "type": row.get("LIMITED_STOCK_TYPE", ""),
                "shares": row.get("FREE_SHARES_NUM", 0),
                "ratio": row.get("FREE_RATIO", 0.0),
            })

        return {"history": history, "upcoming": upcoming}
