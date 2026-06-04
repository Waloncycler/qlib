# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import pandas as pd
import requests

from .base import (
    BaseSourceAdapter,
    clean_symbol,
    to_qlib_symbol,
    UA,
)

logger = logging.getLogger("CN_Stock_Adapters_Filings")


class CninfoAnnouncementsAdapter(BaseSourceAdapter):
    """Adapter for cninfo (巨潮资讯) regulatory announcements search."""

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

    def fetch_announcements(self, symbol: str, page_size: int = 30) -> pd.DataFrame:
        code = clean_symbol(symbol)
        url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
        # Determine orgId (required in 2026 version of cninfo API)
        if code.startswith("6"):
            org_id = f"gssh0{code}"
        elif code.startswith(("8", "4")):
            org_id = f"gsbj0{code}"
        else:
            org_id = f"gssz0{code}"
            
        payload = {
            "stock": f"{code},{org_id}",
            "tabName": "fulltext",
            "pageSize": str(page_size),
            "pageNum": "1",
            "column": "",
            "category": "",
            "plate": "",
            "seDate": "",
            "searchkey": "",
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }
        headers = {
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://www.cninfo.com.cn/new/disclosure",
            "Origin": "https://www.cninfo.com.cn",
        }
        try:
            r = requests.post(url, data=payload, headers=headers, timeout=15)
            d = r.json()
            announcements = d.get("announcements") or []
            rows = []
            for item in announcements:
                ann_id = item.get("announcementId")
                rows.append({
                    "date": item.get("announcementTime", ""),
                    "title": item.get("announcementTitle", ""),
                    "type": item.get("announcementTypeName", ""),
                    "url": f"https://www.cninfo.com.cn/new/disclosure/detail?annoId={ann_id}" if ann_id else "",
                    "symbol": to_qlib_symbol(symbol),
                })
            if rows:
                df = pd.DataFrame(rows)
                df["date"] = pd.to_datetime(df["date"])
                return df
        except Exception as e:
            logger.error(f"Cninfo query failed for {symbol}: {e}")
        return pd.DataFrame()
