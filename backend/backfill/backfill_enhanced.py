"""
backfill_enhanced.py
增强版市场情绪回溯脚本。整合：
1. 原有 Akshare 情绪数据 (上涨/下跌/新高/新低)
2. 东方财富行业排名 (Eastmoney Industry)
3. 龙虎榜机构席位数据 (Dragon-Tiger Institution)
4. ZZSHARE 市场情绪评分 & 换手率中位数
5. ZIZIZAIZAI VIP 择时 & 硬核打板数据 (天地板, 大面等)
6. 全市场估值中位数 (PE/PB)
"""
import time
import random
import logging
import yaml
import sys
import datetime
from pathlib import Path
from datetime import date, datetime, timedelta

import pandas as pd
import numpy as np
import akshare as ak
import requests
from tqdm import tqdm

# 路径修复
CUR_DIR = Path(__file__).resolve().parent
sys.path.append(str(CUR_DIR))
sys.path.append(str(CUR_DIR.parent))

from modules.market.adapters.signals import EastmoneyIndustryAdapter, DragonTigerAdapter
from modules.market.adapters.legacy import ZizizaizaiAdapter, ZzshareAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EnhancedBackfill")

# ─── 配置 ───────────────────────────────────────────────────────────────────
START_DATE = "2026-05-25"   
TOTAL_STOCKS = 5350          
# ────────────────────────────────────────────────────────────────────────────

def run_enhanced_backfill():
    save_dir = CUR_DIR.parent.parent / "data/cn_stock/hierarchical/signals"
    save_dir.mkdir(parents=True, exist_ok=True)
    csv_path = save_dir / "market_sentiment_enhanced.csv"
    
    with open(CUR_DIR.parent / "secret.yaml", "r") as f:
        config = yaml.safe_load(f)

    # 初始化适配器
    ind_adapter = EastmoneyIndustryAdapter(config)
    dt_adapter = DragonTigerAdapter(config)
    zizi_adapter = ZizizaizaiAdapter(config)
    zz_adapter = ZzshareAdapter(config)

    # 1. 获取基础交易日骨架 (使用 SH000001)
    logger.info("Fetching trading days and index data...")
    df_idx = ak.stock_zh_index_daily(symbol="sh000001")
    df_idx["date_str"] = pd.to_datetime(df_idx["date"]).dt.strftime("%Y-%m-%d")
    df_idx = df_idx[df_idx["date_str"] >= START_DATE].sort_values("date_str").reset_index(drop=True)
    target_dates = df_idx["date_str"].tolist()
    index_lookup = df_idx.set_index("date_str")["close"].to_dict()

    # 2. 预抓取各路数据
    
    # 2.1 高低统计 (Akshare)
    hl_lookup = {}
    try:
        df_hl = ak.stock_a_high_low_statistics(symbol="all")
        df_hl["date"] = df_hl["date"].astype(str)
        for _, r in df_hl.iterrows():
            hl_lookup[r["date"]] = r.to_dict()
    except Exception as e:
        logger.warning(f"Failed to fetch HL stats: {e}")

    # 2.2 ZZSHARE 情绪评分
    zz_lookup = {}
    if config.get("zzshare_token") and zz_adapter.client:
        try:
            logger.info("Fetching ZZSHARE market sentiment...")
            zz_data = zz_adapter.client.market_sentiment()
            if zz_data:
                for item in zz_data:
                    d = str(item["date"])
                    d_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                    zz_lookup[d_fmt] = item
            logger.info(f"  → Got ZZSHARE sentiment for {len(zz_lookup)} dates")
        except Exception as e:
            logger.warning(f"Failed to fetch ZZSHARE sentiment: {e}")

    # 2.3 ZIZIZAIZAI VIP 择时
    zizi_lookup = {}
    try:
        logger.info("Fetching ZIZIZAIZAI timing sentiment...")
        df_zizi = zizi_adapter.fetch_timing_sentiment(START_DATE, target_dates[-1])
        if not df_zizi.empty:
            df_zizi["date_str"] = df_zizi["date"].dt.strftime("%Y-%m-%d")
            for _, r in df_zizi.iterrows():
                zizi_lookup[r["date_str"]] = r.to_dict()
        logger.info(f"  → Got ZIZIZAIZAI sentiment for {len(zizi_lookup)} dates")
    except Exception as e:
        logger.warning(f"Failed to fetch ZIZIZAIZAI sentiment: {e}")

    # 2.4 北向资金 (HSGT)
    hsgt_lookup = {}
    try:
        logger.info("Fetching Northbound Capital (HSGT) data...")
        df_hsgt = ak.stock_hsgt_hist_em(symbol="北向资金")
        if not df_hsgt.empty:
            df_hsgt["date_str"] = pd.to_datetime(df_hsgt["日期"]).dt.strftime("%Y-%m-%d")
            for _, r in df_hsgt.iterrows():
                hsgt_lookup[r["date_str"]] = {
                    "hsgt_net_buy": r["当日成交净买额"],
                    "hsgt_cum_buy": r["历史累计净买额"]
                }
        logger.info(f"  → Got HSGT data for {len(hsgt_lookup)} dates")
    except Exception as e:
        logger.warning(f"Failed to fetch HSGT data: {e}")

    # 2.5 Ziruxing 硬核打板数据
    ziruxing_lookup = {}
    try:
        logger.info("Fetching Ziruxing hardcore sentiment data...")
        z_start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        url = f"https://stock.ziruxing.com/sentiment/market/data?date1={z_start}&date2={target_dates[-1]}"
        headers = {"sdk-key": config.get("zzshare_token"), "User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code == 200:
            z_data = res.json().get("data", [])
            for item in z_data:
                ziruxing_lookup[item["date1"]] = item
        logger.info(f"  → Got Ziruxing hardcore data for {len(ziruxing_lookup)} dates")
    except Exception as e:
        logger.warning(f"Failed to fetch Ziruxing hardcore data: {e}")

    # 2.6 全市场估值中位数 (PE/PB)
    val_lookup = {}
    try:
        logger.info("Fetching market valuation (PE/PB) medians...")
        df_pe = ak.stock_a_ttm_lyr()
        df_pb = ak.stock_a_all_pb()
        df_pe["date_str"] = pd.to_datetime(df_pe["date"]).dt.strftime("%Y-%m-%d")
        df_pb["date_str"] = pd.to_datetime(df_pb["date"]).dt.strftime("%Y-%m-%d")
        pe_dict = df_pe.set_index("date_str")["middlePETTM"].to_dict()
        pb_dict = df_pb.set_index("date_str")["middlePB"].to_dict()
        for d in target_dates:
            val_lookup[d] = {"pe_median": pe_dict.get(d, np.nan), "pb_median": pb_dict.get(d, np.nan)}
        logger.info(f"  → Got Valuation data for {len(val_lookup)} dates")
    except Exception as e:
        logger.warning(f"Failed to fetch valuation data: {e}")

    # 2.7 换手率中位数 (最近 5 天)
    turnover_lookup = {}
    if config.get("zzshare_token") and zz_adapter.client:
        try:
            logger.info("Calculating Turnover Median for recent dates...")
            for d_str in target_dates[-5:]:
                d_param = d_str.replace("-", "")
                df_day = zz_adapter.client.daily(trade_date=d_param, limit=6000, fields="turnover_rate")
                if df_day is not None and not df_day.empty:
                    turnover_lookup[d_str] = df_day["turnover_rate"].median()
        except: pass

    # 3. 逐日处理
    rows = []
    total = len(target_dates)

    for i, date_str in enumerate(target_dates):
        if i % 100 == 0: logger.info(f"Processing progress: {i}/{total}")
        row_data = {"date": date_str}

        zi_hard = ziruxing_lookup.get(date_str, {})
        val_data = val_lookup.get(date_str, {})
        
        row_data["index_close"] = index_lookup.get(date_str, np.nan)
        row_data["pe_median"] = val_data.get("pe_median", np.nan)
        row_data["pb_median"] = val_data.get("pb_median", np.nan)
        row_data["turnover_median"] = turnover_lookup.get(date_str, np.nan)

        # 北向资金
        hsgt = hsgt_lookup.get(date_str, {})
        row_data["hsgt_net_buy"] = hsgt.get("hsgt_net_buy", np.nan)
        row_data["hsgt_cum_buy"] = hsgt.get("hsgt_cum_buy", np.nan)

        # A. 基础情绪数据
        hl = hl_lookup.get(date_str, {})
        for k in ["high20", "high60", "high120", "low20", "low60", "low120"]:
            row_data[k] = hl.get(k, np.nan)

        # A.2 ZIZIZAIZAI 择时
        zi = zizi_lookup.get(date_str, {})
        row_data["zizi_market_timing"] = zi.get("market_timing", np.nan)
        row_data["timing_signal_type"] = zi.get("timing_signal_type", np.nan)
        
        # A.3 Ziruxing 核心字段
        if zi_hard:
            row_data["limit_up_count"] = zi_hard.get("uplimit_num", np.nan)
            row_data["real_limit_up_count"] = zi_hard.get("uplimit_n_num", np.nan)
            row_data["limit_down_count"] = zi_hard.get("downlimit_num", np.nan)
            row_data["broken_limit_up_count"] = zi_hard.get("zb_num", np.nan)
            row_data["highest_consecutive_limit_up"] = zi_hard.get("max_lb_num", np.nan)
            row_data["tiandi_num"] = zi_hard.get("tiandi_num", 0)
            row_data["ditian_num"] = zi_hard.get("ditian_num", 0)
            row_data["damian_num"] = zi_hard.get("damian_num", 0)
            row_data["bigleg_num"] = zi_hard.get("bigleg_num", 0)
            row_data["mian_num"] = zi_hard.get("mian_num", 0)
            row_data["lb_2_count"] = zi_hard.get("lb_2_num", 0)
            row_data["lb_3_plus_count"] = zi_hard.get("lb_h_num", 0)
            
            up = zi_hard.get("up_num", 0)
            down = zi_hard.get("down_num", 0)
            if (up + down) > 0:
                row_data["profit_effect_pct"] = round(up / (up + down) * 100, 2)
            else: row_data["profit_effect_pct"] = np.nan

        # B. 龙虎榜机构数据
        try:
            df_dt = dt_adapter.get_daily_dragon_tiger(trade_date=date_str)
            if not df_dt.empty:
                row_data["dt_net_buy_wan"] = df_dt["net_buy_wan"].sum()
                row_data["dt_stock_count"] = len(df_dt)
            else:
                row_data["dt_net_buy_wan"] = 0
                row_data["dt_stock_count"] = 0
        except: pass

        rows.append(row_data)

    df_enhanced = pd.DataFrame(rows)
    orig_csv = save_dir / "market_sentiment.csv"
    if orig_csv.exists():
        df_orig = pd.read_csv(orig_csv)
        df_orig["date"] = df_orig["date"].astype(str)
        df_final = df_enhanced.set_index("date").combine_first(df_orig.set_index("date")).reset_index()
    else:
        df_final = df_enhanced

    df_final = df_final.sort_values("date")
    df_final.to_csv(orig_csv, index=False)
    logger.info(f"Done! Updated {orig_csv}")

if __name__ == "__main__":
    run_enhanced_backfill()
