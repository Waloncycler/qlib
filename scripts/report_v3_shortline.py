"""
AlphaShortLine v1 完整回测报告
K=2, 3, 4，无大盘择时
"""
import sys
from pathlib import Path
import pandas as pd

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_dir))

from modules.backtest.signal_backtest import run_signal_backtest, BacktestConfig

print("=" * 70)
print("AlphaShortLine v1 完整回测报告（无大盘择时）")
print("模型: Alpha158 + 12短线特征 | 股票池: shortline_pool(300只)")
print("Label: T开盘 -> T+1收盘 | 无CSRankNorm")
print("=" * 70)

summary = []

for k in [2, 3, 4]:
    config = BacktestConfig(
        enable_ml_filter=True,
        model_version="v3_open2close",
        top_k=k,
        exit_timing="close",
        enable_market_timing=False,
    )
    result = run_signal_backtest(config)
    m = result["metrics"]

    summary.append({
        "K": k,
        "ann_ret": m["annualized_return"],
        "total_ret": m["total_return"],
        "max_dd": m["max_drawdown"],
        "sharpe": m["sharpe_ratio"],
        "ir": m["information_ratio"],
        "hit_rate": m["hit_rate"],
        "pl_ratio": m["profit_loss_ratio"],
    })

    print(f"\n{'─'*70}")
    print(f"  K = {k}")
    print(f"{'─'*70}")
    print(f"  年化收益:   {m['annualized_return']:>10.2%}")
    print(f"  总收益:     {m['total_return']:>10.2%}")
    print(f"  最大回撤:   {m['max_drawdown']:>10.2%}")
    print(f"  回撤区间:   {m['max_drawdown_start']} -> {m['max_drawdown_end']}")
    print(f"  Sharpe:     {m['sharpe_ratio']:>10.3f}")
    print(f"  信息比率:   {m['information_ratio']:>10.3f}")
    print(f"  胜率:       {m['hit_rate']:>10.2%}")
    print(f"  盈亏比:     {m['profit_loss_ratio']:>10.3f}")
    print(f"  交易天数:   {m['total_trading_days']:>10}")
    print(f"  平均持仓:   {m['avg_holdings_count']:>10.1f}")
    print(f"  平均换手:   {m['avg_turnover']:>10.2%}")
    print(f"  基准年化:   {m['benchmark_annualized_return']:>10.2%}")

    # 月度收益
    df = pd.DataFrame(result["curve"])
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")
    monthly = df.groupby("month")["daily_return"].apply(lambda x: (1 + x).prod() - 1)

    print(f"  月度收益:")
    for idx, val in monthly.items():
        bar_len = int(abs(val) * 30)
        bar = "+" * bar_len if val > 0 else "-" * bar_len
        print(f"    {idx}: {val:>+8.2%} |{bar}")

# 汇总表
print(f"\n{'='*70}")
print(f"汇总对比")
print(f"{'='*70}")
print(f"{'K':>4} {'年化':>10} {'回撤':>10} {'Sharpe':>8} {'胜率':>8} {'盈亏比':>8}")
print(f"{'─'*52}")
for s in summary:
    print(f"{s['K']:>4} {s['ann_ret']:>10.2%} {s['max_dd']:>10.2%} "
          f"{s['sharpe']:>8.3f} {s['hit_rate']:>8.2%} {s['pl_ratio']:>8.3f}")
