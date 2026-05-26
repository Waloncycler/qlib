# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import pandas as pd
import requests

from adapters.base import (
    BaseSourceAdapter,
    clean_symbol,
    get_market_prefix,
    to_qlib_symbol,
    UA,
    get_mootdx_client,
)

logger = logging.getLogger("CN_Stock_Adapters_Fundamentals")


class MootdxFinanceAdapter(BaseSourceAdapter):
    """Adapter for Mootdx quarterly financial snapshots (37 fields)."""

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

    def get_financial_snapshot(self, symbol: str) -> pd.DataFrame:
        code = clean_symbol(symbol)
        try:
            client = get_mootdx_client("std")
            if not client:
                raise RuntimeError("Failed to get mootdx client")
            fin = client.finance(symbol=code)
            if fin is not None and not fin.empty:
                # Transpose if it returns index-based rows, or keep structure
                df = pd.DataFrame(fin)
                df["symbol"] = to_qlib_symbol(symbol)
                return df
        except Exception as e:
            logger.error(f"Mootdx finance snapshot failed for {symbol}: {e}")
        return pd.DataFrame()


class MootdxF10Adapter(BaseSourceAdapter):
    """Adapter for Mootdx F10 company profile textual information."""

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

    def get_company_f10(self, symbol: str, category_name: str = "公司概况") -> str:
        """Fetch F10 textual block. 
        Supported categories: 公司概况, 最新提示, 财务分析, 股东研究, 股本结构, 资本运作, 业内点评, 行业分析, 公司大事
        """
        code = clean_symbol(symbol)
        try:
            client = get_mootdx_client("std")
            if not client:
                raise RuntimeError("Failed to get mootdx client")
            text = client.F10(symbol=code, name=category_name)
            if text:
                # Optimize token limits by truncating excessive rows
                lines = text.split("\n")
                if len(lines) > 300:
                    lines = lines[:150] + ["\n... (Pruned for LLM Context) ...\n"] + lines[-50:]
                return "\n".join(lines)
        except Exception as e:
            logger.error(f"Mootdx F10 failed for {symbol} ({category_name}): {e}")
        return ""


class EastmoneyStockInfoAdapter(BaseSourceAdapter):
    """Adapter for EastMoney basic static stock statistics (industry, capitalization)."""

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

    def get_stock_info(self, symbol: str) -> dict:
        code = clean_symbol(symbol)
        prefix_num = 1 if code.startswith("6") else 0
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "fltt": "2",
            "invt": "2",
            "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
            "secid": f"{prefix_num}.{code}",
        }
        headers = {"User-Agent": UA}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            d = r.json().get("data", {})
            if d:
                return {
                    "code": d.get("f57", ""),
                    "name": d.get("f58", ""),
                    "industry": d.get("f127", ""),
                    "total_shares": d.get("f84", 0.0),     # total shares count
                    "float_shares": d.get("f85", 0.0),     # float shares count
                    "mcap_yuan": d.get("f116", 0.0),       # total cap (yuan)
                    "float_mcap_yuan": d.get("f117", 0.0), # float cap (yuan)
                    "list_date": str(d.get("f189", "")),   # list date YYYYMMDD
                    "price": d.get("f43", 0.0),
                    "symbol": to_qlib_symbol(symbol),
                }
        except Exception as e:
            logger.error(f"Eastmoney basic stock info failed for {symbol}: {e}")
        return {}


class SinaFinancialReportAdapter(BaseSourceAdapter):
    """Adapter for Sina Finance three financial statements (Asset-liability, Profit, and Cash-flow sheets)."""

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

    def fetch_statement(self, symbol: str, report_type: str = "lrb", num: int = 20) -> pd.DataFrame:
        """Fetch quarterly accounting statements from Sina.
        report_type: fzb (Asset-Liability), lrb (Profit), llb (Cash-flow)
        """
        code = clean_symbol(symbol)
        prefix = get_market_prefix(code)
        paper_code = f"{prefix}{code}"
        url = "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
        params = {
            "paperCode": paper_code,
            "source": report_type,
            "type": "0",
            "page": "1",
            "num": str(num),
        }
        headers = {"User-Agent": UA}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            d = r.json()
            data = d.get("result", {}).get("data", {})
            report_list = data.get("report_list", {})
            if isinstance(report_list, dict) and report_list:
                rows = []
                for report_date, v in report_list.items():
                    row = {
                        "date": report_date,
                        "publish_date": v.get("publish_date"),
                        "currency": v.get("rCurrency"),
                    }
                    items_list = v.get("data", [])
                    if isinstance(items_list, list):
                        for item in items_list:
                            field = item.get("item_field")
                            val = item.get("item_value")
                            if field:
                                row[field] = val
                    rows.append(row)
                df = pd.DataFrame(rows)
                df["symbol"] = to_qlib_symbol(symbol)
                return df
        except Exception as e:
            logger.error(f"Sina financial statement ({report_type}) failed for {symbol}: {e}")
        return pd.DataFrame()
