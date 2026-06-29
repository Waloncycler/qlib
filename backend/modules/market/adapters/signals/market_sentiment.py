import logging
import pandas as pd
from modules.market.adapters.base import BaseSourceAdapter

logger = logging.getLogger("CN_Stock_Adapters_Signals")

class MarketSentimentAdapter(BaseSourceAdapter):
    """Adapter for Legulegu market temperature and sentiment statistics."""

    def get_instrument_list(self) -> list:
        return []

    def fetch_symbol_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def get_market_sentiment(self) -> dict:
        try:
            import akshare as ak
            df = ak.stock_market_activity_legu()
            if df is not None and not df.empty:
                row_map = {row['item'].strip(): row['value'] for idx, row in df.iterrows()}
                
                date_str = row_map.get("统计日期", "")
                if date_str:
                    date_str = str(date_str).split(" ")[0]
                else:
                    date_str = pd.Timestamp.now().strftime("%Y-%m-%d")
                
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

                date_param = date_str.replace("-", "")
                
                broken_limit_up_count = 0
                broken_limit_up_rate = 0.0
                highest_consecutive_limit_up = 0
                consecutive_limit_up_2_count = 0
                consecutive_limit_up_3_plus_count = 0
                yesterday_limit_up_avg_return = 0.0
                
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
                
                try:
                    df_zb = ak.stock_zt_pool_zbgc_em(date=date_param)
                    if df_zb is not None and not df_zb.empty:
                        broken_limit_up_count = len(df_zb)
                        total_attempts = int(limit_up) + broken_limit_up_count
                        broken_limit_up_rate = round(broken_limit_up_count / total_attempts, 4) if total_attempts > 0 else 0.0
                except Exception as e:
                    logger.warning(f"Failed to fetch broken limit up pool on {date_str}: {e}")
                
                try:
                    df_prev = ak.stock_zt_pool_previous_em(date=date_param)
                    if df_prev is not None and not df_prev.empty:
                        returns = pd.to_numeric(df_prev["涨跌幅"], errors="coerce").dropna()
                        if not returns.empty:
                            yesterday_limit_up_avg_return = round(float(returns.mean()), 2)
                except Exception as e:
                    logger.warning(f"Failed to fetch yesterday limit up pool on {date_str}: {e}")
                
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
                
                total_market_turnover = 0
                try:
                    import requests
                    resp = requests.get("https://qt.gtimg.cn/q=sh000001,sz399001", timeout=5)
                    if resp.status_code == 200:
                        lines = resp.text.strip().split(";")
                        for line in lines:
                            if line:
                                parts = line.split("~")
                                if len(parts) > 37:
                                    total_market_turnover += float(parts[37]) / 100000000
                except Exception as e:
                    logger.warning(f"Failed to fetch market turnover: {e}")
                    
                top_lhb = ""
                try:
                    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
                    params = {
                        "reportName": "RPT_DAILYBILLBOARD_DETAILS",
                        "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,NET_BUY_AMT",
                        "filter": f"(TRADE_DATE>='{date_str}')",
                        "pageNumber": "1",
                        "pageSize": "50",
                        "sortTypes": "-1",
                        "sortColumns": "NET_BUY_AMT",
                        "source": "WEB",
                        "client": "WEB"
                    }
                    import requests
                    r = requests.get(url, params=params, timeout=5)
                    d = r.json() or {}
                    result = d.get("result") or {}
                    data = result.get("data") or []
                    top_lhb = " ".join([str(x["SECURITY_NAME_ABBR"]) for x in data[:3]])
                except Exception as e:
                    logger.warning(f"Failed to fetch LHB: {e}")

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
                    "low120": low120,
                    "total_market_turnover": int(total_market_turnover),
                    "top_lhb": top_lhb
                })
                return res
        except Exception as e:
            logger.error(f"Failed to fetch Legulegu market activity: {e}")
        return {}
