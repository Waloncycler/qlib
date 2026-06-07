from pathlib import Path
import concurrent.futures
from loguru import logger

from market_data.adapters import CninfoAnnouncementsAdapter

class FilingsRunner:
    def __init__(self, config):
        self.config = config
        self.cninfo = CninfoAnnouncementsAdapter(config)

    def run(self, symbols: list, save_path: Path):
        def process_filings_symbol(sym):
            try:
                df_fil = self.cninfo.fetch_announcements(sym)
                if not df_fil.empty:
                    df_fil.to_json(save_path / f"{sym}_cninfo_filings.json", orient="records", force_ascii=False, indent=4)
                    logger.info(f"Saved cninfo filings list for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch cninfo filings for {sym}: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(process_filings_symbol, symbols))
