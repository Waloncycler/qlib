# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sys
from pathlib import Path
import yaml
import fire
import pandas as pd
from loguru import logger

# Add paths to sys.path so we can import base data_collector classes and local modules
CUR_DIR = Path(__file__).resolve().parent
sys.path.append(str(CUR_DIR))
sys.path.append(str(CUR_DIR.parent.parent))

from data_collector.base import BaseCollector, BaseNormalize, BaseRun, Normalize
from adapters import *


class CnStockCollector(BaseCollector):
    """Collector for Chinese stocks supporting multiple pluggable adapters."""

    def __init__(
        self,
        save_dir: [str, Path],
        start=None,
        end=None,
        interval="1d",
        max_workers=1,
        max_collector_count=2,
        delay=0,
        check_data_length: int = None,
        limit_nums: int = None,
        source: str = "akshare",
        config_path: str = None,
    ):
        self.source = source.lower()
        self.config_path = config_path or str(CUR_DIR / "secret.yaml")
        self.config = self._load_config()

        # Instantiate selected adapter
        self.adapter = self._init_adapter()

        super(CnStockCollector, self).__init__(
            save_dir=save_dir,
            start=start,
            end=end,
            interval=interval,
            max_workers=max_workers,
            max_collector_count=max_collector_count,
            delay=delay,
            check_data_length=check_data_length,
            limit_nums=limit_nums,
        )

    def _load_config(self) -> dict:
        """Loads secret configurations (email, password, API tokens) from secret.yaml or env vars."""
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to load configuration from {self.config_path}: {e}")

        # Override with environment variables if present
        for key in ["zizi_email", "zizi_password", "zzshare_token"]:
            env_val = os.getenv(key.upper())
            if env_val:
                config[key] = env_val

        return config

    def _init_adapter(self):
        if self.source == "mootdx":
            return MootdxAdapter(self.config)
        elif self.source == "akshare":
            return AkshareAdapter(self.config)
        elif self.source == "zizizaizai":
            return ZizizaizaiAdapter(self.config)
        elif self.source == "eastmoney":
            return EastmoneyAdapter(self.config)
        elif self.source == "zzshare":
            return ZzshareAdapter(self.config)
        elif self.source == "tencentsina":
            return TencentSinaAdapter(self.config)
        else:
            raise ValueError(f"Unknown data source: {self.source}")

    def get_instrument_list(self) -> list:
        logger.info(f"Fetching stock list from source: {self.source}...")
        symbols = self.adapter.get_instrument_list()
        logger.info(f"Retrieved {len(symbols)} symbols from source.")
        return symbols

    def normalize_symbol(self, symbol: str) -> str:
        return to_qlib_symbol(symbol)

    def get_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        logger.info(f"Fetching data for {symbol} ({interval}) from {start_datetime} to {end_datetime} via {self.source}")
        return self.adapter.fetch_symbol_data(symbol, interval, start_datetime, end_datetime)

    def download_layer(
        self,
        layer: str,
        symbol: str = "SH600519",
        save_dir: [str, Path] = "./data/cn_stock/hierarchical",
    ):
        import json
        layer = layer.lower()
        save_path = Path(save_dir) / layer
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Determine symbols to query
        if symbol.lower() == "all":
            symbols = self.get_instrument_list()
            if self.limit_nums:
                symbols = symbols[:self.limit_nums]
        else:
            symbols = [symbol]

        logger.info(f"Downloading layer '{layer}' for {len(symbols)} symbols. Output directory: {save_path}")

        if layer == "market":
            baidu = BaiduKlineAdapter(self.config)
            ts = TencentSinaAdapter(self.config)
            mdx = MootdxAdapter(self.config)
            em = EastmoneyAdapter(self.config)
            
            for sym in symbols:
                try:
                    df_k = baidu.fetch_symbol_data(sym, "1d", pd.Timestamp("2026-01-01"), pd.Timestamp.now())
                    if not df_k.empty:
                        df_k.to_csv(save_path / f"{sym}_baidu_kline.csv", index=False)
                        logger.info(f"Saved Baidu KLine for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Baidu Kline for {sym}: {e}")

                try:
                    df_ts = ts.fetch_symbol_data(sym, "1d", pd.Timestamp("2026-01-01"), pd.Timestamp.now())
                    if not df_ts.empty:
                        df_ts.to_csv(save_path / f"{sym}_tencent_sina_kline.csv", index=False)
                        logger.info(f"Saved Tencent/Sina KLine for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Tencent/Sina KLine for {sym}: {e}")

                try:
                    quotes = ts.fetch_tencent_quotes([sym])
                    if quotes:
                        with open(save_path / f"{sym}_tencent_quotes.json", "w", encoding="utf-8") as f:
                            json.dump(quotes, f, ensure_ascii=False, indent=4)
                        logger.info(f"Saved Tencent Quotes for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Tencent quotes for {sym}: {e}")

                try:
                    df_em = em.fetch_symbol_data(sym, "1d", pd.Timestamp.now().normalize(), pd.Timestamp.now())
                    if not df_em.empty:
                        df_em.to_csv(save_path / f"{sym}_eastmoney_snapshot.csv", index=False)
                        logger.info(f"Saved Eastmoney snapshot for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Eastmoney snapshot for {sym}: {e}")

        elif layer == "signals":
            ths_hot = ThsHotReasonAdapter(self.config)
            ths_north = ThsNorthboundAdapter(self.config)
            baidu_concept = BaiduConceptAdapter(self.config)
            em_flow = EastmoneyFundFlowAdapter(self.config)
            dragon_tiger = DragonTigerAdapter(self.config)
            lockup = LockupAdapter(self.config)
            em_ind = EastmoneyIndustryAdapter(self.config)
            sentiment_adapter = MarketSentimentAdapter(self.config)

            try:
                sent_data = sentiment_adapter.get_market_sentiment()
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
                    # Ensure columns order is clean
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
                    # Filter only columns we actually have to prevent crash
                    cols_order = [c for c in cols_order if c in df_combined.columns]
                    df_combined = df_combined[cols_order]

                    df_combined.to_csv(csv_path, index=False)
                    logger.info(f"Saved market sentiment data for date {sent_data['date']} to {csv_path}")
            except Exception as e:
                logger.error(f"Failed to process market sentiment data: {e}")


            try:
                df_hot = ths_hot.get_hot_reasons()
                if not df_hot.empty:
                    df_hot.to_csv(save_path / "ths_hot_reasons.csv", index=False)
                    logger.info("Saved THS Hot Reasons")
            except Exception as e:
                logger.error(f"Failed to fetch THS Hot Reasons: {e}")

            try:
                df_north = ths_north.fetch_realtime_minute_flow()
                if not df_north.empty:
                    df_north.to_csv(save_path / "ths_northbound_realtime_minute.csv", index=False)
                    logger.info("Saved THS Northbound Realtime Minute flow")
            except Exception as e:
                logger.error(f"Failed to fetch Northbound minute flow: {e}")
            
            try:
                df_north_hist = ths_north.load_cached_history()
                if not df_north_hist.empty:
                    df_north_hist.to_csv(save_path / "ths_northbound_history.csv", index=False)
                    logger.info("Saved THS Northbound historical flow")
            except Exception as e:
                logger.error(f"Failed to fetch Northbound history: {e}")

            try:
                df_ind = em_ind.get_industry_board_rankings()
                if not df_ind.empty:
                    df_ind.to_csv(save_path / "eastmoney_industry_rankings.csv", index=False)
                    logger.info("Saved Eastmoney Industry rankings")
            except Exception as e:
                logger.error(f"Failed to fetch Industry rankings: {e}")

            for sym in symbols:
                try:
                    concepts = baidu_concept.get_concept_blocks(sym)
                    if concepts:
                        with open(save_path / f"{sym}_baidu_concepts.json", "w", encoding="utf-8") as f:
                            json.dump(concepts, f, ensure_ascii=False, indent=4)
                        logger.info(f"Saved Baidu Concepts for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Baidu Concepts for {sym}: {e}")

                try:
                    df_ff = em_flow.fetch_minute_flow(sym)
                    if not df_ff.empty:
                        df_ff.to_csv(save_path / f"{sym}_eastmoney_minute_flow.csv", index=False)
                        logger.info(f"Saved Eastmoney minute fund flow for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Eastmoney minute fund flow for {sym}: {e}")

                try:
                    today_str = pd.Timestamp.now().strftime("%Y-%m-%d")
                    dt_info = dragon_tiger.get_stock_dragon_tiger(sym, today_str)
                    if dt_info:
                        with open(save_path / f"{sym}_dragon_tiger.json", "w", encoding="utf-8") as f:
                            json.dump(dt_info, f, ensure_ascii=False, indent=4)
                        logger.info(f"Saved Dragon Tiger for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Dragon Tiger for {sym}: {e}")

                try:
                    today_str = pd.Timestamp.now().strftime("%Y-%m-%d")
                    lock_info = lockup.get_lockup_expiry(sym, today_str)
                    if lock_info:
                        with open(save_path / f"{sym}_lockup_expiry.json", "w", encoding="utf-8") as f:
                            json.dump(lock_info, f, ensure_ascii=False, indent=4)
                        logger.info(f"Saved Lockup Expiry for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Lockup Expiry for {sym}: {e}")

        elif layer == "capital":
            margin = MarginTradingAdapter(self.config)
            block = BlockTradeAdapter(self.config)
            holder = ShareholderAdapter(self.config)
            dividend = DividendAdapter(self.config)
            fflow120 = StockFundFlow120dAdapter(self.config)

            for sym in symbols:
                try:
                    df_m = margin.get_margin_trading(sym)
                    if not df_m.empty:
                        df_m.to_csv(save_path / f"{sym}_margin_trading.csv", index=False)
                        logger.info(f"Saved Margin Trading for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Margin Trading for {sym}: {e}")

                try:
                    df_b = block.get_block_trades(sym)
                    if not df_b.empty:
                        df_b.to_csv(save_path / f"{sym}_block_trades.csv", index=False)
                        logger.info(f"Saved Block Trades for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Block Trades for {sym}: {e}")

                try:
                    df_h = holder.get_shareholders(sym)
                    if not df_h.empty:
                        df_h.to_csv(save_path / f"{sym}_shareholders.csv", index=False)
                        logger.info(f"Saved Shareholder structure for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Shareholders for {sym}: {e}")

                try:
                    df_d = dividend.get_dividends(sym)
                    if not df_d.empty:
                        df_d.to_csv(save_path / f"{sym}_dividends.csv", index=False)
                        logger.info(f"Saved Dividends for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Dividends for {sym}: {e}")

                try:
                    df_ff = fflow120.fetch_daily_flow(sym)
                    if not df_ff.empty:
                        df_ff.to_csv(save_path / f"{sym}_fund_flow_120d.csv", index=False)
                        logger.info(f"Saved 120d Fund Flow for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch 120d Fund Flow for {sym}: {e}")

        elif layer == "fundamentals":
            m_fin = MootdxFinanceAdapter(self.config)
            m_f10 = MootdxF10Adapter(self.config)
            em_info = EastmoneyStockInfoAdapter(self.config)
            sina = SinaFinancialReportAdapter(self.config)

            for sym in symbols:
                try:
                    df_fin = m_fin.get_financial_snapshot(sym)
                    if not df_fin.empty:
                        df_fin.to_csv(save_path / f"{sym}_mootdx_finance.csv", index=False)
                        logger.info(f"Saved Mootdx Finance snapshot for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Mootdx finance snapshot for {sym}: {e}")

                try:
                    f10_text = m_f10.get_company_f10(sym)
                    if f10_text:
                        with open(save_path / f"{sym}_mootdx_f10.txt", "w", encoding="utf-8") as f:
                            f.write(f10_text)
                        logger.info(f"Saved Mootdx F10 for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Mootdx F10 text for {sym}: {e}")

                try:
                    info = em_info.get_stock_info(sym)
                    if info:
                        with open(save_path / f"{sym}_eastmoney_info.json", "w", encoding="utf-8") as f:
                            json.dump(info, f, ensure_ascii=False, indent=4)
                        logger.info(f"Saved Eastmoney Stock Info for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Eastmoney Stock Info for {sym}: {e}")

                for rtype in ["lrb", "fzb", "llb"]:
                    try:
                        df_stmt = sina.fetch_statement(sym, report_type=rtype)
                        if not df_stmt.empty:
                            df_stmt.to_csv(save_path / f"{sym}_sina_{rtype}.csv", index=False)
                            logger.info(f"Saved Sina financial statement {rtype} for {sym}")
                    except Exception as e:
                        logger.error(f"Failed to fetch Sina statement {rtype} for {sym}: {e}")

        elif layer == "news":
            em_news = EastmoneyStockNewsAdapter(self.config)
            cls_tel = ClsTelegraphAdapter(self.config)
            em_global = EastmoneyGlobalNewsAdapter(self.config)

            try:
                df_tel = cls_tel.fetch_telegraph()
                if not df_tel.empty:
                    df_tel.to_json(save_path / "cls_telegraph.json", orient="records", force_ascii=False, indent=4)
                    logger.info("Saved CLS Telegraph Stream")
            except Exception as e:
                logger.error(f"Failed to fetch CLS telegraph: {e}")

            try:
                df_gl = em_global.fetch_global_news()
                if not df_gl.empty:
                    df_gl.to_json(save_path / "eastmoney_global_news.json", orient="records", force_ascii=False, indent=4)
                    logger.info("Saved Eastmoney Global News Stream")
            except Exception as e:
                logger.error(f"Failed to fetch Eastmoney global news: {e}")

            for sym in symbols:
                try:
                    df_n = em_news.fetch_stock_news(sym)
                    if not df_n.empty:
                        df_n.to_json(save_path / f"{sym}_eastmoney_news.json", orient="records", force_ascii=False, indent=4)
                        logger.info(f"Saved Eastmoney stock news for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch Eastmoney stock news for {sym}: {e}")

        elif layer == "research":
            em_rep = EastmoneyReportAdapter(self.config)
            ths_con = ThsConsensusAdapter(self.config)
            iwc = IwencaiAdapter(self.config)

            pdf_dir = save_path / "pdf"
            pdf_dir.mkdir(exist_ok=True)

            for sym in symbols:
                try:
                    # Try to retrieve using report list
                    df_rep = em_rep.fetch_report_list(sym)
                    if not df_rep.empty:
                        df_rep.to_json(save_path / f"{sym}_reports.json", orient="records", force_ascii=False, indent=4)
                        logger.info(f"Saved Eastmoney research report list for {sym}")
                        
                        first_record = df_rep.iloc[0].to_dict()
                        pdf_path = em_rep.download_report_pdf(first_record, target_dir=str(pdf_dir))
                        if pdf_path:
                            logger.info(f"Successfully downloaded PDF for {sym} to {pdf_path}")
                except Exception as e:
                    logger.error(f"Failed to fetch/download Eastmoney reports for {sym}: {e}")

                try:
                    df_con = ths_con.fetch_consensus(sym)
                    if not df_con.empty:
                        df_con.to_json(save_path / f"{sym}_ths_consensus.json", orient="records", force_ascii=False, indent=4)
                        logger.info(f"Saved THS Consensus for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch THS Consensus for {sym}: {e}")

                try:
                    df_iwc = iwc.fetch_iwencai(f"{sym} 业绩预测")
                    if not df_iwc.empty:
                        df_iwc.to_json(save_path / f"{sym}_iwencai.json", orient="records", force_ascii=False, indent=4)
                        logger.info(f"Saved iwencai search results for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch iwencai results for {sym}: {e}")

        elif layer == "filings":
            cninfo = CninfoAnnouncementsAdapter(self.config)

            for sym in symbols:
                try:
                    df_fil = cninfo.fetch_announcements(sym)
                    if not df_fil.empty:
                        df_fil.to_json(save_path / f"{sym}_cninfo_filings.json", orient="records", force_ascii=False, indent=4)
                        logger.info(f"Saved cninfo filings list for {sym}")
                except Exception as e:
                    logger.error(f"Failed to fetch cninfo filings for {sym}: {e}")

        else:
            raise ValueError(f"Unknown hierarchical layer: {layer}")


class CnStockNormalize(BaseNormalize):
    """Normalize raw Chinese Stock data files to standard format."""

    COLUMNS = ["open", "close", "high", "low", "volume", "factor"]

    def _get_calendar_list(self) -> list:
        # Standard A-share business days
        # We can dynamically retrieve the calendar, but for normalization we return empty or standard range
        return []

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        df = df.copy()
        
        # Ensure mandatory columns
        if "date" not in df.columns:
            # Fallback if datetime was used
            for col in ["datetime", "trade_date"]:
                if col in df.columns:
                    df = df.rename(columns={col: "date"})
                    break
        
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates("date")
        
        # Parse numeric columns
        for col in ["open", "close", "high", "low", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                df[col] = 0.0

        if "factor" not in df.columns:
            df["factor"] = 1.0
        else:
            df["factor"] = pd.to_numeric(df["factor"], errors="coerce").fillna(1.0)
            
        # Calculate daily change percent
        if "change" not in df.columns and "close" in df.columns:
            df["change"] = df["close"].pct_change().fillna(0.0)

        # Reorder columns
        out_cols = ["date", "open", "high", "low", "close", "volume", "factor", "symbol"]
        for col in df.columns:
            if col not in out_cols:
                out_cols.append(col)
                
        return df[out_cols]


class Run(BaseRun):
    """Command Line Runner for Multi-source Chinese Stock Data Collector."""

    def __init__(
        self,
        source_dir=None,
        normalize_dir=None,
        max_workers=1,
        interval="1d",
        source="akshare",
        config_path=None,
    ):
        self.source = source
        self.config_path = config_path
        super(Run, self).__init__(source_dir, normalize_dir, max_workers, interval)

    @property
    def collector_class_name(self):
        return "CnStockCollector"

    @property
    def normalize_class_name(self):
        return "CnStockNormalize"

    @property
    def default_base_dir(self) -> Path:
        return CUR_DIR

    def download_data(
        self,
        max_collector_count=2,
        delay=0,
        start=None,
        end=None,
        check_data_length=None,
        limit_nums=None,
    ):
        """Download data from the selected source."""
        # Instantiate and run
        collector = CnStockCollector(
            save_dir=self.source_dir,
            start=start,
            end=end,
            interval=self.interval,
            max_workers=self.max_workers,
            max_collector_count=max_collector_count,
            delay=delay,
            check_data_length=check_data_length,
            limit_nums=limit_nums,
            source=self.source,
            config_path=self.config_path,
        )
        collector.collector_data()

    def normalize_data(self, date_field_name: str = "date", symbol_field_name: str = "symbol", **kwargs):
        """Normalize downloaded raw CSVs."""
        norm_class = CnStockNormalize
        norm_executor = Normalize(
            source_dir=self.source_dir,
            target_dir=self.normalize_dir,
            normalize_class=norm_class,
            max_workers=self.max_workers,
            date_field_name=date_field_name,
            symbol_field_name=symbol_field_name,
            **kwargs,
        )
        norm_executor.normalize()

    def download_layer(
        self,
        layer: str,
        symbol: str = "SH600519",
        save_dir: str = "./data/cn_stock/hierarchical",
        limit_nums: int = None,
    ):
        """Download layer-specific data (signals, capital, fundamentals, news, research, filings, market)."""
        collector = CnStockCollector(
            save_dir=self.source_dir,
            limit_nums=limit_nums,
            source=self.source,
            config_path=self.config_path,
        )
        collector.download_layer(layer=layer, symbol=symbol, save_dir=save_dir)


if __name__ == "__main__":
    fire.Fire(Run)
