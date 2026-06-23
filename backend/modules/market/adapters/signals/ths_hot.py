import logging
import pandas as pd
from datetime import date as datetime_date
from modules.market.adapters.base import BaseSourceAdapter, UA, resilient_request, to_qlib_symbol

logger = logging.getLogger("CN_Stock_Adapters_Signals")

class ThsHotReasonAdapter(BaseSourceAdapter):
    """Adapter for TongHuShun daily strong stocks and theme attribution (题材归因)."""

    def get_instrument_list(self) -> list:
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def get_hot_reasons(self, query_date: str = None) -> pd.DataFrame:
        if query_date is None:
            query_date = datetime_date.today().strftime("%Y-%m-%d")

        url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{query_date}/orderby/date/orderway/desc/charset/GBK/"
        headers = {"User-Agent": UA}
        try:
            r = resilient_request("get", url, headers=headers)
            data = r.json()
            if data.get("errocode", 0) != 0:
                logger.warning(f"THS hot reasons error: {data.get('errormsg')}")
                return pd.DataFrame()

            rows = data.get("data") or []
            df = pd.DataFrame(rows)
            if not df.empty:
                rename_map = {
                    "name": "name", "code": "code", "reason": "reason_tags",
                    "close": "close", "zhangdie": "change_amt", "zhangfu": "change_pct",
                    "huanshou": "turnover_pct", "chengjiaoe": "amount",
                    "chengjiaoliang": "volume", "ddejingliang": "dde_net",
                    "market": "market",
                }
                df = df.rename(columns=rename_map)
                df["symbol"] = df["code"].apply(to_qlib_symbol)
                df["date"] = pd.to_datetime(query_date)
                return df
        except Exception as e:
            logger.error(f"THS hot reasons failed on {query_date}: {e}")
        return pd.DataFrame()
