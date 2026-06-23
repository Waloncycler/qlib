"""
Batch OHLCV data downloader for AI Report Signal Backtest.
Downloads daily OHLCV for all stocks in the AI Morning Reports universe,
using Baostock, and computes an equal-weight benchmark.
Uses disk cache to avoid redundant downloads.
"""
import os
import time
import json
import pandas as pd
from pathlib import Path
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.config import DATA_DIR, WORKSPACE_DIR

OHLCV_DIR = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv"
BENCHMARK_PATH = OHLCV_DIR / "_benchmark_equal_weight_all_a.csv"


def _symbol_to_baostock(symbol: str) -> str:
    """Convert Qlib-style symbol (SH600519) to baostock code (sh.600519)."""
    return symbol[:2].lower() + "." + symbol[2:]


def _download_single_stock(symbol: str, start_date: str, end_date: str) -> bool:
    """Download OHLCV for a single stock using baostock. Returns True on success."""
    import baostock as bs

    code = _symbol_to_baostock(symbol)
    out_path = OHLCV_DIR / f"{symbol}.csv"

    # Skip if already cached and reasonably fresh
    if out_path.exists():
        try:
            existing = pd.read_csv(out_path)
            if len(existing) > 0:
                last_date = str(existing["date"].max())
                if last_date >= end_date:
                    return True
        except Exception:
            pass

    try:
        rs = bs.query_history_k_data_plus(
            code,
            "date,code,open,high,low,close,volume,amount,pctChg,turn",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"  # Forward adjust (qfq)
        )
        
        if rs.error_code != '0':
            logger.warning(f"Baostock error for {symbol}: {rs.error_msg}")
            return False

        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            logger.warning(f"No data returned for {symbol}")
            return False

        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # Normalize types
        numeric_cols = ["open", "high", "low", "close", "volume", "amount", "pctChg", "turn"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df = df.rename(columns={
            "pctChg": "pct_change",
            "turn": "turnover",
        })
        df["symbol"] = symbol

        cols = ["date", "symbol", "open", "close", "high", "low", "volume", "amount", "pct_change", "turnover"]
        df = df[[c for c in cols if c in df.columns]]
        df.to_csv(out_path, index=False)
        return True

    except Exception as e:
        logger.warning(f"Failed to download {symbol}: {e}")
        return False


def build_equal_weight_benchmark(start_date: str, end_date: str, symbols: list) -> bool:
    """Build equal-weight benchmark from all downloaded stocks."""
    logger.info("Building equal-weight benchmark from universe...")
    
    all_dfs = []
    for sym in symbols:
        path = OHLCV_DIR / f"{sym}.csv"
        if path.exists():
            try:
                df = pd.read_csv(path, usecols=["date", "pct_change", "close"])
                df["symbol"] = sym
                all_dfs.append(df)
            except Exception:
                pass
                
    if not all_dfs:
        logger.error("No stock data found to build benchmark.")
        return False
        
    master_df = pd.concat(all_dfs, ignore_index=True)
    # Calculate daily mean return across all available stocks
    daily_returns = master_df.groupby("date")["pct_change"].mean() / 100.0
    
    # Construct an index starting at 1.0
    bench_df = pd.DataFrame({
        "date": daily_returns.index,
        "daily_return": daily_returns.values
    }).sort_values("date").reset_index(drop=True)
    
    # Generate synthetic OHLC values for the backtester
    navs = (1 + bench_df["daily_return"]).cumprod()
    bench_df["close"] = navs
    # Approximate open by shifting close
    bench_df["open"] = bench_df["close"] / (1 + bench_df["daily_return"])
    
    bench_df.to_csv(BENCHMARK_PATH, index=False)
    logger.info(f"Equal-weight benchmark built: {len(bench_df)} rows")
    return True


def download_all(symbols: list, start_date: str, end_date: str, max_workers: int = 4, delay: float = 0.0):
    """
    Download OHLCV for all symbols using baostock.
    Returns (success_count, fail_count, failed_symbols).
    """
    import baostock as bs
    
    OHLCV_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading OHLCV for {len(symbols)} symbols ({start_date} → {end_date})...")

    bs.login()
    
    success = 0
    failed = []

    for i, sym in enumerate(symbols):
        if sym.startswith("BJ"):
            continue
        ok = _download_single_stock(sym, start_date, end_date)
        if ok:
            success += 1
        else:
            failed.append(sym)

        if (i + 1) % 50 == 0:
            logger.info(f"Progress: {i+1}/{len(symbols)} (success={success}, failed={len(failed)})")

    bs.logout()
    
    logger.info(f"Download complete: {success} success, {len(failed)} failed")
    
    # Build benchmark after downloading all stocks
    build_equal_weight_benchmark(start_date, end_date, symbols)
    
    return success, len(failed), failed


def load_ohlcv(symbol: str) -> pd.DataFrame:
    """Load cached OHLCV data for a symbol."""
    path = OHLCV_DIR / f"{symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_benchmark() -> pd.DataFrame:
    """Load cached benchmark data."""
    if not BENCHMARK_PATH.exists():
        return pd.DataFrame()
    df = pd.read_csv(BENCHMARK_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df


if __name__ == "__main__":
    from modules.backtest.pool_generator import get_topic_universe
    universe, min_date, max_date = get_topic_universe()
    print(f"Universe: {len(universe)} symbols, {min_date} → {max_date}")
    download_all(universe, min_date, max_date)
