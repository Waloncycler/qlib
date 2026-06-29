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
PROJECT_DIR = CUR_DIR.parent
sys.path.append(str(PROJECT_DIR))
sys.path.append(str(PROJECT_DIR.parent / "scripts"))

from data_collector.base import BaseCollector, BaseNormalize, BaseRun, Normalize
from modules.market.adapters import (
    MootdxAdapter,
    AkshareAdapter,
    ZizizaizaiAdapter,
    EastmoneyAdapter,
    ZzshareAdapter,
    TencentSinaAdapter,
    to_qlib_symbol,
)
from core.config import global_v8_lock

_instrument_list_cache = None


class CnStockCollector(BaseCollector):
    """Collector for Chinese stocks supporting multiple pluggable adapters."""

    def __init__(
        self,
        save_dir: str | Path,
        start=None,
        end=None,
        interval="1d",
        max_workers=1,
        max_collector_count=2,
        delay=0,
        check_data_length: int | None = None,
        limit_nums: int | None = None,
        source: str = "akshare",
        config_path: str | None = None,
    ):
        self.source = source.lower()
        self.config_path = config_path or str(PROJECT_DIR / "secret.yaml")
        self.limit_nums = limit_nums
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
            check_data_length=check_data_length,  # type: ignore
            limit_nums=limit_nums,  # type: ignore
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
        global _instrument_list_cache
        # If standard source directory contains existing files, only update those to save time and API quota
        for path_str in [getattr(self, "save_dir", ""), str(PROJECT_DIR.parent / "data" / "cn_stock" / "standard" / "source")]:
            if path_str:
                p = Path(path_str)
                if p.exists():
                    csv_files = list(p.glob("*.csv"))
                    if csv_files:
                        symbols = [f.stem for f in csv_files]
                        logger.info(f"Existing CSV files found in target directory. Restricting update to: {symbols}")
                        return symbols

        with global_v8_lock:
            if _instrument_list_cache is not None:
                return _instrument_list_cache

            logger.info(f"Fetching stock list from source: {self.source}...")
            symbols = self.adapter.get_instrument_list()
            logger.info(f"Retrieved {len(symbols)} symbols from source.")
            _instrument_list_cache = symbols
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
        save_dir: str | Path = "./data/cn_stock/hierarchical",
        start_date: pd.Timestamp | None = None
    ):
        layer = layer.lower()
        save_path = Path(save_dir) / layer
        save_path.mkdir(parents=True, exist_ok=True)
        
        # Determine symbols to query
        is_all = (symbol.lower() == "all")
        if is_all:
            symbols = self.get_instrument_list()
            if self.limit_nums:
                symbols = symbols[:self.limit_nums]
        else:
            symbols = [symbol]

        logger.info(f"Downloading layer '{layer}' for {len(symbols)} symbols. Output directory: {save_path}")

        from modules.market.runners import (
            MarketRunner, SignalsRunner, CapitalRunner, FundamentalsRunner, NewsRunner, ResearchRunner, FilingsRunner
        )

        if layer == "market":
            MarketRunner(self.config).run(symbols, save_path, start_date)  # type: ignore
        elif layer == "signals":
            SignalsRunner(self.config).run(symbols, save_path, is_all)
        elif layer == "capital":
            CapitalRunner(self.config).run(symbols, save_path)
        elif layer == "fundamentals":
            FundamentalsRunner(self.config).run(symbols, save_path)
        elif layer == "news":
            NewsRunner(self.config).run(symbols, save_path, is_all)
        elif layer == "research":
            ResearchRunner(self.config).run(symbols, save_path)
        elif layer == "filings":
            FilingsRunner(self.config).run(symbols, save_path)
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
        
        df["date"] = pd.to_datetime(df["date"], format="mixed")
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
            df["factor"] = pd.to_numeric(df["factor"], errors="coerce").fillna(1.0)  # type: ignore
            
        # Calculate daily change percent
        if "change" not in df.columns and "close" in df.columns:
            df["change"] = df["close"].pct_change().fillna(0.0)

        # Reorder columns
        out_cols = ["date", "open", "high", "low", "close", "volume", "factor", "symbol"]
        for col in df.columns:
            if col not in out_cols:
                out_cols.append(col)
                
        return df[out_cols]  # type: ignore


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
        **kwargs,
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
        limit_nums: int | None = None,
        start_date: str | None = None
    ):
        """Download layer-specific data (signals, capital, fundamentals, news, research, filings, market)."""
        collector = CnStockCollector(
            save_dir=self.source_dir,
            limit_nums=limit_nums,
            source=self.source,
            config_path=self.config_path,
        )
        sd = pd.Timestamp(start_date) if start_date else None
        collector.download_layer(layer=layer, symbol=symbol, save_dir=save_dir, start_date=sd)  # type: ignore


if __name__ == "__main__":
    fire.Fire(Run)
