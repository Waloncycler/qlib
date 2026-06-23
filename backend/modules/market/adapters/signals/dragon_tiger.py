import logging
import pandas as pd
from datetime import datetime, timedelta
from modules.market.adapters.base import BaseSourceAdapter, clean_symbol, to_qlib_symbol, eastmoney_datacenter

logger = logging.getLogger("CN_Stock_Adapters_Signals")

class DragonTigerAdapter(BaseSourceAdapter):
    """Adapter for EastMoney Dragon-Tiger board seats and daily statistics."""

    def get_instrument_list(self) -> list:
        return []

    def fetch_symbol_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> pd.DataFrame:
        return pd.DataFrame()

    def get_stock_dragon_tiger(self, symbol: str, trade_date: str, look_back_days: int = 30) -> dict:
        code = clean_symbol(symbol)
        start = datetime.strptime(trade_date, "%Y-%m-%d") - timedelta(days=look_back_days)
        start_str = start.strftime("%Y-%m-%d")

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
