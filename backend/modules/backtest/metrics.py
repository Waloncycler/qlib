import numpy as np
import pandas as pd
from typing import List, Dict, Any

def calculate_backtest_metrics(records: List[Dict[str, Any]], concept_returns: Dict[str, List[float]]) -> Dict[str, Any]:
    """
    Computes aggregate metrics, NAV curves and concept attributions.
    
    Returns:
        Dict containing keys: 'curve', 'metrics', 'concept_attribution'
    """
    if not records:
        return {"curve": [], "metrics": {}, "concept_attribution": []}

    returns_series = pd.Series([r["daily_return"] for r in records])
    bench_series = pd.Series([r["benchmark_return"] for r in records])

    # NAV curves
    strategy_cumulative = (1 + returns_series).cumprod()
    benchmark_cumulative = (1 + bench_series).cumprod()

    # Annualized return (assume 244 trading days)
    total_days = len(records)
    total_return = strategy_cumulative.iloc[-1] - 1 if len(strategy_cumulative) > 0 else 0.0
    ann_return = (1 + total_return) ** (244 / max(total_days, 1)) - 1

    # Max drawdown
    running_max = strategy_cumulative.cummax()
    drawdown = (strategy_cumulative - running_max) / running_max
    
    drawdown_periods = []
    if len(drawdown) > 0 and not drawdown.isna().all():
        end_idx = int(drawdown.idxmin())
        max_drawdown = drawdown.min()
        start_idx = int(strategy_cumulative.iloc[:end_idx + 1].idxmax())
        max_dd_start = records[start_idx]["date"]
        max_dd_end = records[end_idx]["date"]
        
        # Find all drawdowns > 20% + the max drawdown
        underwater = drawdown < 0
        blocks = (~underwater).cumsum()
        for _, group in drawdown.groupby(blocks):
            group_min = group.min()
            if group_min < 0:
                is_global_max = (int(group.idxmin()) == end_idx)
                if group_min <= -0.20 or is_global_max:
                    trough_idx = int(group.idxmin())
                    peak_idx = int(max(0, group.index[0] - 1))
                    drawdown_periods.append({
                        "start": records[peak_idx]["date"],
                        "end": records[trough_idx]["date"],
                        "drawdown": round(float(group_min), 4)
                    })
    else:
        max_drawdown = 0.0
        max_dd_start = ""
        max_dd_end = ""

    # Sharpe ratio (annualized, rf=0)
    sharpe = (returns_series.mean() / returns_series.std() * np.sqrt(244)) if returns_series.std() > 0 else 0.0

    # Information ratio (excess return vs benchmark)
    excess = returns_series - bench_series
    ir = (excess.mean() / excess.std() * np.sqrt(244)) if excess.std() > 0 else 0.0

    # Hit rate (% of days with positive return)
    hit_rate = (returns_series > 0).sum() / max(len(returns_series), 1)

    # Profit/loss ratio
    gains = returns_series[returns_series > 0]
    losses = returns_series[returns_series < 0]
    avg_gain = gains.mean() if len(gains) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 1
    profit_loss_ratio = avg_gain / avg_loss if avg_loss > 0 else 0

    # Benchmark metrics
    bench_total = benchmark_cumulative.iloc[-1] - 1 if len(benchmark_cumulative) > 0 else 0.0
    bench_ann = (1 + bench_total) ** (244 / max(total_days, 1)) - 1

    metrics = {
        "total_return": round(float(total_return), 4),
        "annualized_return": round(float(ann_return), 4),
        "max_drawdown": round(float(max_drawdown), 4),
        "max_drawdown_start": max_dd_start,
        "max_drawdown_end": max_dd_end,
        "drawdown_periods": drawdown_periods,
        "sharpe_ratio": round(float(sharpe), 3),
        "information_ratio": round(float(ir), 3),
        "hit_rate": round(float(hit_rate), 4),
        "profit_loss_ratio": round(float(profit_loss_ratio), 3),
        "total_trading_days": total_days,
        "avg_holdings_count": round(float(np.mean([r["holdings_count"] for r in records])), 1) if records else 0.0,
        "avg_turnover": round(float(np.mean([r["turnover"] for r in records])), 4) if records else 0.0,
        "benchmark_total_return": round(float(bench_total), 4),
        "benchmark_annualized_return": round(float(bench_ann), 4),
    }

    # Build curve output
    curve_data = []
    for i, rec in enumerate(records):
        curve_data.append({
            "date": rec["date"],
            "strategy": round(float(strategy_cumulative.iloc[i]) - 1, 6),
            "benchmark": round(float(benchmark_cumulative.iloc[i]) - 1, 6),
            "daily_return": round(float(rec["daily_return"]), 6),
            "holdings_count": rec["holdings_count"],
            "turnover": rec["turnover"],
        })

    # Concept attribution
    concept_attr = []
    for concept, rets in concept_returns.items():
        rets_arr = np.array(rets)
        concept_attr.append({
            "concept": concept,
            "total_return": round(float(rets_arr.sum()), 4),
            "avg_daily_return": round(float(rets_arr.mean()), 6),
            "days_active": len(rets),
            "hit_rate": round(float((rets_arr > 0).sum() / max(len(rets_arr), 1)), 4),
        })

    # Sort by total return descending
    concept_attr.sort(key=lambda x: x["total_return"], reverse=True)

    return {
        "curve": curve_data,
        "metrics": metrics,
        "concept_attribution": concept_attr,
    }
