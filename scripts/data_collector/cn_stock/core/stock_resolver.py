import os
import sys
import yaml
import time
import pandas as pd
from pathlib import Path
from loguru import logger
import concurrent.futures
import threading

CUR_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CUR_DIR.parent
sys.path.append(str(PROJECT_DIR))

from market_data.adapters import (
    DragonTigerAdapter,
    MarketSentimentAdapter,
    ThsNorthboundAdapter,
    EastmoneyIndustryAdapter,
    clean_symbol,
    to_qlib_symbol
)
from market_data.collector import CnStockCollector

class StockResolver:
    def __init__(self, config_path=None):
        self.config_path = config_path or str(PROJECT_DIR / "secret.yaml")
        self.watchlist_path = str(PROJECT_DIR / "watchlist.yaml")
        
        # Load configs
        self.secret = self._load_yaml(self.config_path)
        self.watchlist = self._load_yaml(self.watchlist_path)
        
        # Simple cache for single stock resolution
        self._resolve_cache = {}
        
    def _load_yaml(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}
        
    def get_dynamic_watchlist(self) -> list:
        """Aggregates static symbols and dynamic hot stocks based on watchlist.yaml."""
        symbols_set = set()
        
        # 1. Static symbols
        static = self.watchlist.get("static_symbols", [])
        for sym in static:
            symbols_set.add(to_qlib_symbol(clean_symbol(sym)))
            
        # 2. Dynamic hot stocks
        if self.watchlist.get("auto_hot_stocks"):
            sources = self.watchlist.get("hot_stock_sources", {})
            logger.info("Aggregating dynamic hot stocks...")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                
                if sources.get("dragon_tiger_top_n", 0) > 0:
                    futures.append(executor.submit(self._get_dragon_tiger, sources["dragon_tiger_top_n"]))
                    
                if sources.get("limit_up_leaders"):
                    futures.append(executor.submit(self._get_limit_up_leaders))
                    
                if sources.get("northbound_top_n", 0) > 0:
                    futures.append(executor.submit(self._get_northbound, sources["northbound_top_n"]))
                    
                if sources.get("broken_limit_up"):
                    futures.append(executor.submit(self._get_broken_limit_up))
                    
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    try:
                        res = future.result()
                        for sym in res:
                            symbols_set.add(to_qlib_symbol(clean_symbol(sym)))
                    except Exception as e:
                        logger.error(f"Error fetching hot stocks: {e}")
                        
        final_list = sorted(list(symbols_set))
        logger.info(f"Final dynamic watchlist contains {len(final_list)} symbols.")
        return final_list

    def _get_dragon_tiger(self, top_n) -> list:
        try:
            dt = DragonTigerAdapter(self.secret)
            # using today's date, or latest trading day (dt adapter handles if data is empty)
            # EastMoney API usually returns empty if today has no data yet.
            # To be safe, we don't query a specific date in the new API but let it fetch the latest.
            # Note: We just query the daily list and take top N by net buy
            import requests
            url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
            params = {
                "reportName": "RPT_DAILYBILLBOARD_DETAILS",
                "columns": "SECURITY_CODE,SECURITY_NAME_ABBR,NET_BUY_AMT",
                "filter": "",
                "pageNumber": "1",
                "pageSize": "50",
                "sortTypes": "-1",
                "sortColumns": "NET_BUY_AMT",
                "source": "WEB",
                "client": "WEB"
            }
            # Need resilient_request here
            from market_data.adapters.base import resilient_request
            r = resilient_request("get", url, params=params)
            d = r.json() or {}
            result = d.get("result") or {}
            data = result.get("data") or []
            return [str(x["SECURITY_CODE"]) for x in data[:top_n]]
        except Exception as e:
            logger.warning(f"Dragon tiger aggregation failed: {e}")
            return []
            
    def _get_limit_up_leaders(self) -> list:
        # Fetch from MarketSentimentAdapter zt_pool
        try:
            ms = MarketSentimentAdapter(self.secret)
            # Use resilient_request directly for zt_pool
            from market_data.adapters.base import resilient_request
            url = "http://push2ex.eastmoney.com/getTopicZTPool"
            params = {"ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.ztb"}
            r = resilient_request("get", url, params=params)
            d = r.json() or {}
            data_dict = d.get("data") or {}
            data = data_dict.get("pool") or []
            # Sort by consecutive days
            data.sort(key=lambda x: x.get("lbc", 0), reverse=True)
            # Take top 5
            return [str(x["c"]) for x in data[:5]]
        except Exception as e:
            logger.warning(f"Limit up leaders aggregation failed: {e}")
            return []

    def _get_northbound(self, top_n) -> list:
        # Use THS Northbound real-time top active stocks
        # For simplicity, we just use the static list or a known endpoint
        return [] # Placeholder, as THS API is complex for top stocks

    def _get_broken_limit_up(self) -> list:
        try:
            from market_data.adapters.base import resilient_request
            url = "http://push2ex.eastmoney.com/getTopicZBPool"
            params = {"ut": "7eea3edcaed734bea9cbfc24409ed989", "dpt": "wz.ztb"}
            r = resilient_request("get", url, params=params)
            d = r.json() or {}
            data_dict = d.get("data") or {}
            data = data_dict.get("pool") or []
            # Take top 3 by amount
            data.sort(key=lambda x: x.get("zdf", 0), reverse=True)
            return [str(x["c"]) for x in data[:3]]
        except Exception as e:
            logger.warning(f"Broken limit up aggregation failed: {e}")
            return []

    @staticmethod
    def _is_trading_hours() -> bool:
        """Check if current time is within A-share trading session (09:15 - 15:30 on weekdays)."""
        from datetime import datetime
        now = datetime.now()
        if now.weekday() >= 5:  # Saturday/Sunday
            return False
        hour_min = now.hour * 100 + now.minute
        return 915 <= hour_min <= 1530

    def _get_cache_ttl(self) -> int:
        """Return cache TTL in seconds based on market hours."""
        if self._is_trading_hours():
            return 180   # 3 minutes during trading
        else:
            return 21600  # 6 hours after market close

    def resolve_single_stock(self, symbol: str, layer: str = None):
        """Fetch all or specific layers for a single stock synchronously. Used by frontend API."""
        symbol = to_qlib_symbol(clean_symbol(symbol))
        
        # Time-aware cache: short during trading hours, long after hours
        cache_key = f"{symbol}_{layer}" if layer else symbol
        now = time.time()
        ttl = self._get_cache_ttl()
        if cache_key in self._resolve_cache:
            last_time = self._resolve_cache[cache_key]
            if now - last_time < ttl:
                logger.info(f"{cache_key} data was fetched recently. Using cache (TTL={ttl}s).")
                return True

        # Auto-refresh stale market-wide data before checking individual stock cache
        save_dir = CUR_DIR.parent.parent.parent.parent / "data/cn_stock/hierarchical"
        if layer == "signals" or not layer:
            market_file_sig = save_dir / "signals" / "ths_hot_reasons.csv"
            if not market_file_sig.exists() or time.time() - market_file_sig.stat().st_mtime > 4 * 3600:
                logger.info("Market-wide signals are stale. Triggering background refresh...")
                def _update_signals():
                    try:
                        from market_data.runners.signals_runner import SignalsRunner
                        SignalsRunner(self.config_path)._run_market_wide(save_dir / "signals")
                    except Exception as e:
                        logger.error(f"Auto-refresh signals failed: {e}")
                threading.Thread(target=_update_signals, daemon=True).start()

        if layer == "news" or not layer:
            market_file_news = save_dir / "news" / "cls_telegraph.json"
            if not market_file_news.exists() or time.time() - market_file_news.stat().st_mtime > 4 * 3600:
                logger.info("Market-wide news are stale. Triggering background refresh...")
                def _update_news():
                    try:
                        from market_data.runners.news_runner import NewsRunner
                        NewsRunner(self.config_path)._run_market_wide(save_dir / "news")
                    except Exception as e:
                        logger.error(f"Auto-refresh news failed: {e}")
                threading.Thread(target=_update_news, daemon=True).start()

        # If market is closed and data files already exist on disk AND are fresh, skip network fetch
        if not self._is_trading_hours():
            check_file = save_dir / "market" / f"{symbol}_tencent_sina_kline.csv"
            if layer == "news":
                check_file = save_dir / "news" / f"{symbol}_eastmoney_news.json"
            elif layer == "signals":
                check_file = save_dir / "signals" / f"{symbol}_dragon_tiger.json"
            elif layer == "capital":
                check_file = save_dir / "capital" / f"{symbol}_fund_flow_120d.csv"
            elif layer == "fundamentals":
                check_file = save_dir / "fundamentals" / f"{symbol}_mootdx_finance.csv"

            if check_file.exists():
                # If file is less than 12 hours old, it's safe to skip fetching after market close
                if time.time() - check_file.stat().st_mtime < 12 * 3600:
                    logger.info(f"Market closed & data on disk for {symbol}_{layer} is fresh. Skipping network fetch.")
                    self._resolve_cache[cache_key] = now
                    return True
                
        logger.info(f"Real-time fetching layer(s) for {symbol}: {layer or 'ALL'}...")
        
        collector = CnStockCollector(
            save_dir=str(CUR_DIR),
            limit_nums=None,
            source="akshare",
            config_path=self.config_path
        )
        # We omit 'research' and 'filings' because downloading PDF reports takes >10 seconds and is not used in UI.
        layers = [layer] if layer else ["market", "signals", "capital", "fundamentals", "news"]
        
        # When fetching a single stock via frontend API, we only need ~180 days of history for speed
        start_date = pd.Timestamp.now() - pd.Timedelta(days=180)
        
        def run_layer(l):
            collector.download_layer(layer=l, symbol=symbol, save_dir=save_dir, start_date=start_date)
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(layers)) as executor:
            futures = {executor.submit(run_layer, l): l for l in layers}
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error fetching layer: {e}")
                    
        self._resolve_cache[cache_key] = now
        return True

if __name__ == "__main__":
    resolver = StockResolver()
    symbols = resolver.get_dynamic_watchlist()
    print("Watchlist symbols:", symbols)
