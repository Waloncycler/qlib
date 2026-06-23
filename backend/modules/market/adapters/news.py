# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import re
import json
import uuid
from datetime import datetime
import pandas as pd
import requests

from .base import (
    BaseSourceAdapter,
    to_qlib_symbol,
    UA,
    resilient_request,
)

logger = logging.getLogger("CN_Stock_Adapters_News")


class EastmoneyStockNewsAdapter(BaseSourceAdapter):
    """Adapter for EastMoney individual stock news (crawling search-api-web)."""

    def get_instrument_list(self) -> list:
        return []

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_stock_news(self, symbol: str, page_size: int = 30) -> pd.DataFrame:
        from .base import clean_symbol
        code = clean_symbol(symbol)
        cb = "jQuery_news"
        url = "https://search-api-web.eastmoney.com/search/jsonp"
        inner_params = json.dumps({
            "uid": "",
            "keyword": code,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": page_size,
                    "preTag": "",
                    "postTag": "",
                }
            },
        }, separators=(',', ':'))
        
        params = {"cb": cb, "param": inner_params}
        headers = {"User-Agent": UA, "Referer": "https://so.eastmoney.com/"}
        try:
            r = resilient_request("get", url, params=params, headers=headers)
            text = r.text
            # Extract JSON string out of jQuery callback function wrappers
            json_str = text[text.index("(") + 1 : text.rindex(")")]
            d = json.loads(json_str)
            articles = d.get("result", {}).get("cmsArticleWebOld", [])
            
            rows = []
            for a in articles:
                rows.append({
                    "date": a.get("date", ""),
                    "title": re.sub(r'<[^>]+>', '', a.get("title", "")),
                    "summary": re.sub(r'<[^>]+>', '', a.get("content", ""))[:250],
                    "source": a.get("mediaName", ""),
                    "url": a.get("url", ""),
                    "symbol": to_qlib_symbol(symbol),
                })
            if rows:
                df = pd.DataFrame(rows)
                df["date"] = pd.to_datetime(df["date"])
                return df
        except Exception as e:
            logger.error(f"Failed to fetch stock news for {symbol}: {e}")
        return pd.DataFrame()


class ClsTelegraphAdapter(BaseSourceAdapter):
    """Adapter for Cailian Press (财联社) Telegraph flash news stream."""

    def get_instrument_list(self) -> list:
        return []

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_telegraph(self, page_size: int = 50) -> pd.DataFrame:
        url = "https://www.cls.cn/nodeapi/telegraphList"
        params = {"rn": str(page_size), "page": "1"}
        headers = {"User-Agent": UA, "Referer": "https://www.cls.cn/"}
        try:
            r = resilient_request("get", url, params=params, headers=headers)
            d = r.json()
            items = d.get("data", {}).get("roll_data", [])
            rows = []
            for item in items:
                ctime = item.get("ctime")
                time_str = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S") if ctime else ""
                rows.append({
                    "date": time_str,
                    "title": item.get("title", "") or item.get("brief", ""),
                    "summary": item.get("content", "") or item.get("brief", ""),
                })
            if rows:
                df = pd.DataFrame(rows)
                df["date"] = pd.to_datetime(df["date"])
                return df
        except Exception as e:
            logger.error(f"Failed to fetch CLS telegraph: {e}")
        return pd.DataFrame()


class EastmoneyGlobalNewsAdapter(BaseSourceAdapter):
    """Adapter for EastMoney 7x24 global财经 fast news feed (NP Weblist)."""

    def get_instrument_list(self) -> list:
        return []

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def fetch_global_news(self, page_size: int = 50) -> pd.DataFrame:
        url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
        params = {
            "client": "web",
            "biz": "web_724",
            "fastColumn": "102",
            "sortEnd": "",
            "pageSize": str(page_size),
            "req_trace": str(uuid.uuid4()),  # Required field to avoid 403 status
        }
        headers = {"User-Agent": UA, "Referer": "https://kuaixun.eastmoney.com/"}
        try:
            r = resilient_request("get", url, params=params, headers=headers)
            d = r.json()
            items = d.get("data", {}).get("fastNewsList", [])
            rows = []
            for item in items:
                rows.append({
                    "date": item.get("showTime", ""),
                    "title": item.get("title", ""),
                    "summary": item.get("summary", "")[:250],
                })
            if rows:
                df = pd.DataFrame(rows)
                df["date"] = pd.to_datetime(df["date"])
                return df
        except Exception as e:
            logger.error(f"Failed to fetch global news: {e}")
        return pd.DataFrame()
