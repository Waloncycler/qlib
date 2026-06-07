import logging
from pathlib import Path
import pandas as pd
from datetime import date as datetime_date
from market_data.adapters.base import BaseSourceAdapter, UA, resilient_request

logger = logging.getLogger("CN_Stock_Adapters_Signals")

class ThsNorthboundAdapter(BaseSourceAdapter):
    """Adapter for THS Northbound minutes and local history cache."""

    def get_instrument_list(self) -> list:
        return []

    def fetch_symbol_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_realtime_minute_flow(self) -> pd.DataFrame:
        url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
        headers = {
            "User-Agent": UA,
            "Host": "data.hexin.cn",
            "Referer": "https://data.hexin.cn/",
        }
        try:
            r = resilient_request("get", url, headers=headers)
            d = r.json()
            times = d.get("time", [])
            hgt = d.get("hgt", [])
            sgt = d.get("sgt", [])
            n = len(times)
            df = pd.DataFrame({
                "time": times,
                "hgt_yi": hgt[:n] + [None] * (n - len(hgt)),
                "sgt_yi": sgt[:n] + [None] * (n - len(sgt)),
            })
            return df
        except Exception as e:
            logger.error(f"THS Northbound flow failed: {e}")
        return pd.DataFrame()

    def get_cache_path(self) -> Path:
        p = Path.home() / ".tradingagents" / "cache" / "northbound_daily.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def cache_today_flow(self, query_date: str = None) -> bool:
        df = self.fetch_realtime_minute_flow()
        if df.empty:
            return False
        df_valid = df.dropna()
        if df_valid.empty:
            return False
            
        if query_date is None:
            query_date = datetime_date.today().strftime("%Y-%m-%d")
            
        last = df_valid.iloc[-1]
        path = self.get_cache_path()
        rows = {}
        if path.exists():
            try:
                for line in path.read_text(encoding="utf-8").strip().split("\n")[1:]:
                    parts = line.split(",")
                    if len(parts) == 3:
                        rows[parts[0]] = line
            except Exception as e:
                logger.warning(f"Failed to read northbound cache: {e}")
                
        rows[query_date] = f"{query_date},{last['hgt_yi']},{last['sgt_yi']}"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("date,hgt_yi,sgt_yi\n")
                for d in sorted(rows.keys()):
                    f.write(rows[d] + "\n")
            return True
        except Exception as e:
            logger.error(f"Failed to write northbound cache: {e}")
        return False

    def load_cached_history(self, n: int = 30) -> pd.DataFrame:
        path = self.get_cache_path()
        if not path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_csv(path)
            df["date"] = pd.to_datetime(df["date"])
            return df.tail(n)
        except Exception as e:
            logger.error(f"Failed to load northbound cache: {e}")
        return pd.DataFrame()
