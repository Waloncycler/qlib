from pathlib import Path
import json
import concurrent.futures
from loguru import logger

from modules.market.adapters import (
    MootdxFinanceAdapter,
    MootdxF10Adapter,
    EastmoneyStockInfoAdapter,
    SinaFinancialReportAdapter
)

class FundamentalsRunner:
    def __init__(self, config):
        self.config = config
        self.m_fin = MootdxFinanceAdapter(config)
        self.m_f10 = MootdxF10Adapter(config)
        self.em_info = EastmoneyStockInfoAdapter(config)
        self.sina = SinaFinancialReportAdapter(config)

    def run(self, symbols: list, save_path: Path):
        def process_fundamentals_symbol(sym):
            try:
                df_fin = self.m_fin.get_financial_snapshot(sym)
                if not df_fin.empty:
                    df_fin.to_csv(save_path / f"{sym}_mootdx_finance.csv", index=False)
                    logger.info(f"Saved Mootdx Finance snapshot for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch Mootdx finance snapshot for {sym}: {e}")

            try:
                f10_text = self.m_f10.get_company_f10(sym)
                if f10_text:
                    with open(save_path / f"{sym}_mootdx_f10.txt", "w", encoding="utf-8") as f:
                        f.write(f10_text)
                    logger.info(f"Saved Mootdx F10 for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch Mootdx F10 text for {sym}: {e}")

            try:
                info = self.em_info.get_stock_info(sym)
                if info:
                    with open(save_path / f"{sym}_eastmoney_info.json", "w", encoding="utf-8") as f:
                        json.dump(info, f, ensure_ascii=False, indent=4)
                    logger.info(f"Saved Eastmoney Stock Info for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch Eastmoney Stock Info for {sym}: {e}")

            for rtype in ["lrb", "fzb", "llb"]:
                try:
                    df_stmt = self.sina.fetch_statement(sym, report_type=rtype)
                    if not df_stmt.empty:
                        df_stmt.to_csv(save_path / f"{sym}_sina_{rtype}.csv", index=False)
                        logger.info(f"Saved Sina financial statement {rtype} for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Sina statement {rtype} for {sym}: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(process_fundamentals_symbol, symbols))
