# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import logging
from datetime import datetime, timedelta, date as datetime_date
from pathlib import Path
import pandas as pd
import requests

from adapters.base import (
    BaseSourceAdapter,
    clean_symbol,
    eastmoney_datacenter,
    get_market_prefix,
    to_qlib_symbol,
    UA,
)

logger = logging.getLogger("CN_Stock_Adapters_Signals")


class ThsHotReasonAdapter(BaseSourceAdapter):
    """Adapter for TongHuShun daily strong stocks and theme attribution (题材归因)."""

    def get_instrument_list(self) -> list:
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        # Not standard time-series daily bar, return empty. Use get_hot_reasons for custom logic.
        return pd.DataFrame()

    def get_hot_reasons(self, query_date: str = None) -> pd.DataFrame:
        """Fetch today's strong stocks and their reason tags. query_date: YYYY-MM-DD"""
        if query_date is None:
            query_date = datetime_date.today().strftime("%Y-%m-%d")

        url = f"http://zx.10jqka.com.cn/event/api/getharden/date/{query_date}/orderby/date/orderway/desc/charset/GBK/"
        headers = {"User-Agent": UA}
        try:
            r = requests.get(url, headers=headers, timeout=10)
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


class ThsNorthboundAdapter(BaseSourceAdapter):
    """Adapter for THS Northbound minutes and local history cache."""

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

    def fetch_realtime_minute_flow(self) -> pd.DataFrame:
        """Fetch today's intraday minute-level Northbound cumulative net flows."""
        url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
        headers = {
            "User-Agent": UA,
            "Host": "data.hexin.cn",
            "Referer": "https://data.hexin.cn/",
        }
        try:
            r = requests.get(url, headers=headers, timeout=10)
            d = r.json()
            times = d.get("time", [])
            hgt = d.get("hgt", [])
            sgt = d.get("sgt", [])
            n = len(times)
            df = pd.DataFrame({
                "time": times,
                "hgt_yi": hgt[:n] + [None] * (n - len(hgt)),
                "sgt_yi": sgt[:n] + [None] * (n - len(sgt)),
            })
            return df
        except Exception as e:
            logger.error(f"THS Northbound flow failed: {e}")
        return pd.DataFrame()

    def get_cache_path(self) -> Path:
        p = Path.home() / ".tradingagents" / "cache" / "northbound_daily.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def cache_today_flow(self, query_date: str = None) -> bool:
        """Save/Append daily closing flow to local history CSV cache."""
        df = self.fetch_realtime_minute_flow()
        if df.empty:
            return False
        df_valid = df.dropna()
        if df_valid.empty:
            return False
            
        if query_date is None:
            query_date = datetime_date.today().strftime("%Y-%m-%d")
            
        last = df_valid.iloc[-1]
        path = self.get_cache_path()
        rows = {}
        if path.exists():
            try:
                for line in path.read_text(encoding="utf-8").strip().split("\n")[1:]:
                    parts = line.split(",")
                    if len(parts) == 3:
                        rows[parts[0]] = line
            except Exception as e:
                logger.warning(f"Failed to read northbound cache: {e}")
                
        rows[query_date] = f"{query_date},{last['hgt_yi']},{last['sgt_yi']}"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("date,hgt_yi,sgt_yi\n")
                for d in sorted(rows.keys()):
                    f.write(rows[d] + "\n")
            return True
        except Exception as e:
            logger.error(f"Failed to write northbound cache: {e}")
        return False

    def load_cached_history(self, n: int = 30) -> pd.DataFrame:
        path = self.get_cache_path()
        if not path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_csv(path)
            df["date"] = pd.to_datetime(df["date"])
            return df.tail(n)
        except Exception as e:
            logger.error(f"Failed to load northbound cache: {e}")
        return pd.DataFrame()


class BaiduConceptAdapter(BaseSourceAdapter):
    """Adapter for Baidu stock concepts, industry, and regional classifications."""

    def get_instrument_list(self) -> list:
        return ["SH600000", "SZ000001", "SZ000002", "SH600519", "SZ300750"]

    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
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


class EastmoneyFundFlowAdapter(BaseSourceAdapter):
    """Adapter for EastMoney push2 minute-level stock fund flow (盘中)."""

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

    def fetch_minute_flow(self, symbol: str) -> pd.DataFrame:
        code = clean_symbol(symbol)
        prefix_num = 1 if code.startswith("6") else 0
        secid = f"{prefix_num}.{code}"
        url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
        params = {
            "secid": secid,
            "klt": 1,
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
        }
        headers = {
            "User-Agent": UA,
            "Referer": "https://quote.eastmoney.com/",
            "Origin": "https://quote.eastmoney.com",
        }
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            d = r.json()
            klines = d.get("data", {}).get("klines", [])
            rows = []
            for line in klines:
                parts = line.split(",")
                if len(parts) >= 6:
                    rows.append({
                        "time": parts[0],
                        "main_net": float(parts[1]),
                        "small_net": float(parts[2]),
                        "mid_net": float(parts[3]),
                        "large_net": float(parts[4]),
                        "super_net": float(parts[5]),
                    })
            if rows:
                df = pd.DataFrame(rows)
                df["symbol"] = to_qlib_symbol(symbol)
                return df
        except Exception as e:
            logger.error(f"Eastmoney minute flow failed for {symbol}: {e}")
        return pd.DataFrame()


class DragonTigerAdapter(BaseSourceAdapter):
    """Adapter for EastMoney Dragon-Tiger board seats and daily statistics."""

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

    def get_stock_dragon_tiger(self, symbol: str, trade_date: str, look_back_days: int = 30) -> dict:
        """Get Dragon-Tiger board occurrences, broker seats detail, and institutional buying/selling."""
        code = clean_symbol(symbol)
        start = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=look_back_days)
        start_str = start.strftime("%Y-%m-%d")

        # 1. Billboard list
        records = []
        data = eastmoney_datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            filter_str=f"(TRADE_DATE>='{start_str}')(TRADE_DATE<='{trade_date}')(SECURITY_CODE=\"{code}\")",
            page_size=50,
            sort_columns="TRADE_DATE",
            sort_types="-1",
        )
        for row in data:
            records.append({
                "date": str(row.get("TRADE_DATE", ""))[:10],
                "reason": row.get("EXPLANATION", ""),
                "net_buy_wan": round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
                "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
            })

        seats = {"buy": [], "sell": []}
        institution = {"buy_amt_wan": 0, "sell_amt_wan": 0, "net_amt_wan": 0}

        if records:
            latest_date = records[0]["date"]
            # Buy details
            buy_data = eastmoney_datacenter(
                "RPT_BILLBOARD_DAILYDETAILSBUY",
                filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")",
                page_size=10,
                sort_columns="BUY",
                sort_types="-1",
            )
            for row in buy_data[:5]:
                seats["buy"].append({
                    "name": row.get("OPERATEDEPT_NAME", ""),
                    "buy_amt_wan": round((row.get("BUY") or 0) / 10000, 1),
                    "sell_amt_wan": round((row.get("SELL") or 0) / 10000, 1),
                    "net_wan": round((row.get("NET") or 0) / 10000, 1),
                })
            # Sell details
            sell_data = eastmoney_datacenter(
                "RPT_BILLBOARD_DAILYDETAILSSELL",
                filter_str=f"(TRADE_DATE='{latest_date}')(SECURITY_CODE=\"{code}\")",
                page_size=10,
                sort_columns="SELL",
                sort_types="-1",
            )
            for row in sell_data[:5]:
                seats["sell"].append({
                    "name": row.get("OPERATEDEPT_NAME", ""),
                    "buy_amt_wan": round((row.get("BUY") or 0) / 10000, 1),
                    "sell_amt_wan": round((row.get("SELL") or 0) / 10000, 1),
                    "net_wan": round((row.get("NET") or 0) / 10000, 1),
                })

            # Institutional buying/selling (OPERATEDEPT_CODE = '0')
            for detail_data, side in [(buy_data, "buy"), (sell_data, "sell")]:
                for row in detail_data:
                    if str(row.get("OPERATEDEPT_CODE", "")) == "0":
                        amt = (row.get("BUY") or 0) if side == "buy" else (row.get("SELL") or 0)
                        if side == "buy":
                            institution["buy_amt_wan"] += amt
                        else:
                            institution["sell_amt_wan"] += amt
                            
            institution["buy_amt_wan"] = round(institution["buy_amt_wan"] / 10000, 1)
            institution["sell_amt_wan"] = round(institution["sell_amt_wan"] / 10000, 1)
            institution["net_amt_wan"] = round(institution["buy_amt_wan"] - institution["sell_amt_wan"], 1)

        return {"records": records, "seats": seats, "institution": institution}

    def get_daily_dragon_tiger(self, trade_date: str = None, min_net_buy_wan: float = None) -> pd.DataFrame:
        """Fetch full-market billboard list for a date."""
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y-%m-%d")

        data = eastmoney_datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
            page_size=500,
            sort_columns="BILLBOARD_NET_AMT",
            sort_types="-1",
        )
        if not data:
            return pd.DataFrame()

        stocks = []
        for row in data:
            net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000
            if min_net_buy_wan is not None and net_buy < min_net_buy_wan:
                continue
            stocks.append({
                "code": row.get("SECURITY_CODE", ""),
                "name": row.get("SECURITY_NAME_ABBR", ""),
                "reason": row.get("EXPLANATION", ""),
                "close": row.get("CLOSE_PRICE") or 0.0,
                "change_pct": round(float(row.get("CHANGE_RATE") or 0.0), 2),
                "net_buy_wan": round(net_buy, 1),
                "buy_wan": round((row.get("BILLBOARD_BUY_AMT") or 0) / 10000, 1),
                "sell_wan": round((row.get("BILLBOARD_SELL_AMT") or 0) / 10000, 1),
                "turnover_pct": round(float(row.get("TURNOVERRATE") or 0.0), 2),
                "symbol": to_qlib_symbol(row.get("SECURITY_CODE", "")),
                "date": pd.to_datetime(trade_date),
            })
        return pd.DataFrame(stocks)


class LockupAdapter(BaseSourceAdapter):
    """Adapter for Lockup Release calendars (restricted stock unlock)."""

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

    def get_lockup_expiry(self, symbol: str, trade_date: str, forward_days: int = 90) -> dict:
        code = clean_symbol(symbol)
        # History
        history_data = eastmoney_datacenter(
            "RPT_LIFT_STAGE",
            filter_str=f"(SECURITY_CODE=\"{code}\")",
            page_size=15,
            sort_columns="FREE_DATE",
            sort_types="-1",
        )
        history = []
        for row in history_data:
            history.append({
                "date": str(row.get("FREE_DATE", ""))[:10],
                "type": row.get("LIMITED_STOCK_TYPE", ""),
                "shares": row.get("FREE_SHARES_NUM", 0),
                "ratio": row.get("FREE_RATIO", 0.0),
            })

        # Future
        end_date = datetime.strptime(trade_date, "%Y-%m-%d") + timedelta(days=forward_days)
        end_str = end_date.strftime("%Y-%m-%d")
        upcoming_data = eastmoney_datacenter(
            "RPT_LIFT_STAGE",
            filter_str=f"(SECURITY_CODE=\"{code}\")(FREE_DATE>='{trade_date}')(FREE_DATE<='{end_str}')",
            page_size=20,
            sort_columns="FREE_DATE",
            sort_types="1",
        )
        upcoming = []
        for row in upcoming_data:
            upcoming.append({
                "date": str(row.get("FREE_DATE", ""))[:10],
                "type": row.get("LIMITED_STOCK_TYPE", ""),
                "shares": row.get("FREE_SHARES_NUM", 0),
                "ratio": row.get("FREE_RATIO", 0.0),
            })

        return {"history": history, "upcoming": upcoming}


class EastmoneyIndustryAdapter(BaseSourceAdapter):
    """Adapter for EastMoney sector board return rankings and flow leaders."""

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

    def get_industry_board_rankings(self, top_n: int = 20) -> pd.DataFrame:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "100", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:90+t:2",  # Eastmoney Sector board code
            "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
        }
        headers = {"User-Agent": UA}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            d = r.json()
            items = d.get("data", {}).get("diff", [])
            rows = []
            for i, item in enumerate(items):
                rows.append({
                    "rank": i + 1,
                    "name": item.get("f14", ""),
                    "change_pct": item.get("f3", 0.0),
                    "code": item.get("f12", ""),
                    "up_count": item.get("f104", 0),
                    "down_count": item.get("f105", 0),
                    "leader": item.get("f140", ""),
                    "leader_change_pct": item.get("f136", 0.0),
                })
            if rows:
                df = pd.DataFrame(rows)
                return df.head(top_n)
        except Exception as e:
            logger.error(f"Eastmoney industry boards ranking query failed: {e}")
        return pd.DataFrame()


class MarketSentimentAdapter(BaseSourceAdapter):
    """Adapter for Legulegu market temperature and sentiment statistics."""

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

    def get_market_sentiment(self) -> dict:
        """Fetch market sentiment indicators from Legulegu via Akshare."""
        try:
            import akshare as ak
            df = ak.stock_market_activity_legu()
            if df is not None and not df.empty:
                # Map rows to dictionary
                row_map = {row['item'].strip(): row['value'] for idx, row in df.iterrows()}
                
                # Extract date from 统计日期 (e.g. "2026-05-22 15:00:00")
                date_str = row_map.get("统计日期", "")
                if date_str:
                    date_str = str(date_str).split(" ")[0]
                else:
                    date_str = pd.Timestamp.now().strftime("%Y-%m-%d")
                
                # Parse sentiment score (活跃度, e.g. '71.73%')
                act_str = str(row_map.get("活跃度", "0.0%"))
                if "%" in act_str:
                    try:
                        sentiment_score = float(act_str.replace("%", "").strip())
                    except ValueError:
                        sentiment_score = 0.0
                else:
                    try:
                        sentiment_score = float(act_str)
                    except ValueError:
                        sentiment_score = 0.0
                
                # Extract counts safely
                def get_float_val(key, default=0.0):
                    val = row_map.get(key, default)
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return default

                up_count = get_float_val("上涨")
                down_count = get_float_val("下跌")
                flat_count = get_float_val("平盘")
                suspended_count = get_float_val("停牌")
                limit_up = get_float_val("涨停")
                real_limit_up = get_float_val("真实涨停")
                st_limit_up = get_float_val("st st*涨停")
                limit_down = get_float_val("跌停")
                real_limit_down = get_float_val("真实跌停")
                st_limit_down = get_float_val("st st*跌停")

                up_down_ratio = up_count / down_count if down_count > 0 else up_count

                res = {
                    "date": date_str,
                    "up_count": int(up_count),
                    "down_count": int(down_count),
                    "flat_count": int(flat_count),
                    "suspended_count": int(suspended_count),
                    "limit_up_count": int(limit_up),
                    "real_limit_up_count": int(real_limit_up),
                    "st_limit_up_count": int(st_limit_up),
                    "limit_down_count": int(limit_down),
                    "real_limit_down_count": int(real_limit_down),
                    "st_limit_down_count": int(st_limit_down),
                    "sentiment_score": sentiment_score,
                    "up_down_ratio": round(up_down_ratio, 3)
                }

                # Query extra metrics dynamically for today
                date_param = date_str.replace("-", "")
                
                broken_limit_up_count = 0
                broken_limit_up_rate = 0.0
                highest_consecutive_limit_up = 0
                consecutive_limit_up_2_count = 0
                consecutive_limit_up_3_plus_count = 0
                yesterday_limit_up_avg_return = 0.0
                
                # Limit up pool
                try:
                    df_zt = ak.stock_zt_pool_em(date=date_param)
                    if df_zt is not None and not df_zt.empty:
                        if "连板数" in df_zt.columns:
                            consec_series = pd.to_numeric(df_zt["连板数"], errors="coerce").fillna(1)
                            highest_consecutive_limit_up = int(consec_series.max())
                            consecutive_limit_up_2_count = int((consec_series == 2).sum())
                            consecutive_limit_up_3_plus_count = int((consec_series >= 3).sum())
                except Exception as e:
                    logger.warning(f"Failed to fetch limit up pool on {date_str}: {e}")
                
                # Broken limit up pool
                try:
                    df_zb = ak.stock_zt_pool_zbgc_em(date=date_param)
                    if df_zb is not None and not df_zb.empty:
                        broken_limit_up_count = len(df_zb)
                        total_attempts = int(limit_up) + broken_limit_up_count
                        broken_limit_up_rate = round(broken_limit_up_count / total_attempts, 4) if total_attempts > 0 else 0.0
                except Exception as e:
                    logger.warning(f"Failed to fetch broken limit up pool on {date_str}: {e}")
                
                # Yesterday limit up pool
                try:
                    df_prev = ak.stock_zt_pool_previous_em(date=date_param)
                    if df_prev is not None and not df_prev.empty:
                        returns = pd.to_numeric(df_prev["涨跌幅"], errors="coerce").dropna()
                        if not returns.empty:
                            yesterday_limit_up_avg_return = round(float(returns.mean()), 2)
                except Exception as e:
                    logger.warning(f"Failed to fetch yesterday limit up pool on {date_str}: {e}")
                
                # High/low statistics
                high20 = 0
                high60 = 0
                high120 = 0
                low20 = 0
                low60 = 0
                low120 = 0
                try:
                    df_hl = ak.stock_a_high_low_statistics(symbol="all")
                    if df_hl is not None and not df_hl.empty:
                        df_hl["date"] = df_hl["date"].astype(str)
                        matching_row = df_hl[df_hl["date"] == date_str]
                        if not matching_row.empty:
                            high20 = int(matching_row.iloc[0]["high20"])
                            high60 = int(matching_row.iloc[0]["high60"])
                            high120 = int(matching_row.iloc[0]["high120"])
                            low20 = int(matching_row.iloc[0]["low20"])
                            low60 = int(matching_row.iloc[0]["low60"])
                            low120 = int(matching_row.iloc[0]["low120"])
                except Exception as e:
                    logger.warning(f"Failed to fetch high/low statistics: {e}")
                
                res.update({
                    "broken_limit_up_count": broken_limit_up_count,
                    "broken_limit_up_rate": broken_limit_up_rate,
                    "highest_consecutive_limit_up": highest_consecutive_limit_up,
                    "consecutive_limit_up_2_count": consecutive_limit_up_2_count,
                    "consecutive_limit_up_3_plus_count": consecutive_limit_up_3_plus_count,
                    "yesterday_limit_up_avg_return": yesterday_limit_up_avg_return,
                    "high20": high20,
                    "high60": high60,
                    "high120": high120,
                    "low20": low20,
                    "low60": low60,
                    "low120": low120
                })
                return res
        except Exception as e:
            logger.error(f"Failed to fetch Legulegu market activity: {e}")
        return {}

