import json
import sys
import os
from pathlib import Path

# Setup path
PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from modules.backtest.service import get_signal_backtest_results

COMPARISON_FILE = PROJECT_DIR / "data" / "cn_stock" / "predictions" / "strategy_comparison.json"

def main():
    if not COMPARISON_FILE.exists():
        print("Comparison file not found.")
        return

    with open(COMPARISON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        print(f"Recalculating {item['label']} (Model={item['model']}, K={item['K']}, vol={item.get('vol')}, timing={item.get('timing')}, crash={item.get('crash')}, boost={item.get('boost')})...")
        
        enable_ml = item["model"] not in ["pure_signal", "factor_rank"]
        
        res = get_signal_backtest_results(
            enable_ml_filter=enable_ml,
            model_version=item["model"],
            top_k=item["K"],
            enable_market_timing=item.get("timing", False),
            enable_turnover_filter=item.get("vol", False),
            enable_crash_filter=item.get("crash", False),
            enable_selection_boost=item.get("boost", False)
        )
        
        if "metrics" in res:
            metrics = res["metrics"]
            item["annual"] = round(metrics.get("annualized_return", 0) * 100, 1)
            item["drawdown"] = round(metrics.get("max_drawdown", 0) * 100, 1)
            item["sharpe"] = round(metrics.get("sharpe_ratio", 0), 3)
            item["win_rate"] = round(metrics.get("hit_rate", 0) * 100, 1)
            item["pnl"] = round(metrics.get("profit_loss_ratio", 0), 3)
            print(f" -> Annual: {item['annual']}%, Drawdown: {item['drawdown']}%, Sharpe: {item['sharpe']}, Win: {item['win_rate']}%")
        else:
            print(" -> Failed to get metrics.")

    # Sort and save
    data.sort(key=lambda x: x.get("sharpe", 0), reverse=True)
    for i, item in enumerate(data):
        item["id"] = i + 1

    with open(COMPARISON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("Updated strategy_comparison.json successfully!")

if __name__ == "__main__":
    main()
