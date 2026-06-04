import os
import sys
import yaml
import time
import pandas as pd
from pathlib import Path
from loguru import logger
import concurrent.futures

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

    def resolve_single_stock(self, symbol: str, layer: str = None):
        """Fetch all or specific layers for a single stock synchronously. Used by frontend API."""
        symbol = to_qlib_symbol(clean_symbol(symbol))
        
        # Check cache (5 min TTL)
        cache_key = f"{symbol}_{layer}" if layer else symbol
        now = time.time()
        if cache_key in self._resolve_cache:
            last_time = self._resolve_cache[cache_key]
            if now - last_time < 300:
                logger.info(f"{cache_key} data was fetched recently. Using cache.")
                return True
                
        logger.info(f"Real-time fetching layer(s) for {symbol}: {layer or 'ALL'}...")
        save_dir = CUR_DIR.parent.parent.parent.parent / "data/cn_stock/hierarchical"
        
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
        
        def run_layer(layer):
            collector.download_layer(layer=layer, symbol=symbol, save_dir=save_dir, start_date=start_date)
            
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
