import json
from pathlib import Path
import pandas as pd
import concurrent.futures
from loguru import logger

from modules.market.adapters import (
    ThsHotReasonAdapter,
    ThsNorthboundAdapter,
    BaiduConceptAdapter,
    EastmoneyFundFlowAdapter,
    DragonTigerAdapter,
    LockupAdapter,
    EastmoneyIndustryAdapter,
    MarketSentimentAdapter
)
from core.data_schema import validate_market_sentiment

class SignalsRunner:
    def __init__(self, config):
        self.config = config
        self.ths_hot = ThsHotReasonAdapter(config)
        self.ths_north = ThsNorthboundAdapter(config)
        self.baidu_concept = BaiduConceptAdapter(config)
        self.em_flow = EastmoneyFundFlowAdapter(config)
        self.dragon_tiger = DragonTigerAdapter(config)
        self.lockup = LockupAdapter(config)
        self.em_ind = EastmoneyIndustryAdapter(config)
        self.sentiment_adapter = MarketSentimentAdapter(config)

    def run(self, symbols: list, save_path: Path, is_all: bool = False):
        if is_all:
            self._run_market_wide(save_path)
            
        def process_signals_symbol(sym):
            def fetch_baidu_concepts():
                try:
                    concepts = self.baidu_concept.get_concept_blocks(sym)
                    if concepts:
                        with open(save_path / f"{sym}_baidu_concepts.json", "w", encoding="utf-8") as f:
                            json.dump(concepts, f, ensure_ascii=False, indent=4)
                        logger.info(f"Saved Baidu Concepts for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Baidu Concepts for {sym}: {e}")

            def fetch_em_minute_flow():
                try:
                    df_ff = self.em_flow.fetch_minute_flow(sym)
                    if not df_ff.empty:
                        df_ff.to_csv(save_path / f"{sym}_eastmoney_minute_flow.csv", index=False)
                        logger.info(f"Saved Eastmoney minute fund flow for {sym}")
                except Exception as e:
                    logger.debug(f"Eastmoney minute flow skipped for {sym}: {e}")

            def fetch_dragon_tiger():
                try:
                    today_str = pd.Timestamp.now().strftime("%Y-%m-%d")
                    dt_info = self.dragon_tiger.get_stock_dragon_tiger(sym, today_str)
                    if dt_info:
                        with open(save_path / f"{sym}_dragon_tiger.json", "w", encoding="utf-8") as f:
                            json.dump(dt_info, f, ensure_ascii=False, indent=4)
                        logger.info(f"Saved Dragon Tiger for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Dragon Tiger for {sym}: {e}")

            def fetch_lockup():
                try:
                    today_str = pd.Timestamp.now().strftime("%Y-%m-%d")
                    lock_info = self.lockup.get_lockup_expiry(sym, today_str)
                    if lock_info:
                        with open(save_path / f"{sym}_lockup_expiry.json", "w", encoding="utf-8") as f:
                            json.dump(lock_info, f, ensure_ascii=False, indent=4)
                        logger.info(f"Saved Lockup Expiry for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Lockup Expiry for {sym}: {e}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as inner_executor:
                futures = [
                    inner_executor.submit(fetch_baidu_concepts),
                    inner_executor.submit(fetch_em_minute_flow),
                    inner_executor.submit(fetch_dragon_tiger),
                    inner_executor.submit(fetch_lockup),
                ]
                concurrent.futures.wait(futures, timeout=30)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(process_signals_symbol, symbols))

    def _run_market_wide(self, save_path: Path):
        def process_sentiment():
            try:
                sent_data = self.sentiment_adapter.get_market_sentiment()
                if sent_data:
                    csv_path = save_path / "market_sentiment.csv"
                    if csv_path.exists():
                        try:
                            df_existing = pd.read_csv(csv_path)
                            df_existing["date"] = df_existing["date"].astype(str)
                        except Exception as e:
                            logger.warning(f"Failed to read existing market sentiment CSV: {e}. Re-creating.")
                            df_existing = pd.DataFrame()
                    else:
                        df_existing = pd.DataFrame()

                    df_new = pd.DataFrame([sent_data])
                    df_new["date"] = df_new["date"].astype(str)

                    if not df_existing.empty:
                        df_existing = df_existing.set_index("date")
                        df_new = df_new.set_index("date")
                        df_combined = df_new.combine_first(df_existing).reset_index()
                    else:
                        df_combined = df_new

                    df_combined = df_combined.sort_values("date")
                    cols_order = [
                        "date", "up_count", "down_count", "flat_count", "suspended_count",
                        "limit_up_count", "real_limit_up_count", "st_limit_up_count",
                        "limit_down_count", "real_limit_down_count", "st_limit_down_count",
                        "sentiment_score", "up_down_ratio",
                        "broken_limit_up_count", "broken_limit_up_rate",
                        "highest_consecutive_limit_up", "consecutive_limit_up_2_count",
                        "consecutive_limit_up_3_plus_count", "yesterday_limit_up_avg_return",
                        "high20", "high60", "high120", "low20", "low60", "low120"
                    ]
                    other_cols = [c for c in df_combined.columns if c not in cols_order]
                    final_cols = [c for c in cols_order if c in df_combined.columns] + other_cols
                    df_combined = df_combined[final_cols]
                    
                    if validate_market_sentiment(df_combined):
                        df_combined.to_csv(csv_path, index=False)
                        logger.info(f"Saved market sentiment data for date {sent_data['date']} to {csv_path}")
                    else:
                        logger.error(f"Skipped saving market sentiment data for {sent_data['date']} due to schema validation failure.")
                        df_new.to_csv(csv_path.with_name("market_sentiment_failed_schema.csv"), index=False)
            except Exception as e:
                logger.error(f"Failed to process market sentiment data: {e}")

        def process_ths_hot():
            try:
                df_hot = self.ths_hot.get_hot_reasons()
                if not df_hot.empty:
                    df_hot.to_csv(save_path / "ths_hot_reasons.csv", index=False)
                    logger.info("Saved THS Hot Reasons")
            except Exception as e:
                logger.error(f"Failed to fetch THS Hot Reasons: {e}")

        def process_ths_north():
            try:
                df_north = self.ths_north.fetch_realtime_minute_flow()
                if not df_north.empty:
                    df_north.to_csv(save_path / "ths_northbound_realtime_minute.csv", index=False)
                    logger.info("Saved THS Northbound Realtime Minute flow")
            except Exception as e:
                logger.error(f"Failed to fetch Northbound minute flow: {e}")
            try:
                df_north_hist = self.ths_north.load_cached_history()
                if not df_north_hist.empty:
                    df_north_hist.to_csv(save_path / "ths_northbound_history.csv", index=False)
                    logger.info("Saved THS Northbound historical flow")
            except Exception as e:
                logger.error(f"Failed to fetch Northbound history: {e}")

        def process_em_ind():
            try:
                df_ind = self.em_ind.get_industry_board_rankings()
                if not df_ind.empty:
                    df_ind.to_csv(save_path / "eastmoney_industry_rankings.csv", index=False)
                    logger.info("Saved Eastmoney Industry rankings")
            except Exception as e:
                logger.error(f"Failed to fetch Industry rankings: {e}")

        # Run sequentially to avoid mini_racer (V8) crash in akshare on Apple Silicon (not thread-safe)
        process_sentiment()
        process_ths_hot()
        process_ths_north()
        process_em_ind()
