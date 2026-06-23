# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import pandas as pd
import requests

from .base import (
    BaseSourceAdapter,
    clean_symbol,
    eastmoney_datacenter,
    to_qlib_symbol,
    UA,
    resilient_request,
)

logger = logging.getLogger("CN_Stock_Adapters_Capital")


class MarginTradingAdapter(BaseSourceAdapter):
    """Adapter for Margin Trading (融资融券) details."""

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

    def get_margin_trading(self, symbol: str, page_size: int = 50) -> pd.DataFrame:
        code = clean_symbol(symbol)
        data = eastmoney_datacenter(
            "RPTA_WEB_RZRQ_GGMX",
            filter_str=f'(SCODE="{code}")',
            page_size=page_size,
            sort_columns="DATE",
            sort_types="-1",
        )
        rows = []
        for row in data:
            dt = row.get("DATE")
            if not dt or str(dt).lower() in ["none", "nan", ""]:
                continue
            rows.append({
                "date": str(dt)[:10],
                "rzye_yuan": row.get("RZYE", 0.0),       # 融资余额
                "rzmre_yuan": row.get("RZMRE", 0.0),     # 融资买入额
                "rzche_yuan": row.get("RZCHE", 0.0),     # 融资偿还额
                "rqye_yuan": row.get("RQYE", 0.0),       # 融券余额
                "rqmcl_shares": row.get("RQMCL", 0.0),   # 融券卖出量
                "rqchl_shares": row.get("RQCHL", 0.0),   # 融券偿还量
                "rzrqye_yuan": row.get("RZRQYE", 0.0),   # 融资融券余额合计
                "symbol": to_qlib_symbol(symbol),
            })
        if rows:
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            return df
        return pd.DataFrame()


class BlockTradeAdapter(BaseSourceAdapter):
    """Adapter for Block Trades (大宗交易)."""

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

    def get_block_trades(self, symbol: str, page_size: int = 50) -> pd.DataFrame:
        code = clean_symbol(symbol)
        data = eastmoney_datacenter(
            "RPT_DATA_BLOCKTRADE",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="TRADE_DATE",
            sort_types="-1",
        )
        rows = []
        for row in data:
            dt = row.get("TRADE_DATE")
            if not dt or str(dt).lower() in ["none", "nan", ""]:
                continue
            close = row.get("CLOSE_PRICE") or 0.0
            deal_price = row.get("DEAL_PRICE") or 0.0
            premium = ((deal_price / close - 1) * 100) if close else 0.0
            rows.append({
                "date": str(dt)[:10],
                "deal_price": deal_price,
                "close_price": close,
                "premium_pct": round(premium, 2),
                "volume_shares": row.get("DEAL_VOLUME", 0.0),
                "amount_yuan": row.get("DEAL_AMT", 0.0),
                "buyer_dept": row.get("BUYER_NAME", ""),
                "seller_dept": row.get("SELLER_NAME", ""),
                "symbol": to_qlib_symbol(symbol),
            })
        if rows:
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            return df
        return pd.DataFrame()


class ShareholderAdapter(BaseSourceAdapter):
    """Adapter for Shareholders counts (股东户数)."""

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

    def get_shareholders(self, symbol: str, page_size: int = 15) -> pd.DataFrame:
        code = clean_symbol(symbol)
        data = eastmoney_datacenter(
            "RPT_HOLDERNUMLATEST",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="END_DATE",
            sort_types="-1",
        )
        rows = []
        for row in data:
            dt = row.get("END_DATE")
            if not dt or str(dt).lower() in ["none", "nan", ""]:
                continue
            rows.append({
                "date": str(dt)[:10],
                "holder_num": row.get("HOLDER_NUM", 0),
                "change_num": row.get("HOLDER_NUM_CHANGE", 0),
                "change_ratio_pct": row.get("HOLDER_NUM_RATIO", 0.0),
                "avg_free_shares": row.get("AVG_FREE_SHARES", 0.0),
                "symbol": to_qlib_symbol(symbol),
            })
        if rows:
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            return df
        return pd.DataFrame()


class DividendAdapter(BaseSourceAdapter):
    """Adapter for Dividend yields and plan status (分红送转)."""

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

    def get_dividends(self, symbol: str, page_size: int = 30) -> pd.DataFrame:
        code = clean_symbol(symbol)
        data = eastmoney_datacenter(
            "RPT_SHAREBONUS_DET",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="EX_DIVIDEND_DATE",
            sort_types="-1",
        )
        rows = []
        for row in data:
            dt = row.get("EX_DIVIDEND_DATE")
            if not dt or str(dt).lower() in ["none", "nan", ""]:
                continue
            rows.append({
                "date": str(dt)[:10],
                "bonus_rmb_pretax": row.get("PRETAX_BONUS_RMB", 0.0),  # Per share dividend (RMB)
                "transfer_ratio_per_10": row.get("TRANSFER_RATIO", 0.0),  # Per 10 share bonus
                "bonus_ratio_per_10": row.get("BONUS_RATIO", 0.0),
                "progress_status": row.get("ASSIGN_PROGRESS", ""),
                "symbol": to_qlib_symbol(symbol),
            })
        if rows:
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            return df
        return pd.DataFrame()


class StockFundFlow120dAdapter(BaseSourceAdapter):
    """Adapter for daily fund flows (个股资金流向 - 最近 120 日)."""

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

    def fetch_daily_flow(self, symbol: str, limit: int = 120) -> pd.DataFrame:
        code = clean_symbol(symbol).lower()
        if code.startswith("6"):
            sina_sym = f"sh{code}"
        elif code.startswith("8") or code.startswith("4"):
            sina_sym = f"bj{code}"
        else:
            sina_sym = f"sz{code}"

        url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs"
        params = {
            "page": 1,
            "num": limit,
            "sort": "opendate",
            "asc": 0,
            "daima": sina_sym
        }
        headers = {"User-Agent": UA}
        try:
            r = resilient_request("get", url, params=params, headers=headers)
            # Sina returns pure JSON array
            items = r.json()
            rows = []
            for item in items:
                rows.append({
                    "date": item.get("opendate"),
                    "main_net_flow": float(item.get("netamount", 0.0)),
                    "turnover": float(item.get("turnover", 0.0)),
                })
            if rows:
                df = pd.DataFrame(rows)
                df["symbol"] = to_qlib_symbol(symbol)
                df["date"] = pd.to_datetime(df["date"])
                # Sina returns descending by date, we might want ascending for charts
                df = df.sort_values("date").reset_index(drop=True)
                return df
        except Exception as e:
            logger.error(f"Daily fund flows failed for {symbol} via Sina: {e}")
        return pd.DataFrame()
