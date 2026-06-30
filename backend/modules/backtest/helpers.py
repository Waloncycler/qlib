import json
import pandas as pd
import numpy as np
from loguru import logger
from typing import Dict, Set, Any

from core.config import DATA_DIR, WORKSPACE_DIR
from modules.backtest.data_downloader import load_ohlcv
from modules.backtest.config import BacktestConfig


def _parse_reports() -> Dict[str, dict]:
    """Parse AI Morning Reports and return structured daily pools.
    
    For dates where a curated OpenClaw stock pool exists locally
    (data/cn_stock/stock_pools/), it OVERRIDES the zizi report pool
    to ensure trades match the curated Top Picks.
    """
    reports_path = DATA_DIR / "signals" / "zizizaizai_reports.json"
    if not reports_path.exists():
        logger.error(f"Reports file not found: {reports_path}")
        return {}

    with open(reports_path, "r", encoding="utf-8") as f:
        reports = json.load(f)

    # Build per-day pool: {date -> {symbol -> {"weight_type": "core"|"other", "is_new": bool, "concept": str}}}
    daily_pools = {}
    for r in reports:
        raw_date = r.get("created_time", "")
        if not raw_date:
            continue
        date = raw_date.split(" ")[0]

        if date not in daily_pools:
            daily_pools[date] = {}

        for pool in r.get("stock_pool", []):
            concept = pool.get("concept", "Unknown")
            is_new = pool.get("is_new", False)

            for stock in pool.get("core_stocks", []):
                sym = stock.get("symbol", "")
                if sym and not sym.startswith("BJ"):
                    existing = daily_pools[date].get(sym)
                    if not existing or existing["weight_type"] != "core":
                        daily_pools[date][sym] = {
                            "weight_type": "core",
                            "is_new": is_new or (existing["is_new"] if existing else False),
                            "concept": concept,
                            "name": stock.get("name", ""),
                        }

            for stock in pool.get("other_stocks", []):
                sym = stock.get("symbol", "")
                if sym and not sym.startswith("BJ"):
                    if sym not in daily_pools[date]:
                        daily_pools[date][sym] = {
                            "weight_type": "other",
                            "is_new": is_new,
                            "concept": concept,
                            "name": stock.get("name", ""),
                        }

    # --- Apply curated pool overrides (moved to pool_generator) ---
    from modules.backtest.pool_generator import apply_curated_overrides
    return apply_curated_overrides(daily_pools)


def _compute_target_weights(
    pool: Dict[str, dict],
    config: BacktestConfig
) -> Dict[str, float]:
    """Compute normalized target weights for a daily pool."""
    raw_weights = {}
    for sym, info in pool.items():
        w = 1.0
        if info["weight_type"] == "core":
            w *= config.core_weight_multiplier
        if info["is_new"]:
            w *= config.new_concept_multiplier
        raw_weights[sym] = w

    total = sum(raw_weights.values())
    if total == 0:
        return {}
    return {sym: w / total for sym, w in raw_weights.items()}


def _filter_by_volume(
    pool: Dict[str, dict],
    prices: Dict[str, pd.DataFrame],
    date_ts: pd.Timestamp,
    config: BacktestConfig
) -> Dict[str, dict]:
    """量能过滤：排除低活跃/放量出货/缩量高位标的。

    规则（基于换手率×量比组合矩阵分析）：
      1. 换手率 < min_turnover → 不活跃，排除
      2. 量比 > max_vol_ratio → 放量出货，排除
      3. 换手率 > 10% 且量比 < 0.8 → 高位缩量，动能衰竭，排除

    Returns: 过滤后的 pool（原 pool 的子集）
    """
    if not config.enable_turnover_filter:
        return pool

    filtered = {}
    for sym, info in pool.items():
        if sym not in prices:
            filtered[sym] = info
            continue
        pdf = prices[sym]
        prev_data = pdf[pdf.index < date_ts]
        if len(prev_data) < 6:
            filtered[sym] = info
            continue

        prev_turnover = prev_data.iloc[-1].get("turnover", np.nan)
        prev_vol = prev_data.iloc[-1].get("volume", np.nan)
        vol_ma5 = prev_data.tail(5)["volume"].mean()

        if pd.isna(prev_turnover) or pd.isna(prev_vol) or vol_ma5 <= 0:
            filtered[sym] = info
            continue

        vol_ratio = prev_vol / vol_ma5

        # 规则1: 低换手率
        if prev_turnover < config.min_turnover:
            continue
        # 规则2: 放量出货
        if vol_ratio > config.max_vol_ratio:
            continue
        # 规则3: 高位缩量
        if prev_turnover > 10.0 and vol_ratio < 0.8:
            continue

        filtered[sym] = info

    removed = len(pool) - len(filtered)
    if removed > 0:
        logger.info(f"Volume filter removed {removed} stocks on {date_ts.date()}")
    return filtered


def _rank_select_by_factor(
    pool: Dict[str, dict],
    prices: Dict[str, pd.DataFrame],
    date_ts: pd.Timestamp,
    config: BacktestConfig
) -> Dict[str, dict]:
    """用因子排序从池中选 Top K，返回 Top K 子集。

    支持的因子：
    - turnover: 前日换手率（正向，越高越好）
    - amount: 前日成交额（正向）
    - body_ratio: 前日 K线实体比率（反向，越小越好=蓄势）
    - gap: 前日竞价缺口（正向）
    """
    if len(pool) <= config.top_k:
        return pool

    factor_name = config.factor_name
    scores = {}

    for sym in pool:
        if sym not in prices:
            continue
        pdf = prices[sym]
        prev_data = pdf[pdf.index < date_ts]
        if len(prev_data) < 2:
            continue

        prev_row = prev_data.iloc[-1]
        prev2_row = prev_data.iloc[-2] if len(prev_data) >= 2 else prev_row

        po = float(prev_row.get("open", 0))
        pc = float(prev_row.get("close", 0))
        ph = float(prev_row.get("high", 0))
        pl = float(prev_row.get("low", 0))
        prev_close = float(prev2_row.get("close", pc))
        range_val = ph - pl

        if factor_name == "turnover":
            val = float(prev_row.get("turnover", 0))
        elif factor_name == "amount":
            val = float(prev_row.get("amount", 0))
        elif factor_name == "body_ratio":
            val = -(pc - po) / range_val if range_val > 0 else 0  # 反向
        elif factor_name == "gap":
            val = (po - prev_close) / prev_close if prev_close > 0 else 0
        else:
            val = float(prev_row.get("turnover", 0))

        if pd.notna(val):
            scores[sym] = val

    # 排序取 Top K
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_k_syms = set(sym for sym, _ in ranked[:config.top_k])

    selected = {sym: info for sym, info in pool.items() if sym in top_k_syms}
    logger.info(f"Factor rank ({factor_name}) selected {len(selected)} from {len(pool)} on {date_ts.date()}")
    return selected


def _load_selection_history() -> Dict[str, Set[str]]:
    """加载所有 AI 早报池历史，返回 {date_str: set(symbols)}。
    
    用于计算每只股票"连续入选天数"特征。
    符号格式统一为 UPPER(with_prefix)，如 SH600118、SZ002837。
    """
    pool_dir = WORKSPACE_DIR / "data" / "cn_stock" / "stock_pools"
    if not pool_dir.exists():
        return {}

    def _to_backtest_symbol(code: str) -> str:
        """将 6 位纯数字 code 转为大写带前缀格式（与 backtest pool 一致）"""
        code = code.strip()
        if len(code) != 6:
            return code.upper()
        if code.startswith(("6", "68")):
            return f"SH{code}"
        return f"SZ{code}"

    selection_by_date = {}
    for fpath in sorted(pool_dir.glob("stock_pool_*.json")):
        try:
            date_str = fpath.stem.replace("stock_pool_", "")
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            symbols = set()
            for s in data.get("stocks", []):
                code = s.get("code", "")
                if code:
                    symbols.add(_to_backtest_symbol(code))
            selection_by_date[date_str] = symbols
        except Exception:
            continue
    return selection_by_date


def _compute_selection_boost(
    today_syms: set,
    date_str: str,
    selection_history: dict,
    boost_factor: float = 0.05,
    max_boost: float = 0.30,
) -> dict:
    """计算每只标的的连续入选加分系数。

    加分 = boost_factor * min(consecutive_days, max_boost / boost_factor)
    即最多加 max_boost（默认30%）。

    返回 {symbol: boost_multiplier}（1.0 = 不加分）
    """
    if not selection_history or not today_syms:
        return {}

    sorted_dates = sorted(selection_history.keys())
    # 找到 date_str 之前最近一个有数据的日期
    prev_dates = [d for d in sorted_dates if d < date_str]
    if not prev_dates:
        return {}

    # 从最近的日期往前数连续入选天数
    boosts = {}
    max_days = int(max_boost / boost_factor)  # 最多加多少天
    for sym in today_syms:
        consecutive = 0
        for d in reversed(prev_dates):
            if sym in selection_history.get(d, set()):
                consecutive += 1
                if consecutive >= max_days:
                    break
            else:
                break
        if consecutive > 0:
            boosts[sym] = max(0.1, 1.0 - boost_factor * consecutive)

    return boosts


def _load_all_prices(symbols: Set[str]) -> Dict[str, pd.DataFrame]:
    """Load OHLCV DataFrames for all symbols, indexed by date."""
    prices = {}
    for sym in symbols:
        df = load_ohlcv(sym)
        if not df.empty:
            df = df.set_index("date").sort_index()
            prices[sym] = df
    return prices
