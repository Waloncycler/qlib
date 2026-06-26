"""
短线子池筛选器

从 llm_pool 出发，基于 Qlib K 线数据计算短线活跃度指标，
筛选出最适合短线交易的股票子集。

筛选维度：
1. 打板强度：近 60 日涨停次数（pct_change ≥ 9.8%）
2. 换手活跃度：近 60 日平均换手率
3. 波动率：近 60 日日收益率标准差
4. 动量：近 20 日累计涨幅绝对值（排除涨幅过大但保持适度动量）

输出：shortline_pool.txt → Qlib instruments 格式
"""

import sys
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
from pathlib import Path
import numpy as np
import pandas as pd

import qlib
from qlib.constant import REG_CN

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_dir))
from core.config import WORKSPACE_DIR

# ============================================================
# 配置
# ============================================================
PROVIDER_URI = str(WORKSPACE_DIR / "data" / "cn_stock" / "standard" / "qlib_data")
INSTRUMENTS_DIR = WORKSPACE_DIR / "data" / "cn_stock" / "standard" / "qlib_data" / "instruments"

# 筛选时间窗口（使用最近 60 个交易日）
LOOKBACK_DAYS = 60
# 涨停阈值（主板 10%，创业板/科创板 20%，这里用 9.8% 宽松判断主板涨停）
LIMIT_UP_THRESHOLD = 9.8
# 最终保留的股票数量
TARGET_POOL_SIZE = 300


def init_qlib():
    qlib.init(provider_uri=PROVIDER_URI, region=REG_CN)


def load_llm_pool_symbols():
    """读取 llm_pool.txt 中的全部股票代码"""
    pool_file = INSTRUMENTS_DIR / "llm_pool.txt"
    if not pool_file.exists():
        print(f"ERROR: {pool_file} not found. Run generate_llm_pool.py first.")
        sys.exit(1)

    symbols = []
    with open(pool_file, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if parts:
                symbols.append(parts[0])
    print(f"Loaded {len(symbols)} symbols from llm_pool.txt")
    return symbols


def compute_shortline_scores(symbols):
    """
    对每只股票计算短线活跃度综合评分。

    使用 Qlib 表达式引擎批量计算，避免逐只加载。
    """
    from qlib.data import D

    # 时间范围：取最近 LOOKBACK_DAYS 个交易日
    calendar = D.calendar(start_time="2024-06-01")
    if len(calendar) < LOOKBACK_DAYS:
        print(f"WARNING: Only {len(calendar)} trading days available, expected >= {LOOKBACK_DAYS}")
    end_date = calendar[-1]
    start_idx = max(0, len(calendar) - LOOKBACK_DAYS)
    start_date = calendar[start_idx]

    print(f"Computing short-line features from {start_date.date()} to {end_date.date()}...")

    # 批量加载所需字段
    fields = ["$close", "$open", "$high", "$low", "$volume", "$pct_change", "$turnover"]
    try:
        # D.features 返回 MultiIndex DataFrame (datetime, instrument)
        df = D.features(
            instruments=symbols,
            fields=fields,
            start_time=start_date,
            end_time=end_date,
            freq="day",
        )
    except Exception as e:
        print(f"Error loading features: {e}")
        return pd.DataFrame()

    if df.empty:
        print("ERROR: No data loaded.")
        return pd.DataFrame()

    print(f"Loaded raw data: {df.shape}")

    # 按股票分组计算短线指标
    results = []
    grouped = df.groupby(level="instrument")

    for sym, group in grouped:
        group = group.droplevel("instrument").sort_index()
        if len(group) < 20:
            continue  # 数据不足，跳过

        pct_chg = group["$pct_change"]
        turnover = group["$turnover"]
        close = group["$close"]
        volume = group["$volume"]

        # 1. 打板强度：涨停天数占比（pct_change 以 % 为单位）
        limit_up_days = (pct_chg >= LIMIT_UP_THRESHOLD).sum()
        limit_up_ratio = limit_up_days / len(group)

        # 2. 换手活跃度：平均换手率
        avg_turnover = turnover.mean()

        # 3. 波动率：日收益率标准差
        daily_ret = pct_chg / 100.0
        volatility = daily_ret.std()

        # 4. 近 20 日动量
        recent_20 = group.tail(20)
        if len(recent_20) >= 2 and recent_20["$close"].iloc[0] > 0:
            mom_20 = recent_20["$close"].iloc[-1] / recent_20["$close"].iloc[0] - 1
        else:
            mom_20 = 0.0

        # 5. 近 5 日量比（最近5日均量 / 全周期均量）
        vol_recent = volume.tail(5).mean()
        vol_avg = volume.mean()
        vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1.0

        # 综合评分（加权组合）
        # 权重设计：打板强度和换手率最重要，波动率适中，动量适度
        score = (
            limit_up_ratio * 40.0          # 打板强度：权重最大
            + min(avg_turnover, 10.0) * 3.0  # 换手率：封顶 10%，避免异常值
            + volatility * 100 * 5.0          # 波动率：放大到合理范围
            + abs(mom_20) * 10.0               # 动量绝对值：趋势活跃度
            + (vol_ratio - 1.0) * 15.0         # 量比变化：近期放量
        )

        results.append({
            "symbol": sym,
            "limit_up_days": int(limit_up_days),
            "limit_up_ratio": round(limit_up_ratio, 4),
            "avg_turnover": round(avg_turnover, 4),
            "volatility": round(volatility, 4),
            "mom_20": round(mom_20, 4),
            "vol_ratio": round(vol_ratio, 2),
            "score": round(score, 2),
        })

    scores_df = pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
    return scores_df


def generate_shortline_pool(scores_df, target_size=TARGET_POOL_SIZE):
    """根据评分取 Top N 生成短线子池"""
    if scores_df.empty:
        print("ERROR: No scores computed.")
        return []

    # 取评分最高的 target_size 只
    selected = scores_df.head(target_size)
    symbols = selected["symbol"].tolist()

    print(f"\n{'='*60}")
    print(f"短线子池 Top {len(symbols)} 只股票：")
    print(f"{'='*60}")
    print(selected[["symbol", "score", "limit_up_days", "avg_turnover", "volatility", "vol_ratio"]].to_string(index=False))
    print(f"{'='*60}")

    # 统计信息
    print(f"\n子池统计：")
    print(f"  平均涨停天数: {selected['limit_up_days'].mean():.1f}")
    print(f"  平均换手率: {selected['avg_turnover'].mean():.2f}%")
    print(f"  平均波动率: {selected['volatility'].mean():.4f}")
    print(f"  评分范围: [{selected['score'].min():.2f}, {selected['score'].max():.2f}]")

    return symbols


def save_pool(symbols, filename="shortline_pool.txt"):
    """保存为 Qlib instruments 格式"""
    out_path = INSTRUMENTS_DIR / filename
    with open(out_path, "w") as f:
        for sym in sorted(symbols):
            f.write(f"{sym}\t2000-01-01\t2099-12-31\n")
    print(f"\nSaved {len(symbols)} symbols to {out_path}")


if __name__ == "__main__":
    init_qlib()

    # 1. 加载 llm_pool 股票
    symbols = load_llm_pool_symbols()

    # 2. 计算短线活跃度评分
    scores_df = compute_shortline_scores(symbols)

    # 3. 生成短线子池
    pool_symbols = generate_shortline_pool(scores_df)

    # 4. 保存
    save_pool(pool_symbols)

    # 5. 同时保存评分明细（供分析用）
    scores_path = WORKSPACE_DIR / "data" / "cn_stock" / "shortline_scores.csv"
    scores_df.to_csv(scores_path, index=False)
    print(f"Scores detail saved to {scores_path}")

    print("\nDone! Short-line sub-pool generation complete.")
