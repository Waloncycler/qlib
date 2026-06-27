"""
Hybrid composite scoring for today's AI pre-market picks.

Combines ML predictions with popularity data (THS + Eastmoney) and
applies LLM logic boosts and risk veto to produce a ranked list.
"""
import json
import concurrent.futures

import pandas as pd
from loguru import logger

from core.config import WORKSPACE_DIR, config
from modules.market.adapters.base import to_qlib_symbol
from modules.market.adapters.popularity import EastmoneyPopularityAdapter, TonghuashunPopularityAdapter


def get_todays_picks_service(model_version="v3_open2close", top_k=10, use_composite=True):
    """Fetches the latest AI pre-market report and scores it with ML + popularity."""
    from modules.backtest.signal_backtest import _parse_reports

    daily_pools = _parse_reports()
    if not daily_pools:
        return {"status": "error", "message": "No historical pool data found."}

    latest_date = max(daily_pools.keys())

    stock_pools_dir = WORKSPACE_DIR / "data" / "cn_stock" / "stock_pools"
    override_file = stock_pools_dir / f"stock_pool_{latest_date}.json"

    candidates = {}

    if override_file.exists():
        with open(override_file, 'r', encoding='utf-8') as f:
            pool_data = json.load(f)
        stocks = pool_data.get('stocks', [])

        candidates = {to_qlib_symbol(s['code']): s for s in stocks}
    else:
        pool_data = daily_pools[latest_date]
        for sym, info in pool_data.items():
            candidates[sym] = info

    # Load ML predictions
    pred_path = WORKSPACE_DIR / "data" / "cn_stock" / "predictions" / f"{model_version}.pkl"

    if not pred_path.exists():
        return {"status": "error", "message": f"ML predictions file not found at {pred_path}. Run backtest first."}

    preds = pd.read_pickle(pred_path)
    if isinstance(preds, pd.DataFrame) and preds.shape[1] > 0:
        preds = preds.iloc[:, 0]

    # Upper-case the symbols!
    if isinstance(preds.index, pd.MultiIndex):
        preds.index = preds.index.set_levels(preds.index.levels[1].str.upper(), level=1)

    latest_pred_date = preds.index.get_level_values(0).max()
    day_preds = preds.loc[latest_pred_date]
    valid_preds = day_preds.reindex(list(candidates.keys())).dropna()

    # SORT and TRUNCATE: Only check popularity/risk for the Top 25 ML scores to avoid crashing the server
    valid_preds = valid_preds.sort_values(ascending=False).head(25)

    # 1. Fetch Batch Data from THS
    ths_pop = TonghuashunPopularityAdapter(config)
    ths_batch_data = ths_pop.get_batch_data(list(valid_preds.index))

    # 2. Fetch EM Popularity concurrently (Top 20 candidates is sufficient)
    em_pop = EastmoneyPopularityAdapter(config)
    em_ranks = {}

    def fetch_em(sym):
        return sym, em_pop.get_realtime_rank(sym)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_em, sym): sym for sym in valid_preds.index}
        for future in concurrent.futures.as_completed(futures):
            sym, r = future.result()
            em_ranks[sym] = r

    # 3. Map scores back and Adjust (Hybrid Composite Scoring)
    results = []
    for sym, score in valid_preds.items():
        s_info = candidates[sym]
        base_score = float(score)

        # Get meta
        raw_code = ''.join([c for c in sym if c.isdigit()])
        ths_meta = ths_batch_data.get(raw_code, {})
        ths_rank = ths_meta.get("rank", 99999)
        is_risky = ths_meta.get("is_risky", False)
        em_rank = em_ranks.get(sym, 99999)

        # Base multiplier
        multiplier = 1.0

        # LLM Logic Boost
        if s_info.get("weight_type") == "core":
            multiplier += 0.5
        if s_info.get("is_new"):
            multiplier += 0.2

        # Popularity Boost (Top 200 Cross-validation)
        pop_boost = 0.0
        pop_status = "一般"
        if em_rank <= 200 and ths_rank <= 200:
            pop_boost += 1.0  # Massive boost
            pop_status = "双百强"
        elif em_rank <= 200 or ths_rank <= 200:
            pop_boost += 0.5  # Moderate boost
            pop_status = "人气股"

        # Adjust score
        if use_composite:
            adjusted_score = base_score * multiplier + pop_boost
        else:
            adjusted_score = base_score

        # Risk Veto
        if is_risky:
            adjusted_score = -9999.0  # Veto
            pop_status = "风控剔除"

        results.append({
            "symbol": sym,
            "name": s_info.get("name", ths_meta.get("name", "")),
            "theme": s_info.get("theme", s_info.get("concept", "")),
            "score": round(adjusted_score, 4),
            "original_score": round(base_score, 4),
            "em_rank": em_rank if em_rank != 99999 else "无",
            "ths_rank": ths_rank if ths_rank != 99999 else "无",
            "popularity": pop_status
        })

    results.sort(key=lambda x: x['score'], reverse=True)

    return {
        "status": "success",
        "date": latest_date,
        "prediction_date": latest_pred_date.strftime("%Y-%m-%d") if hasattr(latest_pred_date, 'strftime') else str(latest_pred_date),
        "data": results,
        "top_picks": [r for r in results[:top_k] if r["score"] > -9900],  # Don't return vetoed
        "other_candidates": results[top_k:]
    }
