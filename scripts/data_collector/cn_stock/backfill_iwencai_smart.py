import os
import sys
import yaml
import time
import requests
import logging
import pandas as pd
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

from adapters.research import IwencaiAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IwencaiSmartBackfill")

MAX_CALLS_PER_RUN = 190

def main():
    config_path = current_dir / "secret.yaml"
    if not config_path.exists():
        logger.error(f"Error: {config_path} not found.")
        sys.exit(1)
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
        
    adapter = IwencaiAdapter(config)
    if not adapter.api_key:
        logger.error("iWencai API key not found in config.")
        sys.exit(1)

    csv_path = current_dir / "../../../data/cn_stock/hierarchical/signals/market_sentiment.csv"
    if not csv_path.exists():
        logger.error(f"CSV not found: {csv_path}")
        sys.exit(1)

    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date", ascending=False) # prioritize recent dates

    api_calls_made = 0
    updated_rows = 0

    def query_iwencai_raw(query):
        nonlocal api_calls_made
        api_calls_made += 1
        headers = {
            "Authorization": f"Bearer {adapter.api_key}",
            "Content-Type": "application/json",
            **adapter._claw_headers(skill_id="data-query"),
        }
        payload = {
            "query": query,
            "page": "1",
            "limit": "10",
            "is_cache": "1",
            "expand_index": "true",
        }
        try:
            r = requests.post(f"{adapter.base_url}/v1/query2data", json=payload, headers=headers, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"Request failed for '{query}': {e}")
            return {}

    for idx, row in df.iterrows():
        if api_calls_made >= MAX_CALLS_PER_RUN:
            logger.info("Reached maximum API calls per run (190). Stopping.")
            break
            
        date_str = row["date"].strftime("%Y-%m-%d")
        c_date = row["date"].strftime("%Y年%m月%d日")
        modified = False
        
        # 1. Backfill Valuation (pe_median, pb_median)
        if pd.isna(row.get("pe_median")) or pd.isna(row.get("pb_median")):
            q = f"{c_date}A股中位数PE，中位数PB，中位数换手率"
            logger.info(f"[{api_calls_made}/{MAX_CALLS_PER_RUN}] Fetching valuation for {date_str}...")
            data = query_iwencai_raw(q)
            if data.get("datas") and len(data["datas"]) > 0:
                first_row = data["datas"][0]
                # Map keys correctly
                pe_key = next((k for k in first_row.keys() if "市盈率" in k and "中位" in k), None)
                pb_key = next((k for k in first_row.keys() if "市净率" in k and "中位" in k), None)
                turnover_key = next((k for k in first_row.keys() if "换手率" in k and "中位" in k), None)
                
                if pe_key and first_row[pe_key]:
                    df.at[idx, "pe_median"] = float(first_row[pe_key])
                    modified = True
                if pb_key and first_row[pb_key]:
                    df.at[idx, "pb_median"] = float(first_row[pb_key])
                    modified = True
                if turnover_key and first_row[turnover_key]:
                    df.at[idx, "turnover_median"] = float(first_row[turnover_key])
                    modified = True
            time.sleep(1) # throttle

        if api_calls_made >= MAX_CALLS_PER_RUN:
            break

        # 2. Backfill limit up count
        if pd.isna(row.get("uplimit_num")):
            q = f"{c_date}涨停"
            logger.info(f"[{api_calls_made}/{MAX_CALLS_PER_RUN}] Fetching limit up count for {date_str}...")
            data = query_iwencai_raw(q)
            if "row_count" in data:
                df.at[idx, "uplimit_num"] = int(data["row_count"])
                modified = True
            time.sleep(1) # throttle

        if modified:
            updated_rows += 1

    if updated_rows > 0:
        logger.info(f"Saving {updated_rows} updated rows back to CSV...")
        df = df.sort_values("date")
        df.to_csv(csv_path, index=False)
        logger.info("Done.")
    else:
        logger.info("No rows needed updating or API failed.")

if __name__ == "__main__":
    main()
