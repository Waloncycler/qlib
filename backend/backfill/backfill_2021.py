"""
backfill_2021.py
把 market_sentiment.csv 中 Charts 2~7 的历史数据补填至 2021-01-04 起。

数据来源:
  - Ziruxing API (2021~至今): uplimit_num, downlimit_num, zb_num, lb_2_num, lb_h_num, max_lb_num
  - Baostock 全市场日线 (计算): high20/60/120, low20/60/120

运行:
    /Users/walox/qlib/.venv/bin/python backend/backfill_2021.py
"""
import time
import logging
import requests
import yaml
from pathlib import Path
import pandas as pd
import numpy as np
import baostock as bs

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Backfill2021")

CUR_DIR = Path(__file__).resolve().parent
SIGNALS_DIR = CUR_DIR / "../../../data/cn_stock/hierarchical/signals"
SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
TARGET_CSV = SIGNALS_DIR / "market_sentiment.csv"
START_DATE = "2021-01-01"


def fetch_ziruxing_from_2021(token: str) -> pd.DataFrame:
    """Fetch all Ziruxing sentiment data from 2021 to today using quarterly chunks."""
    headers = {"sdk-key": token, "User-Agent": "Mozilla/5.0"}
    all_data = []
    today = pd.Timestamp.now().date()

    # Build list of quarterly ranges from 2021-01-01 to today
    quarters = []
    start = pd.Timestamp("2021-01-01").date()
    while start <= today:
        q_end = (pd.Timestamp(start) + pd.DateOffset(months=3) - pd.DateOffset(days=1)).date()
        q_end = min(q_end, today)
        quarters.append((str(start), str(q_end)))
        start = (pd.Timestamp(q_end) + pd.DateOffset(days=1)).date()

    logger.info(f"Fetching Ziruxing in {len(quarters)} quarterly chunks from 2021-01-01...")
    for i, (q_start, q_end) in enumerate(quarters):
        url = f"https://stock.ziruxing.com/sentiment/market/data?date1={q_start}&date2={q_end}"
        logger.info(f"  [{i+1}/{len(quarters)}] {q_start} ~ {q_end}")
        for attempt in range(3):
            try:
                res = requests.get(url, headers=headers, timeout=30)
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    if data:
                        df = pd.DataFrame(data)
                        df = df.rename(columns={"date1": "date"})
                        all_data.append(df)
                        logger.info(f"    -> {len(df)} records")
                    else:
                        logger.warning(f"    -> No data returned")
                    break
                else:
                    logger.error(f"    -> HTTP {res.status_code}")
                    break
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"    -> Attempt {attempt+1} failed: {e}, retrying...")
                    time.sleep(3)
                else:
                    logger.error(f"    -> All attempts failed: {e}")
        time.sleep(0.5)

    if not all_data:
        return pd.DataFrame()
    df_all = pd.concat(all_data).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    logger.info(f"Ziruxing total: {len(df_all)} rows ({df_all['date'].iloc[0]} ~ {df_all['date'].iloc[-1]})")
    return df_all


def fetch_all_stocks_baostock() -> list:
    """Get the full list of A-share stocks (type==1, status==1 = active ordinary shares)."""
    logger.info("Fetching A-share stock list from baostock...")
    rs = bs.query_stock_basic()  # no type_ param in this version
    stocks = []
    while (rs.error_code == '0') and rs.next():
        row = rs.get_row_data()
        # fields: code, code_name, ipoDate, outDate, type, status
        # type '1' = 普通股, status '1' = 上市
        if len(row) >= 6 and row[4] == '1' and row[5] == '1':
            stocks.append(row[0])
    logger.info(f"Got {len(stocks)} active A-share stocks")
    return stocks


def fetch_daily_close_baostock(code: str, start: str, end: str) -> pd.DataFrame:
    """Fetch daily close prices for a single stock."""
    rs = bs.query_history_k_data_plus(
        code, "date,close",
        start_date=start, end_date=end,
        frequency="d", adjustflag="3"
    )
    if rs.error_code != '0':
        return pd.DataFrame()
    rows = []
    while rs.next():
        rows.append(rs.get_row_data())
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "close"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def _baostock_reconnect():
    """Logout and login again to reset dropped socket connection."""
    try:
        bs.logout()
    except Exception:
        pass
    time.sleep(1)
    for attempt in range(5):
        lg = bs.login()
        if lg.error_code == '0':
            return True
        logger.warning(f"  Re-login attempt {attempt+1} failed: {lg.error_msg}")
        time.sleep(2)
    return False


def compute_breadth(stocks: list, start: str = "2020-06-01") -> pd.DataFrame:
    """Download closes and compute rolling-window high/low breadth counts.
    
    Re-logins baostock every RECONNECT_EVERY stocks to prevent Broken Pipe
    connection drops that silently return empty data.
    """
    RECONNECT_EVERY = 300  # re-login every N stocks to keep connection alive

    end = pd.Timestamp.now().strftime("%Y-%m-%d")
    logger.info(f"Downloading closes for {len(stocks)} stocks ({start} ~ {end})...")
    all_close = {}
    errors = 0

    for i, code in enumerate(stocks):
        # Periodic reconnect to prevent socket from dying silently
        if i > 0 and i % RECONNECT_EVERY == 0:
            logger.info(f"  [{i}/{len(stocks)}] Reconnecting baostock... fetched={len(all_close)}, errors={errors}")
            _baostock_reconnect()
            time.sleep(1)

        # Fetch with one auto-retry on empty result (possible stale connection)
        df = pd.DataFrame()
        for attempt in range(2):
            try:
                df = fetch_daily_close_baostock(code, start, end)
                if not df.empty:
                    break
                elif attempt == 0:
                    # Empty might mean dead connection — reconnect and retry
                    _baostock_reconnect()
            except Exception as e:
                if attempt == 0:
                    _baostock_reconnect()
                else:
                    errors += 1

        if not df.empty:
            all_close[code] = df.set_index("date")["close"]

        if (i + 1) % 500 == 0:
            logger.info(f"  Progress {i+1}/{len(stocks)}, fetched={len(all_close)}, errors={errors}")

    logger.info(f"Download complete: {len(all_close)}/{len(stocks)} stocks, errors={errors}")
    if not all_close:
        return pd.DataFrame()

    logger.info("Building wide price matrix...")
    close_wide = pd.DataFrame(all_close).sort_index()

    logger.info("Computing rolling breadth (high20/60/120, low20/60/120)...")
    parts = []
    for window in [20, 60, 120]:
        roll_max = close_wide.rolling(window=window, min_periods=window).max()
        roll_min = close_wide.rolling(window=window, min_periods=window).min()
        high_cnt = (close_wide >= roll_max).sum(axis=1).rename(f"high{window}")
        low_cnt  = (close_wide <= roll_min).sum(axis=1).rename(f"low{window}")
        parts += [high_cnt, low_cnt]

    breadth = pd.concat(parts, axis=1)
    breadth = breadth[breadth.index >= pd.Timestamp(START_DATE)]
    breadth.index = breadth.index.strftime("%Y-%m-%d")
    breadth.index.name = "date"
    breadth = breadth.reset_index()
    for col in ["high20", "high60", "high120", "low20", "low60", "low120"]:
        breadth[col] = breadth[col].astype(int)

    logger.info(f"Breadth: {len(breadth)} rows ({breadth['date'].iloc[0]} ~ {breadth['date'].iloc[-1]})")
    return breadth


def merge_into_sentiment(df_ziruxing: pd.DataFrame, df_breadth: pd.DataFrame):
    """Merge new data into existing market_sentiment.csv."""
    df = pd.read_csv(TARGET_CSV)
    df["date"] = df["date"].astype(str)
    logger.info(f"Original CSV: {len(df)} rows")

    # --- Ziruxing ---
    if not df_ziruxing.empty:
        df_ziruxing["date"] = df_ziruxing["date"].astype(str)
        zi_map = df_ziruxing.set_index("date")

        # Ensure all ziruxing columns exist
        zi_cols = [c for c in df_ziruxing.columns if c not in ("date", "id")]
        for col in zi_cols:
            if col not in df.columns:
                df[col] = np.nan

        # Field mapping (from Eastmoney convention to Ziruxing)
        field_map = {
            "limit_up_count": "uplimit_num",
            "real_limit_up_count": "uplimit_n_num",
            "limit_down_count": "downlimit_num",
            "broken_limit_up_count": "zb_num",
            "consecutive_limit_up_2_count": "lb_2_num",
            "consecutive_limit_up_3_plus_count": "lb_h_num",
            "highest_consecutive_limit_up": "max_lb_num",
        }

        for idx, row in df.iterrows():
            d = row["date"]
            if d not in zi_map.index:
                continue
            zi = zi_map.loc[d]

            # Patch composite Eastmoney-style fields
            for dst, src in field_map.items():
                if dst not in df.columns:
                    df[dst] = np.nan
                if pd.isna(df.at[idx, dst]):
                    v = zi.get(src, np.nan)
                    if not pd.isna(v):
                        df.at[idx, dst] = v

            # Copy raw ziruxing fields
            for col in zi_cols:
                cur = df.at[idx, col]
                if pd.isna(cur) or cur == 0:
                    v = zi.get(col, np.nan)
                    if not pd.isna(v) and v != 0:
                        df.at[idx, col] = v

        # Compute broken_limit_up_rate where still missing
        if "broken_limit_up_rate" not in df.columns:
            df["broken_limit_up_rate"] = np.nan
        for idx, row in df.iterrows():
            d = row["date"]
            if not pd.isna(df.at[idx, "broken_limit_up_rate"]):
                continue
            if d not in zi_map.index:
                continue
            zi = zi_map.loc[d]
            zb = float(zi.get("zb_num", 0) or 0)
            zt = float(zi.get("uplimit_num", 0) or 0)
            total = zb + zt
            if total > 0:
                df.at[idx, "broken_limit_up_rate"] = round(zb / total, 4)

        logger.info("Ziruxing merge done.")

    # --- Breadth ---
    if not df_breadth.empty:
        df_breadth["date"] = df_breadth["date"].astype(str)
        brd_map = df_breadth.set_index("date")
        for col in ["high20", "high60", "high120", "low20", "low60", "low120"]:
            if col not in df.columns:
                df[col] = np.nan
        for idx, row in df.iterrows():
            d = row["date"]
            if d not in brd_map.index:
                continue
            for col in ["high20", "high60", "high120", "low20", "low60", "low120"]:
                if pd.isna(df.at[idx, col]):
                    v = brd_map.at[d, col]
                    if not pd.isna(v):
                        df.at[idx, col] = int(v)
        logger.info("Breadth merge done.")

    df = df.sort_values("date").reset_index(drop=True)
    df.to_csv(TARGET_CSV, index=False)
    logger.info(f"Saved {len(df)} rows -> {TARGET_CSV}")

    # Coverage report
    key_cols = ["limit_up_count", "limit_down_count", "broken_limit_up_rate",
                "consecutive_limit_up_2_count", "highest_consecutive_limit_up",
                "high20", "high60", "high120", "low20", "low60", "low120"]
    for col in key_cols:
        if col in df.columns:
            n = df[col].notna().sum()
            logger.info(f"  {col:42s}: {n}/{len(df)} non-null")


def main():
    with open(CUR_DIR / "secret.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    token = cfg.get("zzshare_token", "")

    logger.info("=" * 60)
    logger.info("Step 1/3: Ziruxing 2021~今天 (quarterly chunks)")
    logger.info("=" * 60)
    df_zi = fetch_ziruxing_from_2021(token)

    logger.info("=" * 60)
    logger.info("Step 2/3: Baostock 全市场广度 high/low 20/60/120")
    logger.info("=" * 60)
    # Initial login; compute_breadth will re-login every RECONNECT_EVERY stocks
    lg = bs.login()
    logger.info(f"Initial baostock login: {lg.error_msg}")
    try:
        stocks = fetch_all_stocks_baostock()
        df_brd = compute_breadth(stocks, start="2020-06-01")
    finally:
        try:
            bs.logout()
        except Exception:
            pass

    logger.info("=" * 60)
    logger.info("Step 3/3: 合并写入 market_sentiment.csv")
    logger.info("=" * 60)
    merge_into_sentiment(df_zi, df_brd)
    logger.info("ALL DONE!")




if __name__ == "__main__":
    main()
