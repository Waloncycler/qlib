"""
计算每日创历史新高（上市以来最高价）和历史新低的个股数量
需要先运行 download_data 拉取全市场 A 股数据

用法:
    python scripts/data_collector/cn_stock/calc_alltime_high_low.py \
        --source_dir data/cn_stock/standard/source \
        --output data/cn_stock/hierarchical/signals/market_alltime_high_low.csv
"""
import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AlltimeHighLow")


def calc_alltime_high_low(source_dir: str, output_path: str):
    """
    遍历所有个股 CSV，计算每个交易日有多少只股票
    当日最高价 == 历史最高价（历史新高）
    当日最低价 == 历史最低价（历史新低）
    """
    source_dir = Path(source_dir)
    csv_files = list(source_dir.glob("*.csv"))
    logger.info(f"Found {len(csv_files)} stock CSV files in {source_dir}")

    if not csv_files:
        logger.error("No CSV files found. Please run download_data first.")
        return

    # Build a list of DataFrames: each with [date, is_new_high, is_new_low]
    all_records = []

    for i, fpath in enumerate(csv_files):
        try:
            df = pd.read_csv(fpath, parse_dates=["date"])
            if "close" not in df.columns or "date" not in df.columns:
                continue
            df = df.sort_values("date").reset_index(drop=True)

            # Rolling cumulative max/min of close price
            # is_new_high: today's close >= all previous closes (historical max)
            df["cum_max"] = df["close"].expanding().max()
            df["cum_min"] = df["close"].expanding().min()
            df["is_new_high"] = df["close"] >= df["cum_max"]
            df["is_new_low"] = df["close"] <= df["cum_min"]

            # Exclude the very first day (always a "new high")
            df.loc[df.index == 0, ["is_new_high", "is_new_low"]] = False

            all_records.append(df[["date", "is_new_high", "is_new_low"]])

            if (i + 1) % 500 == 0:
                logger.info(f"Processed {i + 1}/{len(csv_files)} stocks...")
        except Exception as e:
            logger.warning(f"Failed to process {fpath.name}: {e}")

    if not all_records:
        logger.error("No records computed.")
        return

    logger.info(f"Concatenating {len(all_records)} stock records...")
    combined = pd.concat(all_records, ignore_index=True)

    # Aggregate by date
    agg = combined.groupby("date").agg(
        new_high_alltime=("is_new_high", "sum"),
        new_low_alltime=("is_new_low", "sum"),
    ).reset_index()
    agg["date"] = agg["date"].dt.strftime("%Y-%m-%d")
    agg = agg.sort_values("date").reset_index(drop=True)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(output_path, index=False)
    logger.info(f"Saved {len(agg)} rows to {output_path}")
    logger.info(f"\nPreview (last 5 rows):\n{agg.tail(5).to_string()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate all-time high/low stocks per day")
    parser.add_argument("--source_dir", default="data/cn_stock/standard/source",
                        help="Directory containing individual stock CSVs")
    parser.add_argument("--output", default="data/cn_stock/hierarchical/signals/market_alltime_high_low.csv",
                        help="Output CSV path")
    args = parser.parse_args()
    calc_alltime_high_low(args.source_dir, args.output)
