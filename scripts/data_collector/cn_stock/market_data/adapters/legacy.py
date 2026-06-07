#  Copyright (c) Microsoft Corporation.
#  Licensed under the MIT License.

import datetime
import json
import logging
from typing import List, Optional
import requests
import pandas as pd

from .base import (
    BaseSourceAdapter,
    clean_symbol,
    to_qlib_symbol,
    to_ts_code,
)

logger = logging.getLogger(__name__)


class ZizizaizaiAdapter(BaseSourceAdapter):
    """Adapter for ZIZIZAIZAI API (email login, Bearer token, timing sentiment, uplimit hot list)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.email = config.get("zizi_email", "waloncycler@163.com")
        self.password = config.get("zizi_password", "")
        # The user provided token is an SDK key
        self.token = config.get("zzshare_token", "08afc8f2a1ef2ee3cba15c85bad7f3ced2f120005f3d4bed9efc2d65d9fc5d7d")
        self.base_url = "https://api.zizizaizai.com"
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime.datetime] = None

    def _login(self):
        """Perform email login to retrieve Bearer Token."""
        if not self.password:
            return
        
        # URL as provided by user
        url = f"{self.base_url}/v2/login/email/login"
        payload = {"email": self.email, "password": self.password}
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Referer": "https://quant.zizizaizai.com/login",
            "Origin": "https://quant.zizizaizai.com"
        }
        
        logger.info(f"Logging in to ZIZIZAIZAI for {self.email}...")
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code == 400:
                data = res.json()
                if data.get("code") == 40004:
                    logger.error("ZIZIZAIZAI login failed: Password incorrect. Please verify credentials in secret.yaml.")
                    return
            res.raise_for_status()
            data = res.json()
            # The API returns token in data.access_token or data.token
            token = data.get("data", {}).get("access_token") or data.get("data", {}).get("token") or data.get("token")
            if not token:
                logger.error(f"No token found in ZIZIZAIZAI login response: {data}")
                return
            self._token = token
            # Default token expiry 1800s
            self._token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=1800)
            logger.info("Successfully logged in to ZIZIZAIZAI via email.")
        except Exception as e:
            logger.error(f"ZIZIZAIZAI login failed: {e}")

    def get_headers(self) -> dict:
        """Get headers, prioritizing SDK key then falling back to Bearer token from login."""
        # Preference 1: SDK Key (token from secret.yaml)
        if self.token:
            return {
                "sdk-key": self.token,
                "Referer": "https://quant.zizizaizai.com/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            }
        
        # Preference 2: Bearer Token from login
        if not self._token or (self._token_expiry and datetime.datetime.now() >= self._token_expiry):
            self._login()
        
        headers = {
            "Referer": "https://quant.zizizaizai.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def get_instrument_list(self) -> List[str]:
        headers = self.get_headers()
        url = f"{self.base_url}/v3/open/review/uplimit/hot"
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        params = {"date1": yesterday, "limit": 100}
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                items = data.get("data", {}).get("list", []) or data.get("list", []) or data.get("data", [])
                symbols = []
                for item in items:
                    code = item.get("symbol") or item.get("code")
                    if code:
                        symbols.append(to_qlib_symbol(code))
                if symbols:
                    return symbols
        except Exception as e:
            logger.warning(f"Failed to fetch hot stock list from ZIZIZAIZAI: {e}")
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        code = clean_symbol(symbol)
        headers = self.get_headers()
        url = f"{self.base_url}/v3/open/review/uplimit/hot"

        all_records = []
        date_range = pd.date_range(start_datetime, end_datetime, freq="B")
        for dt in date_range:
            date_str = dt.strftime("%Y-%m-%d")
            params = {"date1": date_str, "limit": 100}
            try:
                res = requests.get(url, headers=headers, params=params, timeout=10)
                if res.status_code == 401:
                    headers = self.get_headers()
                    res = requests.get(url, headers=headers, params=params, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    items = data.get("data", {}).get("list", []) or data.get("list", []) or data.get("data", [])
                    for item in items:
                        item_code = item.get("symbol") or item.get("code")
                        if item_code and clean_symbol(item_code) == code:
                            all_records.append({
                                "date": dt,
                                "up_limit_count": float(item.get("up_limit_count", 0)),
                                "market_c": float(item.get("market_c", 0)),
                                "symbol": to_qlib_symbol(symbol),
                            })
                            break
            except Exception as e:
                logger.error(f"ZIZIZAIZAI failed to fetch for {symbol} on {date_str}: {e}")

        if all_records:
            df = pd.DataFrame(all_records)
            df["open"] = df["up_limit_count"]
            df["high"] = df["up_limit_count"]
            df["low"] = df["up_limit_count"]
            df["close"] = df["up_limit_count"]
            df["volume"] = df["market_c"]
            df["factor"] = 1.0
            return df
        return pd.DataFrame()

    def fetch_timing_sentiment(self, start_date: str, end_date: str) -> pd.DataFrame:
        headers = self.get_headers()
        url = f"{self.base_url}/v3/sentiment/timing"
        params = {"date1": start_date, "date2": end_date}
        try:
            res = requests.get(url, headers=headers, params=params, timeout=30)
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == 20000 or data.get("code") == 200:
                    items = data.get("data", [])
                    if items:
                        df = pd.DataFrame(items)
                        if "date" in df.columns:
                            df["date"] = pd.to_datetime(df["date"])
                        elif "date1" in df.columns:
                            df["date"] = pd.to_datetime(df["date1"])
                        return df
                else:
                    logger.error(f"ZIZIZAIZAI timing API error: {data.get('msg') or data.get('message')}")
        except Exception as e:
            logger.error(f"Failed to fetch timing sentiment from ZIZIZAIZAI: {e}")
        return pd.DataFrame()


class ZzshareAdapter(BaseSourceAdapter):
    """Adapter for ZZSHARE SDK (zzshare.client.DataApi)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.token = config.get("zzshare_token", "08afc8f2a1ef2ee3cba15c85bad7f3ced2f120005f3d4bed9efc2d65d9fc5d7d")
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            import zzshare
            from zzshare.client import DataApi
            self.client = DataApi(token=self.token)
        except Exception as e:
            logger.warning(f"Failed to load ZZSHARE SDK: {e}. SDK calls will fail.")

    def get_instrument_list(self) -> List[str]:
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        if not self.client:
            logger.error("ZZSHARE client is not initialized.")
            return pd.DataFrame()
        ts_code = to_ts_code(symbol)
        try:
            df = self.client.daily(
                ts_code=ts_code,
                date1=start_datetime.strftime("%Y-%m-%d"),
                date2=end_datetime.strftime("%Y-%m-%d"),
            )
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "trade_date": "date",
                    "vol": "volume",
                })
                df["factor"] = 1.0
                df["symbol"] = to_qlib_symbol(symbol)
                df["date"] = pd.to_datetime(df["date"])
                return df[["date", "open", "high", "low", "close", "volume", "factor", "symbol"]]
        except Exception as e:
            logger.error(f"ZZSHARE failed to fetch {symbol}: {e}")
        return pd.DataFrame()

    def fetch_sentiment_trend(self) -> pd.DataFrame:
        if not self.client:
            return pd.DataFrame()
        try:
            # Note: SDK sentiment_trend expects model param
            df = self.client.sentiment_trend(model='base')
            if df is not None:
                df["date"] = pd.to_datetime(df["date"])
                return df
        except Exception as e:
            logger.error(f"ZZSHARE failed to fetch sentiment trend: {e}")
        return pd.DataFrame()
