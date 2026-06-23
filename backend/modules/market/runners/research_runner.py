from pathlib import Path
import concurrent.futures
from loguru import logger

from modules.market.adapters import (
    EastmoneyReportAdapter,
    ThsConsensusAdapter,
    IwencaiAdapter
)

class ResearchRunner:
    def __init__(self, config):
        self.config = config
        self.em_rep = EastmoneyReportAdapter(config)
        self.ths_con = ThsConsensusAdapter(config)
        self.iwc = IwencaiAdapter(config)

    def run(self, symbols: list, save_path: Path):
        pdf_dir = save_path / "pdf"
        pdf_dir.mkdir(exist_ok=True)

        def process_research_symbol(sym):
            try:
                # Try to retrieve using report list
                df_rep = self.em_rep.fetch_report_list(sym)
                if not df_rep.empty:
                    df_rep.to_json(save_path / f"{sym}_reports.json", orient="records", force_ascii=False, indent=4)
                    logger.info(f"Saved Eastmoney research report list for {sym}")
                    
                    first_record = df_rep.iloc[0].to_dict()
                    pdf_path = self.em_rep.download_report_pdf(first_record, target_dir=str(pdf_dir))
                    if pdf_path:
                        logger.info(f"Successfully downloaded PDF for {sym} to {pdf_path}")
            except Exception as e:
                logger.error(f"Failed to fetch/download Eastmoney reports for {sym}: {e}")

            try:
                df_con = self.ths_con.fetch_consensus(sym)
                if not df_con.empty:
                    df_con.to_json(save_path / f"{sym}_ths_consensus.json", orient="records", force_ascii=False, indent=4)
                    logger.info(f"Saved THS Consensus for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch THS Consensus for {sym}: {e}")

            try:
                df_iwc = self.iwc.fetch_iwencai(f"{sym} 业绩预测")
                if not df_iwc.empty:
                    df_iwc.to_json(save_path / f"{sym}_iwencai.json", orient="records", force_ascii=False, indent=4)
                    logger.info(f"Saved iwencai search results for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch iwencai results for {sym}: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(process_research_symbol, symbols))
