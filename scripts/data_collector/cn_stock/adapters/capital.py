# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import pandas as pd
import requests

from adapters.base import (
    BaseSourceAdapter,
    clean_symbol,
    eastmoney_datacenter,
    to_qlib_symbol,
    UA,
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
        code = clean_symbol(symbol)
        prefix_num = 1 if code.startswith("6") else 0
        url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
        params = {
            "secid": f"{prefix_num}.{code}",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "lmt": str(limit),
        }
        headers = {
            "User-Agent": UA,
            "Referer": "https://quote.eastmoney.com/",
            "Origin": "https://quote.eastmoney.com",
        }
        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            d = r.json()
            klines = d.get("data", {}).get("klines", [])
            rows = []
            for line in klines:
                parts = line.split(",")
                if len(parts) >= 7:
                    rows.append({
                        "date": parts[0],
                        "main_net": float(parts[1]) if parts[1] != "-" else 0.0,
                        "small_net": float(parts[2]) if parts[2] != "-" else 0.0,
                        "mid_net": float(parts[3]) if parts[3] != "-" else 0.0,
                        "large_net": float(parts[4]) if parts[4] != "-" else 0.0,
                        "super_net": float(parts[5]) if parts[5] != "-" else 0.0,
                    })
            if rows:
                df = pd.DataFrame(rows)
                df["symbol"] = to_qlib_symbol(symbol)
                df["date"] = pd.to_datetime(df["date"])
                return df
        except Exception as e:
            logger.error(f"Daily fund flows failed for {symbol}: {e}")
        return pd.DataFrame()
