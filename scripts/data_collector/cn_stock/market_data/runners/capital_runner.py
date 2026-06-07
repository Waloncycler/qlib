from pathlib import Path
import concurrent.futures
from loguru import logger

from market_data.adapters import (
    MarginTradingAdapter,
    BlockTradeAdapter,
    ShareholderAdapter,
    DividendAdapter,
    StockFundFlow120dAdapter
)

class CapitalRunner:
    def __init__(self, config):
        self.config = config
        self.margin = MarginTradingAdapter(config)
        self.block = BlockTradeAdapter(config)
        self.holder = ShareholderAdapter(config)
        self.dividend = DividendAdapter(config)
        self.fflow120 = StockFundFlow120dAdapter(config)

    def run(self, symbols: list, save_path: Path):
        def process_capital_symbol(sym):
            try:
                df_m = self.margin.get_margin_trading(sym)
                if not df_m.empty:
                    df_m.to_csv(save_path / f"{sym}_margin_trading.csv", index=False)
                    logger.info(f"Saved Margin Trading for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch Margin Trading for {sym}: {e}")

            try:
                df_b = self.block.get_block_trades(sym)
                if not df_b.empty:
                    df_b.to_csv(save_path / f"{sym}_block_trades.csv", index=False)
                    logger.info(f"Saved Block Trades for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch Block Trades for {sym}: {e}")

            try:
                df_h = self.holder.get_shareholders(sym)
                if not df_h.empty:
                    df_h.to_csv(save_path / f"{sym}_shareholders.csv", index=False)
                    logger.info(f"Saved Shareholder structure for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch Shareholders for {sym}: {e}")

            try:
                df_d = self.dividend.get_dividends(sym)
                if not df_d.empty:
                    df_d.to_csv(save_path / f"{sym}_dividends.csv", index=False)
                    logger.info(f"Saved Dividends for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch Dividends for {sym}: {e}")

            try:
                df_ff = self.fflow120.fetch_daily_flow(sym)
                if not df_ff.empty:
                    df_ff.to_csv(save_path / f"{sym}_fund_flow_120d.csv", index=False)
                    logger.info(f"Saved 120d Fund Flow for {sym}")
            except Exception as e:
                logger.error(f"Failed to fetch 120d Fund Flow for {sym}: {e}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            list(executor.map(process_capital_symbol, symbols))
