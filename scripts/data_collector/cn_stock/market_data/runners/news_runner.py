from pathlib import Path
import concurrent.futures
from loguru import logger

from market_data.adapters import (
    EastmoneyStockNewsAdapter,
    ClsTelegraphAdapter,
    EastmoneyGlobalNewsAdapter
)

class NewsRunner:
    def __init__(self, config):
        self.config = config
        self.em_news = EastmoneyStockNewsAdapter(config)
        self.cls_tel = ClsTelegraphAdapter(config)
        self.em_global = EastmoneyGlobalNewsAdapter(config)

    def _run_market_wide(self, save_path: Path):
        try:
            df_tel = self.cls_tel.fetch_telegraph()
            if not df_tel.empty:
                df_tel.to_json(save_path / "cls_telegraph.json", orient="records", force_ascii=False, indent=4)
                logger.info("Saved CLS Telegraph Stream")
        except Exception as e:
            logger.error(f"Failed to fetch CLS telegraph: {e}")

        try:
            df_gl = self.em_global.fetch_global_news()
            if not df_gl.empty:
                df_gl.to_json(save_path / "eastmoney_global_news.json", orient="records", force_ascii=False, indent=4)
                logger.info("Saved Eastmoney Global News Stream")
        except Exception as e:
            logger.error(f"Failed to fetch Eastmoney global news: {e}")

    def run(self, symbols: list, save_path: Path, is_all: bool = False):
        if is_all:
            self._run_market_wide(save_path)
            
        def process_news_symbol(sym):
            try:
                df_n = self.em_news.fetch_stock_news(sym)
                if not df_n.empty:
                    df_n.to_json(save_path / f"{sym}_eastmoney_news.json", orient="records", force_ascii=False, indent=4)
                    logger.info(f"Saved Eastmoney stock news for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch Eastmoney stock news for {sym}: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(process_news_symbol, symbols))
