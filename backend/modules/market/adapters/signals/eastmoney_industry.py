import logging
import pandas as pd
from modules.market.adapters.base import BaseSourceAdapter, UA, resilient_request

logger = logging.getLogger("CN_Stock_Adapters_Signals")

class EastmoneyIndustryAdapter(BaseSourceAdapter):
    """Adapter for EastMoney sector board return rankings and flow leaders."""

    def get_instrument_list(self) -> list:
        return []

    def fetch_symbol_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def get_industry_board_rankings(self, top_n: int = 20) -> pd.DataFrame:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "100", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:90+t:2",
            "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
        }
        headers = {"User-Agent": UA}
        try:
            r = resilient_request("get", url, params=params, headers=headers)
            d = r.json()
            items = d.get("data", {}).get("diff", [])
            rows = []
            for i, item in enumerate(items):
                rows.append({
                    "rank": i + 1,
                    "name": item.get("f14", ""),
                    "change_pct": item.get("f3", 0.0),
                    "code": item.get("f12", ""),
                    "up_count": item.get("f104", 0),
                    "down_count": item.get("f105", 0),
                    "leader": item.get("f140", ""),
                    "leader_change_pct": item.get("f136", 0.0),
                })
            if rows:
                df = pd.DataFrame(rows)
                return df.head(top_n)
        except Exception as e:
            logger.error(f"Eastmoney industry boards ranking query failed: {e}")
        return pd.DataFrame()
