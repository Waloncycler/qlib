import sys
import pandas as pd
from loguru import logger

# Add backend dir to path so we can import
sys.path.append("/Users/walox/qlib/backend")

from core.config import WORKSPACE_DIR
from modules.backtest.service import run_signal_backtest_service

def run_all():
    models = ["v1_default", "v2_open2open", "v3_open2close"]
    k_values = [3, 5, 8, 10, 15]
    results = []

    for model in models:
        for k in k_values:
            print(f"Testing Model={model}, K={k}")
            try:
                res = run_signal_backtest_service(enable_ml_filter=True, model_version=model, top_k=k)
                if "metrics" in res:
                    metrics = res["metrics"]
                    results.append({
                        "Model": model,
                        "K": k,
                        "Annual Return": f"{metrics.get('annualized_return', 0.0):.2%}",
                        "Max Drawdown": f"{metrics.get('max_drawdown', 0.0):.2%}",
                        "Sharpe Ratio": round(metrics.get("sharpe_ratio", 0.0), 3),
                        "Win Rate": f"{metrics.get('hit_rate', 0.0):.2%}"
                    })
            except Exception as e:
                print(f"Failed {model} K={k}: {e}")

    df = pd.DataFrame(results)
    print("\n--- RESULTS ---")
    print(df.to_markdown())

if __name__ == "__main__":
    run_all()
