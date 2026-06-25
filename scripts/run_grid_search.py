import sys
from pathlib import Path
sys.path.append("/Users/walox/qlib/backend")

from modules.backtest.optimizer import optimize_top_k
import pandas as pd

models = ["v1_default", "v2_open2open", "v3_open2close"]
ks = [3, 5, 8, 10, 15]

all_results = []
for m in models:
    df = optimize_top_k(model_version=m, k_values=ks)
    df['Model'] = m
    all_results.append(df)

final_df = pd.concat(all_results, ignore_index=True)
final_df = final_df.sort_values(by='Annual Return', key=lambda x: x.str.rstrip('%').astype(float), ascending=False)
final_df.to_csv("/Users/walox/qlib/data/cn_stock/backtest_ohlcv/grid_search_summary.csv", index=False)
print("GRID SEARCH COMPLETE. Results saved.")
print(final_df.to_markdown())
