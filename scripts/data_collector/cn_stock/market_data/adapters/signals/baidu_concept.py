import logging
import pandas as pd
import requests
from market_data.adapters.base import BaseSourceAdapter, UA, clean_symbol

logger = logging.getLogger("CN_Stock_Adapters_Signals")

class BaiduConceptAdapter(BaseSourceAdapter):
    """Adapter for Baidu stock concepts, industry, and regional classifications."""

    def get_instrument_list(self) -> list:
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def get_concept_blocks(self, symbol: str) -> dict:
        code = clean_symbol(symbol)
        url = f"https://finance.pae.baidu.com/api/getrelatedblock?code={code}&market=ab&typeCode=all&finClientType=pc"
        headers = {
            "Host": "finance.pae.baidu.com",
            "User-Agent": UA,
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        }
        try:
            r = requests.get(url, headers=headers, timeout=10)
            d = r.json()
            if str(d.get("ResultCode", -1)) != "0":
                logger.warning(f"Baidu PAE concept blocks returned non-zero code for {symbol}")
                return {}

            result = {"industry": [], "concept": [], "region": [], "concept_tags": []}
            for block in d.get("Result", []):
                block_type = block.get("type", "")
                for item in block.get("list", []):
                    entry = {
                        "name": item.get("name", ""),
                        "change_pct": item.get("increase", ""),
                        "desc": item.get("desc", ""),
                    }
                    if "行业" in block_type:
                        result["industry"].append(entry)
                    elif "概念" in block_type:
                        result["concept"].append(entry)
                        result["concept_tags"].append(entry["name"])
                    elif "地域" in block_type:
                        result["region"].append(entry)
            return result
        except Exception as e:
            logger.error(f"Baidu concept blocks failed for {symbol}: {e}")
        return {}
