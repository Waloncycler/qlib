import pandas as pd
import qlib
from qlib.data import D
import os
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# Initialize qlib
provider_uri = os.path.abspath("data/cn_stock/standard/qlib_data")
qlib.init(provider_uri=provider_uri, region="cn")

# Load market sentiment
df = pd.read_csv('data/cn_stock/hierarchical/signals/market_sentiment.csv', index_col='date')
df.index = pd.to_datetime(df.index)

# Forward fill missing data just in case
df = df.ffill()

start_date = '2021-01-01'
end_date = '2026-05-18'

# Fetch Benchmark
bench_df = D.features(["SH600000"], ["$close"], start_time=start_date, end_time=end_date)
bench_df = bench_df.reset_index(level='instrument', drop=True)
bench_df.index = pd.to_datetime(bench_df.index)
bench_df['bench_ret'] = bench_df['$close'].pct_change()

# Join with sentiment
merged = bench_df.join(df[['sentiment_score']], how='inner')
merged = merged.dropna(subset=['bench_ret', 'sentiment_score'])

# Binary Strategy Logic
merged['risk'] = np.where(merged['sentiment_score'] >= 50.0, 1.0, 0.0)

# Calculate Returns
merged['strat_ret'] = merged['bench_ret'] * merged['risk'].shift(1)
merged = merged.dropna(subset=['strat_ret'])

merged['cum_bench'] = (1 + merged['bench_ret']).cumprod()
merged['cum_strat'] = (1 + merged['strat_ret']).cumprod()

# Plotting
fig, ax1 = plt.subplots(figsize=(12, 6))

# Plot Returns on primary Y-axis
color1 = 'tab:blue'
color2 = 'tab:orange'
ax1.set_xlabel('Date')
ax1.set_ylabel('Cumulative Return', color='black')
ax1.plot(merged.index, merged['cum_bench'], color=color1, label='Benchmark', alpha=0.7)
ax1.plot(merged.index, merged['cum_strat'], color=color2, label='Binary Strategy', linewidth=2)
ax1.tick_params(axis='y', labelcolor='black')
ax1.legend(loc='upper left')

# Plot Sentiment Indicator on secondary Y-axis
ax2 = ax1.twinx()
color3 = 'tab:gray'
ax2.set_ylabel('Sentiment Score', color=color3)
ax2.plot(merged.index, merged['sentiment_score'], color=color3, alpha=0.3, label='Sentiment Score')
# Add the threshold line
ax2.axhline(50, color='red', linestyle='--', alpha=0.5, label='Threshold (50)')
ax2.tick_params(axis='y', labelcolor=color3)
ax2.set_ylim(0, 100)
ax2.legend(loc='upper right')

plt.title('Timing Strategy Performance vs Indicator (Sentiment Score)')
fig.tight_layout()

# Save image
output_path = '/Users/walox/.gemini/antigravity-ide/brain/5160ce4a-1957-49e7-8ba8-d74fde576f48/timing_curve.png'
plt.savefig(output_path, dpi=300)
print(f"Plot saved to {output_path}")
