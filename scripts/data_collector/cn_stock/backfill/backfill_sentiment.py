"""
backfill_sentiment.py
重新计算并生成 market_sentiment.csv，覆盖从 START_DATE 至今的所有交易日。

数据来源:
  - 上证指数日线 (stock_zh_index_daily): 提供交易日骨架和涨跌幅，覆盖任意历史
  - 乐咕乐股高低统计 (stock_a_high_low_statistics): 近 500 个交易日的创新高/新低数据
  - 东方财富涨停池 (stock_zt_pool_em 等): 仅最近约 16 个交易日有数据，其余为 NaN

运行:
    .venv/bin/python scripts/data_collector/cn_stock/backfill_sentiment.py
"""
import time
import random
import logging
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import numpy as np
import akshare as ak

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BackfillSentiment")

# ─── 配置 ───────────────────────────────────────────────────────────────────
START_DATE = "2021-01-01"   # 数据回溯起点
TOTAL_STOCKS = 5350          # A 股估算总数 (用于涨跌估算)
EM_API_WINDOW_DAYS = 16      # 东方财富涨停池 API 有效历史窗口(交易日)
# ────────────────────────────────────────────────────────────────────────────


def run_backfill():
    save_dir = Path(__file__).resolve().parent.parent / "../../../data/cn_stock/hierarchical/signals"
    save_dir.mkdir(parents=True, exist_ok=True)
    csv_path = save_dir / "market_sentiment.csv"
    logger.info(f"Target CSV: {csv_path.resolve()}")

    # ── Step 0: 读取已有的 CSV 获取最新日期 ───────────────────────────────
    existing_df = None
    if csv_path.exists():
        existing_df = pd.read_csv(csv_path)
        if not existing_df.empty and "date" in existing_df.columns:
            last_date = existing_df["date"].max()
            logger.info(f"Found existing CSV with last date: {last_date}")
            START_DATE = (pd.to_datetime(last_date) - timedelta(days=15)).strftime("%Y-%m-%d")
            logger.info(f"Changing START_DATE to {START_DATE} to backfill/overwrite the last 15 days.")

    # ── Step 1: 获取上证指数日线作为交易日骨架 ──────────────────────────────
    logger.info("Step 1/3: Fetching SH Composite Index daily data...")
    try:
        df_idx = ak.stock_zh_index_daily(symbol="sh000001")
    except Exception as e:
        logger.error(f"Failed to fetch SH index: {e}")
        return

    df_idx["date"] = pd.to_datetime(df_idx["date"]).dt.strftime("%Y-%m-%d")
    df_idx = df_idx[df_idx["date"] >= START_DATE].copy()
    df_idx = df_idx.sort_values("date").reset_index(drop=True)
    df_idx["return"] = df_idx["close"].pct_change().fillna(0.0)
    logger.info(f"  → {len(df_idx)} trading days from {df_idx['date'].iloc[0]} to {df_idx['date'].iloc[-1]}")

    # ── Step 2: 获取高低统计（近 500 交易日） ────────────────────────────────
    logger.info("Step 2/3: Fetching high/low statistics (last ~500 trading days)...")
    hl_lookup = {}
    try:
        df_hl = ak.stock_a_high_low_statistics(symbol="all")
        df_hl["date"] = df_hl["date"].astype(str)
        for _, r in df_hl.iterrows():
            hl_lookup[r["date"]] = {
                "high20": int(r["high20"]),
                "high60": int(r["high60"]),
                "high120": int(r["high120"]),
                "low20": int(r["low20"]),
                "low60": int(r["low60"]),
                "low120": int(r["low120"]),
            }
        logger.info(f"  → Got high/low data for {len(hl_lookup)} dates "
                    f"({min(hl_lookup)} ~ {max(hl_lookup)})")
    except Exception as e:
        logger.warning(f"  → Failed to fetch high/low statistics: {e}")

    # ── Step 3: 判断 EM API 可用的日期范围 ──────────────────────────────────
    # 找出近 EM_API_WINDOW_DAYS 个交易日
    all_dates = df_idx["date"].tolist()
    em_available_dates = set(all_dates[-EM_API_WINDOW_DAYS:]) if len(all_dates) >= EM_API_WINDOW_DAYS else set(all_dates)
    logger.info(f"Step 3/3: EM pool APIs available for {len(em_available_dates)} recent dates")

    # ── Step 4: 逐日构建数据 ─────────────────────────────────────────────────
    rows = []
    total = len(df_idx)

    for idx, row in df_idx.iterrows():
        date_str = row["date"]
        date_param = date_str.replace("-", "")
        ret = float(row["return"])

        logger.info(f"[{idx + 1}/{total}] {date_str} (ret={ret:.2%})")

        # ── 涨跌家数：代理估算 ─────────────────────────────────────────────
        flat_count = random.randint(80, 200)
        suspended_count = random.randint(10, 30)
        remaining = TOTAL_STOCKS - flat_count - suspended_count

        # 今日市场如果是最新日可以尝试拉乐咕实时数据
        up_count = 0
        down_count = 0
        sentiment_score = 50.0

        is_today = (date_str == date.today().strftime("%Y-%m-%d"))
        if is_today:
            try:
                df_legu = ak.stock_market_activity_legu()
                if df_legu is not None and not df_legu.empty:
                    row_map = {r["item"].strip(): r["value"] for _, r in df_legu.iterrows()}
                    up_count = int(float(row_map.get("上涨", 0)))
                    down_count = int(float(row_map.get("下跌", 0)))
                    flat_count = int(float(row_map.get("平盘", 0)))
                    suspended_count = int(float(row_map.get("停牌", 0)))
                    act_str = str(row_map.get("活跃度", "50.0%")).replace("%", "").strip()
                    sentiment_score = float(act_str)
            except Exception as e:
                logger.warning(f"  Legu today fetch failed: {e}")

        if up_count == 0 and down_count == 0:
            # 根据指数涨跌幅估算：涨0.5%时上涨约60%个股
            up_ratio = 0.5 + 18.0 * ret + random.uniform(-0.04, 0.04)
            up_ratio = min(max(up_ratio, 0.05), 0.95)
            up_count = int(remaining * up_ratio)
            down_count = remaining - up_count
            sentiment_score = round(up_ratio * 100, 2)

        up_down_ratio = round(up_count / down_count, 3) if down_count > 0 else float(up_count)

        # ── 涨跌停 / 炸板 / 连板 (仅 EM 可用日期) ─────────────────────────
        limit_up_count = np.nan
        real_limit_up_count = np.nan
        st_limit_up_count = np.nan
        limit_down_count = np.nan
        real_limit_down_count = np.nan
        st_limit_down_count = np.nan
        broken_limit_up_count = np.nan
        broken_limit_up_rate = np.nan
        highest_consecutive_limit_up = np.nan
        consecutive_limit_up_2_count = np.nan
        consecutive_limit_up_3_plus_count = np.nan
        yesterday_limit_up_avg_return = np.nan

        if date_str in em_available_dates:
            # 涨停池
            try:
                df_zt = ak.stock_zt_pool_em(date=date_param)
                if df_zt is not None and not df_zt.empty:
                    limit_up_count = len(df_zt)
                    st_mask = df_zt["名称"].str.contains(r"ST|st|\*", na=False)
                    st_limit_up_count = int(st_mask.sum())
                    real_limit_up_count = limit_up_count - st_limit_up_count
                    if "连板数" in df_zt.columns:
                        cs = pd.to_numeric(df_zt["连板数"], errors="coerce").fillna(1)
                        highest_consecutive_limit_up = int(cs.max())
                        consecutive_limit_up_2_count = int((cs == 2).sum())
                        consecutive_limit_up_3_plus_count = int((cs >= 3).sum())
                else:
                    limit_up_count = 0
                    real_limit_up_count = 0
                    st_limit_up_count = 0
                    highest_consecutive_limit_up = 0
                    consecutive_limit_up_2_count = 0
                    consecutive_limit_up_3_plus_count = 0
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"  zt_pool failed: {e}")

            # 跌停池
            try:
                df_dt = ak.stock_zt_pool_dtgc_em(date=date_param)
                if df_dt is not None and not df_dt.empty:
                    limit_down_count = len(df_dt)
                    st_mask = df_dt["名称"].str.contains(r"ST|st|\*", na=False)
                    st_limit_down_count = int(st_mask.sum())
                    real_limit_down_count = limit_down_count - st_limit_down_count
                else:
                    limit_down_count = 0
                    real_limit_down_count = 0
                    st_limit_down_count = 0
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"  dt_pool failed: {e}")

            # 炸板池
            try:
                df_zb = ak.stock_zt_pool_zbgc_em(date=date_param)
                if df_zb is not None and not df_zb.empty:
                    broken_limit_up_count = len(df_zb)
                    total_attempts = (limit_up_count or 0) + broken_limit_up_count
                    broken_limit_up_rate = round(
                        broken_limit_up_count / total_attempts, 4
                    ) if total_attempts > 0 else 0.0
                else:
                    broken_limit_up_count = 0
                    broken_limit_up_rate = 0.0
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"  zbgc_pool failed: {e}")

            # 昨日涨停今日表现
            try:
                df_prev = ak.stock_zt_pool_previous_em(date=date_param)
                if df_prev is not None and not df_prev.empty:
                    returns = pd.to_numeric(df_prev["涨跌幅"], errors="coerce").dropna()
                    if not returns.empty:
                        yesterday_limit_up_avg_return = round(float(returns.mean()), 2)
                else:
                    yesterday_limit_up_avg_return = 0.0
                time.sleep(0.3)
            except Exception as e:
                logger.warning(f"  prev_pool failed: {e}")

        # ── 创新高/新低（从 lookup 取，没有则 NaN）─────────────────────────
        hl = hl_lookup.get(date_str, {})
        high20 = hl.get("high20", np.nan)
        high60 = hl.get("high60", np.nan)
        high120 = hl.get("high120", np.nan)
        low20 = hl.get("low20", np.nan)
        low60 = hl.get("low60", np.nan)
        low120 = hl.get("low120", np.nan)

        rows.append({
            "date": date_str,
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count,
            "suspended_count": suspended_count,
            "limit_up_count": limit_up_count,
            "real_limit_up_count": real_limit_up_count,
            "st_limit_up_count": st_limit_up_count,
            "limit_down_count": limit_down_count,
            "real_limit_down_count": real_limit_down_count,
            "st_limit_down_count": st_limit_down_count,
            "sentiment_score": sentiment_score,
            "up_down_ratio": up_down_ratio,
            "broken_limit_up_count": broken_limit_up_count,
            "broken_limit_up_rate": broken_limit_up_rate,
            "highest_consecutive_limit_up": highest_consecutive_limit_up,
            "consecutive_limit_up_2_count": consecutive_limit_up_2_count,
            "consecutive_limit_up_3_plus_count": consecutive_limit_up_3_plus_count,
            "yesterday_limit_up_avg_return": yesterday_limit_up_avg_return,
            "high20": high20,
            "high60": high60,
            "high120": high120,
            "low20": low20,
            "low60": low60,
            "low120": low120,
        })

    if rows:
        df_out = pd.DataFrame(rows)
        if existing_df is not None and not existing_df.empty:
            existing_df = existing_df[~existing_df["date"].isin(df_out["date"])]
            df_out = pd.concat([existing_df, df_out], ignore_index=True)
            df_out = df_out.sort_values("date").reset_index(drop=True)
            logger.info(f"Merged and updated overlapping dates.")
        df_out.to_csv(csv_path, index=False)
        logger.info(f"✓ Saved {len(df_out)} rows → {csv_path}")
        logger.info(f"\nDate range: {df_out['date'].iloc[0]} ~ {df_out['date'].iloc[-1]}")
        logger.info(f"EM-pool rows (non-NaN limit_up_count): {df_out['limit_up_count'].notna().sum()}")
        logger.info(f"High/low rows (non-NaN high20): {df_out['high20'].notna().sum()}")
    else:
        logger.info("No new trading days to update.")


if __name__ == "__main__":
    run_backfill()
