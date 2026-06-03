# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import os
import json
import re
import time
import secrets
from pathlib import Path
from typing import Optional
import pandas as pd
import requests

from adapters.base import (
    BaseSourceAdapter,
    clean_symbol,
    to_qlib_symbol,
    UA,
)

logger = logging.getLogger("CN_Stock_Adapters_Research")

REPORT_API = "https://reportapi.eastmoney.com/report/list"
PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"


class EastmoneyReportAdapter(BaseSourceAdapter):
    """Adapter for EastMoney Research Reports list and PDF downloads."""

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

    def fetch_report_list(self, symbol: str, max_pages: int = 3) -> pd.DataFrame:
        code = clean_symbol(symbol)
        session = requests.Session()
        session.headers.update({"User-Agent": UA, "Referer": "https://data.eastmoney.com/"})
        all_records = []
        for page in range(1, max_pages + 1):
            params = {
                "industryCode": "*", "pageSize": "100", "industry": "*",
                "rating": "*", "ratingChange": "*",
                "beginTime": "2000-01-01", "endTime": "2030-01-01",
                "pageNo": str(page), "fields": "", "qType": "0",
                "orgCode": "", "code": code, "rcode": "",
                "p": str(page), "pageNum": str(page), "pageNumber": str(page),
            }
            try:
                r = session.get(REPORT_API, params=params, timeout=30)
                d = r.json()
                rows = d.get("data") or []
                if not rows:
                    break
                all_records.extend(rows)
                if page >= (d.get("TotalPage", 1) or 1):
                    break
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"Failed to fetch reports for {symbol} on page {page}: {e}")
                break
                
        if all_records:
            df = pd.DataFrame(all_records)
            df["symbol"] = to_qlib_symbol(symbol)
            return df
        return pd.DataFrame()

    def download_report_pdf(self, record: dict, target_dir: str = "./reports") -> Optional[str]:
        info_code = record.get("infoCode")
        if not info_code:
            return None
        date_str = (record.get("publishDate") or "")[:10]
        org = record.get("orgSName") or "Unknown"
        title = re.sub(r'[\\/:*?"<>|]', "_", record.get("title", ""))[:80]
        fname = f"{date_str}_{org}_{title}.pdf"
        target = Path(target_dir) / fname
        if target.exists():
            return str(target)
            
        url = PDF_TPL.format(info_code=info_code)
        try:
            r = requests.get(url, headers={"User-Agent": UA, "Referer": "https://data.eastmoney.com/"}, timeout=60)
            if r.status_code == 200 and len(r.content) >= 1024:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(r.content)
                return str(target)
        except Exception as e:
            logger.error(f"Failed to download report PDF from {url}: {e}")
        return None


class ThsConsensusAdapter(BaseSourceAdapter):
    """Adapter for THS Consensus earnings forecasts (机构一致预期 EPS)."""

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

    def fetch_consensus(self, symbol: str) -> pd.DataFrame:
        code = clean_symbol(symbol)
        url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
        headers = {
            "User-Agent": UA,
            "Referer": "https://basic.10jqka.com.cn/",
        }
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.encoding = "gbk"
            dfs = pd.read_html(r.text)
            for df in dfs:
                cols = [str(c) for c in df.columns]
                if any("每股收益" in c or "均值" in c for c in cols):
                    df["symbol"] = to_qlib_symbol(symbol)
                    return df
            if dfs:
                df = dfs[0]
                df["symbol"] = to_qlib_symbol(symbol)
                return df
        except Exception as e:
            logger.error(f"THS consensus forecast failed for {symbol}: {e}")
        return pd.DataFrame()


class IwencaiAdapter(BaseSourceAdapter):
    """Adapter for iwencai NL Semantic Research Search."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.api_key = config.get("iwencai_api_key") or os.environ.get("IWENCAI_API_KEY", "")
        self.base_url = config.get("iwencai_base_url") or os.environ.get("IWENCAI_BASE_URL", "https://openapi.iwencai.com")

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

    def _claw_headers(self, skill_id: str = "report-search") -> dict:
        return {
            "X-Claw-Call-Type": "normal",
            "X-Claw-Skill-Id": skill_id,
            "X-Claw-Skill-Version": "2.0.0",
            "X-Claw-Plugin-Id": "none",
            "X-Claw-Plugin-Version": "none",
            "X-Claw-Trace-Id": secrets.token_hex(32),
        }

    def semantic_search(self, query: str, channel: str = "report", size: int = 50) -> list:
        """Search iwencai with natural language. channel: report / announcement / news"""
        if not self.api_key:
            logger.warning("iwencai API Key is not configured. Search will return empty.")
            return []
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self._claw_headers(),
        }
        payload = {
            "channels": [channel],
            "app_id": "AIME_SKILL",
            "query": query,
            "size": size,
        }
        try:
            from adapters.base import resilient_request
            r = resilient_request("post", f"{self.base_url}/v1/comprehensive/search", json=payload, headers=headers, timeout=30, max_retries=3)
            if r.status_code == 200:
                data = r.json()
                if data.get("status_code") == 0:
                    articles = data.get("data") or []
                    # Deduplicate articles by unique ID or title/date
                    best = {}
                    for a in articles:
                        uid = a.get("uid") or f"{a.get('title')}|{a.get('publish_date')}"
                        score = float(a.get("score") or 0.0)
                        if uid not in best or score > float(best[uid].get("score" or 0.0)):
                            best[uid] = a
                    return sorted(best.values(), key=lambda x: x.get("publish_date", ""), reverse=True)
                else:
                    logger.error(f"iwencai search error status: {data.get('status_msg')}")
        except Exception as e:
            logger.error(f"iwencai semantic search failed for query '{query}': {e}")
        return []

    def query2data(self, query: str, page: int = 1, limit: int = 50) -> list:
        """Fetch structured data columns from iwencai queries."""
        if not self.api_key:
            return []
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self._claw_headers(skill_id="data-query"),
        }
        payload = {
            "query": query,
            "page": str(page),
            "limit": str(limit),
            "is_cache": "1",
            "expand_index": "true",
        }
        try:
            from adapters.base import resilient_request
            r = resilient_request("post", f"{self.base_url}/v1/query2data", json=payload, headers=headers, timeout=30, max_retries=3)
            if r.status_code == 200:
                data = r.json()
                if data.get("status_code") == 0:
                    return data.get("datas") or []
        except Exception as e:
            logger.error(f"iwencai query2data failed for '{query}': {e}")
        return []

    def fetch_iwencai(self, query: str) -> pd.DataFrame:
        """Helper to fetch iwencai search results and return as DataFrame."""
        res = self.semantic_search(query)
        if not res:
            res = self.query2data(query)
        if res:
            return pd.DataFrame(res)
        return pd.DataFrame()

