"""
fetch_ziruxing_sentiment.py
全面接管紫如星 (ziruxing.com) 的硬核打板情绪数据，并整合进 Qlib 数据体系。
覆盖 2022 年至今的全量数据。
"""
import time
import logging
import yaml
import sys
from pathlib import Path
import pandas as pd
import requests
from tqdm import tqdm

# 路径修复
CUR_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CUR_DIR.parent
sys.path.append(str(PROJECT_DIR))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ZiruxingFetcher")

def fetch_history(all_years=False):
    with open(PROJECT_DIR / "secret.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    token = config.get("zzshare_token")
    if not token:
        logger.error("Token missing in secret.yaml")
        return

    # 1. 确定抓取范围
    start_date = "2022-01-01"
    end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
    
    # 默认只抓取今年以提高速度。如果指定了 all_years=True，则从 2022 年开始全量抓取
    start_year = 2022 if all_years else pd.Timestamp.now().year
    years = range(start_year, pd.Timestamp.now().year + 1)
    all_data = []

    headers = {"sdk-key": token, "User-Agent": "Mozilla/5.0"}
    
    for year in years:
        y_start = f"{year}-01-01"
        y_end = f"{year}-12-31" if year < pd.Timestamp.now().year else end_date
        
        url = f"https://stock.ziruxing.com/sentiment/market/data?date1={y_start}&date2={y_end}"
        logger.info(f"Fetching Ziruxing data for {year}...")
        
        try:
            from modules.market.adapters.base import resilient_request
            res = resilient_request("get", url, headers=headers, timeout=20)
            if res.status_code == 200:
                data = res.json().get("data", [])
                if data:
                    df_year = pd.DataFrame(data)
                    df_year = df_year.rename(columns={"date1": "date"})
                    all_data.append(df_year)
                    logger.info(f"  -> Got {len(df_year)} records for {year}")
                else:
                    logger.warning(f"  -> No data for {year}")
            else:
                logger.error(f"  -> API Failed for {year}: {res.status_code}")
        except Exception as e:
            logger.error(f"  -> Error for {year}: {e}")
        
        time.sleep(1)

    if not all_data:
        logger.error("No data collected at all.")
        return

    df_final = pd.concat(all_data).drop_duplicates(subset=["date"]).sort_values("date")
    
    # 2. 整合进 market_sentiment.csv
    save_dir = Path("/Users/walox/qlib/data/cn_stock/hierarchical/signals")
    save_dir.mkdir(parents=True, exist_ok=True)
    target_csv = save_dir / "market_sentiment.csv"
    
    if target_csv.exists():
        df_orig = pd.read_csv(target_csv)
        df_orig["date"] = df_orig["date"].astype(str)
        # 合并：以 ziruxing 的硬核数据覆盖或补充原有列
        # Ziruxing 有一些字段与原有重名，我们选择保留 Ziruxing 的（通常更准）
        df_merged = df_final.set_index("date").combine_first(df_orig.set_index("date")).reset_index()
    else:
        df_merged = df_final

    df_merged.to_csv(target_csv, index=False)
    logger.info(f"Successfully integrated all-time Ziruxing data into {target_csv}")
    
    # 3. 注册为 Features (核心工作)
    # 我们创建一个专门的 metadata 文件记录这些字段，供 DataHandler 使用
    feature_meta = {
        "ziruxing_features": [c for c in df_final.columns if c != "date" and c != "id"],
        "description": "Hardcore Speculation Sentiment Indicators"
    }
    meta_path = save_dir / "market_feature_metadata.yaml"
    with open(meta_path, "w") as f:
        yaml.dump(feature_meta, f)
    logger.info(f"Registered {len(feature_meta['ziruxing_features'])} indicators in {meta_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Fetch all years since 2022")
    args = parser.parse_args()
    fetch_history(all_years=args.all)
