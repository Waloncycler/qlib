from pathlib import Path
import pandas as pd
import json
import concurrent.futures
from loguru import logger

from modules.market.adapters import (
    BaiduKlineAdapter,
    TencentSinaAdapter,
    MootdxAdapter,
    EastmoneyAdapter
)

class MarketRunner:
    def __init__(self, config):
        self.config = config
        self.baidu = BaiduKlineAdapter(config)
        self.ts = TencentSinaAdapter(config)
        self.mdx = MootdxAdapter(config)
        self.em = EastmoneyAdapter(config)

    def run(self, symbols: list, save_path: Path, start_date: pd.Timestamp = None):
        def process_market(sym):
            # Run all data sources in parallel within each symbol
            def fetch_baidu():
                try:
                    sd = start_date if start_date else pd.Timestamp("2022-01-01")
                    df_k = self.baidu.fetch_symbol_data(sym, "1d", sd, pd.Timestamp.now())
                    if not df_k.empty:
                        df_k.to_csv(save_path / f"{sym}_baidu_kline.csv", index=False)
                        logger.info(f"Saved Baidu KLine for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Baidu Kline for {sym}: {e}")

            def fetch_tencent_sina():
                try:
                    sd = start_date if start_date else pd.Timestamp("2022-01-01")
                    df_ts = self.ts.fetch_symbol_data(sym, "1d", sd, pd.Timestamp.now())
                    if not df_ts.empty:
                        df_ts.to_csv(save_path / f"{sym}_tencent_sina_kline.csv", index=False)
                        logger.info(f"Saved Tencent/Sina KLine for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Tencent/Sina KLine for {sym}: {e}")

            def fetch_quotes():
                try:
                    quotes = self.ts.fetch_tencent_quotes([sym])
                    if quotes:
                        with open(save_path / f"{sym}_tencent_quotes.json", "w", encoding="utf-8") as f:
                            json.dump(quotes, f, ensure_ascii=False, indent=4)
                        logger.info(f"Saved Tencent Quotes for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Tencent quotes for {sym}: {e}")

            def fetch_eastmoney():
                # Non-critical: frontend doesn't display this. Use fast timeout.
                try:
                    df_em = self.em.fetch_symbol_data(sym, "1d", pd.Timestamp.now().normalize(), pd.Timestamp.now())
                    if not df_em.empty:
                        df_em.to_csv(save_path / f"{sym}_eastmoney_snapshot.csv", index=False)
                        logger.info(f"Saved Eastmoney snapshot for {sym}")
                except Exception as e:
                    logger.debug(f"Eastmoney snapshot skipped for {sym}: {e}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as inner_executor:
                futures = [
                    inner_executor.submit(fetch_tencent_sina),
                    inner_executor.submit(fetch_quotes)
                ]
                concurrent.futures.wait(futures, timeout=10)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(process_market, symbols))
