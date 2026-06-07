import logging
import pandas as pd
from market_data.adapters.base import BaseSourceAdapter, UA, resilient_request, clean_symbol, to_qlib_symbol

logger = logging.getLogger("CN_Stock_Adapters_Signals")

class EastmoneyFundFlowAdapter(BaseSourceAdapter):
    """Adapter for EastMoney push2 minute-level stock fund flow (盘中)."""

    def get_instrument_list(self) -> list:
        return []

    def fetch_symbol_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_minute_flow(self, symbol: str) -> pd.DataFrame:
        code = clean_symbol(symbol)
        prefix_num = 1 if code.startswith("6") else 0
        secid = f"{prefix_num}.{code}"
        url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
        params = {
            "secid": secid,
            "klt": 1,
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
        }
        headers = {
            "User-Agent": UA,
            "Referer": "https://quote.eastmoney.com/",
            "Origin": "https://quote.eastmoney.com",
        }
        try:
            r = resilient_request("get", url, params=params, headers=headers)
            d = r.json()
            klines = d.get("data", {}).get("klines", [])
            rows = []
            for line in klines:
                parts = line.split(",")
                if len(parts) >= 6:
                    rows.append({
                        "time": parts[0],
                        "main_net": float(parts[1]),
                        "small_net": float(parts[2]),
                        "mid_net": float(parts[3]),
                        "large_net": float(parts[4]),
                        "super_net": float(parts[5]),
                    })
            if rows:
                df = pd.DataFrame(rows)
                df["symbol"] = to_qlib_symbol(symbol)
                return df
        except Exception as e:
            logger.error(f"Eastmoney minute flow failed for {symbol}: {e}")
        return pd.DataFrame()
