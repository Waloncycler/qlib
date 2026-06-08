# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
import urllib.request
from typing import List, Optional
import pandas as pd
import requests

from .base import (
    BaseSourceAdapter,
    clean_symbol,
    get_market_prefix,
    to_qlib_symbol,
    to_tencent_symbol,
    UA,
    get_mootdx_client,
    resilient_request,
)

logger = logging.getLogger("CN_Stock_Adapters_Market")


class MootdxAdapter(BaseSourceAdapter):
    """Adapter for mootdx (TDX high-speed server connection)."""

    def get_instrument_list(self) -> List[str]:
        try:
            client = get_mootdx_client("std")
            if not client:
                raise RuntimeError("Failed to get mootdx client")
            stocks = client.stocks()
            if stocks is not None and not stocks.empty:
                return [to_qlib_symbol(code) for code in stocks.index.tolist()]
        except Exception as e:
            logger.warning(f"Failed to fetch stock list from mootdx: {e}. Using fallback.")
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        code = clean_symbol(symbol)
        try:
            client = get_mootdx_client("std")
            if not client:
                raise RuntimeError("Failed to get mootdx client")
            freq = 9 if interval == "1d" else 8
            df = client.k(symbol=code, begin=start_datetime.strftime("%Y-%m-%d"), end=end_datetime.strftime("%Y-%m-%d"))
            if df is not None and not df.empty:
                if "date" in df.columns:
                    df = df.reset_index(drop=True)
                elif df.index.name == "date" or "date" in df.index.names:
                    df = df.reset_index()
                elif "datetime" in df.columns:
                    df = df.reset_index(drop=True)
                    df = df.rename(columns={"datetime": "date"})
                elif df.index.name == "datetime" or "datetime" in df.index.names:
                    df = df.reset_index()
                    df = df.rename(columns={"datetime": "date"})
                else:
                    df = df.reset_index()

                if "datetime" in df.columns and "date" not in df.columns:
                    df = df.rename(columns={"datetime": "date"})

                if "volume" not in df.columns:
                    if "vol" in df.columns:
                        df = df.rename(columns={"vol": "volume"})

                df["factor"] = 1.0
                df["symbol"] = to_qlib_symbol(symbol)
                df["date"] = pd.to_datetime(df["date"])
                
                for col in ["open", "high", "low", "close", "volume"]:
                    if col not in df.columns:
                        df[col] = 0.0
                
                return df[["date", "open", "high", "low", "close", "volume", "factor", "symbol"]]
        except Exception as e:
            logger.error(f"mootdx failed to fetch {symbol}: {e}")
        return pd.DataFrame()


class AkshareAdapter(BaseSourceAdapter):
    """Adapter for akshare APIs."""

    def get_instrument_list(self) -> List[str]:
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                return [to_qlib_symbol(code) for code in df["代码"].tolist()]
        except Exception as e:
            logger.warning(f"Failed to fetch stock list from akshare: {e}. Using fallback.")
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        code = clean_symbol(symbol)
        try:
            import akshare as ak
            period = "daily" if interval == "1d" else "1"
            df = ak.stock_zh_a_hist(
                symbol=code,
                period=period,
                start_date=start_datetime.strftime("%Y%m%d"),
                end_date=end_datetime.strftime("%Y%m%d"),
                adjust="qfq",
            )
            if df is not None and not df.empty:
                df = df.rename(columns={
                    "日期": "date",
                    "开盘": "open",
                    "最高": "high",
                    "最低": "low",
                    "收盘": "close",
                    "成交量": "volume",
                })
                df["factor"] = 1.0
                df["symbol"] = to_qlib_symbol(symbol)
                df["date"] = pd.to_datetime(df["date"])
                return df[["date", "open", "high", "low", "close", "volume", "factor", "symbol"]]
        except Exception as e:
            logger.error(f"akshare failed to fetch {symbol}: {e}")
        return pd.DataFrame()


class TencentSinaAdapter(BaseSourceAdapter):
    """Adapter for Tencent quotes and Sina K-lines."""

    def get_instrument_list(self) -> List[str]:
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        tencent_code = to_tencent_symbol(symbol)
        url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {
            "symbol": tencent_code,
            "scale": 240 if interval == "1d" else 1,
            "ma": 5,
            "datalen": 2000,
        }
        try:
            res = resilient_request("get", url, params=params, headers={"User-Agent": UA})
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and data:
                    df = pd.DataFrame(data)
                    df = df.rename(columns={"day": "date"})
                    df["open"] = df["open"].astype(float)
                    df["high"] = df["high"].astype(float)
                    df["low"] = df["low"].astype(float)
                    df["close"] = df["close"].astype(float)
                    df["volume"] = df["volume"].astype(float)
                    df["factor"] = 1.0
                    df["symbol"] = to_qlib_symbol(symbol)
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    
                    # Append real-time data for today if missing
                    if interval == "1d" and not df.empty and df.iloc[-1]["date"].date() < pd.Timestamp.now().date():
                        quotes = self.fetch_tencent_quotes([symbol])
                        code_no_prefix = clean_symbol(symbol)
                        if code_no_prefix in quotes:
                            q = quotes[code_no_prefix]
                            if q["open"] > 0:
                                today = pd.Timestamp.now().normalize()
                                new_row = {
                                    "date": today,
                                    "open": q["open"],
                                    "high": q["high"],
                                    "low": q["low"],
                                    "close": q["price"],
                                    "volume": q["volume_lots"] * 100,
                                    "factor": 1.0,
                                    "symbol": to_qlib_symbol(symbol)
                                }
                                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

                    df["ma5"] = df["close"].rolling(5).mean()
                    df["ma20"] = df["close"].rolling(20).mean()
                    df = df[(df["date"] >= start_datetime) & (df["date"] <= end_datetime)]
                    return df[["date", "open", "high", "low", "close", "volume", "factor", "symbol", "ma5", "ma20"]]
        except Exception as e:
            logger.error(f"Sina KLine failed for {symbol}: {e}")
        return pd.DataFrame()

    def fetch_tencent_quotes(self, codes: list[str]) -> dict[str, dict]:
        """Fetch Tencent quotes covering PE, PB, and MCAPs."""
        prefixed = [to_tencent_symbol(c) for c in codes]
        url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0")
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read().decode("gbk")
            result = {}
            for line in data.strip().split(";"):
                if not line.strip() or "=" not in line or '"' not in line:
                    continue
                key = line.split("=")[0].split("_")[-1]
                vals = line.split('"')[1].split("~")
                if len(vals) < 53:
                    continue
                code = key[2:]
                result[code] = {
                    "name": vals[1],
                    "price": float(vals[3]) if vals[3] else 0.0,
                    "last_close": float(vals[4]) if vals[4] else 0.0,
                    "open": float(vals[5]) if vals[5] else 0.0,
                    "change_amt": float(vals[31]) if vals[31] else 0.0,
                    "change_pct": float(vals[32]) if vals[32] else 0.0,
                    "high": float(vals[33]) if vals[33] else 0.0,
                    "low": float(vals[34]) if vals[34] else 0.0,
                    "amount_wan": float(vals[37]) if vals[37] else 0.0,
                    "turnover_pct": float(vals[38]) if vals[38] else 0.0,
                    "pe_ttm": float(vals[39]) if vals[39] else 0.0,
                    "amplitude_pct": float(vals[43]) if vals[43] else 0.0,
                    "mcap_yi": float(vals[44]) if vals[44] else 0.0,
                    "float_mcap_yi": float(vals[45]) if vals[45] else 0.0,
                    "pb": float(vals[46]) if vals[46] else 0.0,
                    "limit_up": float(vals[47]) if vals[47] else 0.0,
                    "limit_down": float(vals[48]) if vals[48] else 0.0,
                    "vol_ratio": float(vals[49]) if vals[49] else 0.0,
                    "pe_static": float(vals[52]) if vals[52] else 0.0,
                    "volume_lots": float(vals[36]) if len(vals) > 36 and vals[36] else 0.0,
                }
            return result
        except Exception as e:
            logger.error(f"Failed to fetch Tencent quotes: {e}")
        return {}


class BaiduKlineAdapter(BaseSourceAdapter):
    """Adapter to fetch K-line data directly from Baidu, including moving averages (MA5/10/20)."""

    def get_instrument_list(self) -> List[str]:
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        code = clean_symbol(symbol)
        url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
        params = {
            "all": "1",
            "isIndex": "false",
            "isBk": "false",
            "isBlock": "false",
            "isFutures": "false",
            "isStock": "true",
            "newFormat": "1",
            "group": "quotation_kline_ab",
            "finClientType": "pc",
            "code": code,
            "ktype": "1",  # Daily K-line
        }
        headers = {
            "User-Agent": UA,
            "Accept": "application/vnd.finance-web.v1+json",
            "Origin": "https://gushitong.baidu.com",
            "Referer": "https://gushitong.baidu.com/",
        }
        try:
            r = resilient_request("get", url, params=params, headers=headers)
            d = r.json()
            result = d.get("Result", {})
            if isinstance(result, list):
                if not result:
                    return pd.DataFrame()
                result = result[0]
            md = result.get("newMarketData", {}) if isinstance(result, dict) else {}
            keys = md.get("keys", [])
            rows_str = md.get("marketData", "").split(";")
            
            rows = []
            for row in rows_str:
                if not row:
                    continue
                parts = row.split(",")
                if len(parts) < len(keys):
                    continue
                row_dict = dict(zip(keys, parts))
                rows.append(row_dict)
                
            if rows:
                df = pd.DataFrame(rows)
                df = df.rename(columns={
                    "time": "date",
                    "volume": "volume",
                })
                df["date"] = pd.to_datetime(df["date"])
                df["open"] = pd.to_numeric(df["open"], errors="coerce")
                df["high"] = pd.to_numeric(df["high"], errors="coerce")
                df["low"] = pd.to_numeric(df["low"], errors="coerce")
                df["close"] = pd.to_numeric(df["close"], errors="coerce")
                df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
                df["factor"] = 1.0
                df["symbol"] = to_qlib_symbol(symbol)
                
                # Check for moving averages
                for col in ["ma5avgprice", "ma10avgprice", "ma20avgprice"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                        
                df = df[(df["date"] >= start_datetime) & (df["date"] <= end_datetime)]
                return df
        except Exception as e:
            logger.error(f"Baidu KLine failed for {symbol}: {e}")
        return pd.DataFrame()


class EastmoneyAdapter(BaseSourceAdapter):
    """Adapter for EastMoney push client real-time snapshot list API."""

    def get_instrument_list(self) -> List[str]:
        # Query snapshot of all stocks to get active instruments
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1,
            "pz": 5000,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:0+t:6,m:1+t:2",
            "fields": "f12",
        }
        try:
            res = resilient_request("get", url, params=params)
            if res.status_code == 200:
                data = res.json()
                diff = data.get("data", {}).get("diff", [])
                symbols = [to_qlib_symbol(item["f12"]) for item in diff if "f12" in item]
                if symbols:
                    return symbols
        except Exception as e:
            logger.warning(f"Failed to fetch stock list from EastMoney: {e}")
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        """Fetches the latest real-time snapshot for this stock and outputs as a single-row DataFrame."""
        code = clean_symbol(symbol)
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1,
            "pz": 5000,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": "m:0+t:6,m:1+t:2",
            "fields": "f2,f3,f6,f8,f12,f14,f22",
        }
        try:
            res = resilient_request("get", url, params=params)
            if res.status_code == 200:
                data = res.json()
                diff = data.get("data", {}).get("diff", [])
                for item in diff:
                    if item.get("f12") == code:
                        # Map snapshot fields
                        df = pd.DataFrame([{
                            "date": pd.Timestamp.now().normalize(),
                            "open": float(item.get("f2", 0)),  # Using price as open/high/low/close since it's a snapshot
                            "high": float(item.get("f2", 0)),
                            "low": float(item.get("f2", 0)),
                            "close": float(item.get("f2", 0)),
                            "volume": float(item.get("f6", 0)),  # 成交额
                            "change": float(item.get("f3", 0)),  # 涨幅
                            "turnover": float(item.get("f8", 0)),  # 换手率
                            "quantity_relative": float(item.get("f22", 0)),  # 量比
                            "factor": 1.0,
                            "symbol": to_qlib_symbol(symbol),
                        }])
                        return df
        except Exception as e:
            logger.error(f"Eastmoney failed to fetch snapshot for {symbol}: {e}")
        return pd.DataFrame()

