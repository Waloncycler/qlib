import pandas as pd
import qlib
from qlib.data import D
import os

# Initialize qlib
provider_uri = os.path.abspath("data/cn_stock/standard/qlib_data")
qlib.init(provider_uri=provider_uri, region="cn")

# Load market sentiment
df = pd.read_csv('data/cn_stock/hierarchical/signals/market_sentiment.csv', index_col='date')
df.index = pd.to_datetime(df.index)
df = df.ffill()

start_date = '2026-01-01'
end_date = '2026-05-18'

# Determine risk degree
def get_risk(row):
    pe_median = row.get("pe_median", 35.0)
    sentiment_score = row.get("sentiment_score", 0.0)
    uplimit_num = row.get("uplimit_num", 0.0)
    
    if pd.isna(pe_median) or pd.isna(sentiment_score) or pd.isna(uplimit_num):
        return 0.0
        
    if sentiment_score > 40.0 and uplimit_num > 35.0 and pe_median < 33.0:
        return 1.0
    else:
        return 0.0

df['risk_degree'] = df.apply(get_risk, axis=1)

# Fetch Benchmark data (e.g. SH600000)
bench_df = D.features(["SH600000"], ["$close"], start_time=start_date, end_time=end_date)
bench_df = bench_df.reset_index(level='instrument', drop=True)
bench_df.index = pd.to_datetime(bench_df.index)

# Calculate Daily Returns
bench_df['bench_ret'] = bench_df['$close'].pct_change()
bench_df['risk_degree'] = df['risk_degree'].reindex(bench_df.index).ffill()

# Calculate Strategy Returns
bench_df['strat_ret'] = bench_df['bench_ret'] * bench_df['risk_degree'].shift(1)

# Drop NaN
bench_df = bench_df.dropna()

# Cumulative returns
bench_cum = (1 + bench_df['bench_ret']).cumprod()
strat_cum = (1 + bench_df['strat_ret']).cumprod()

print("--- Macro Score Evaluation ---")
print(f"Evaluation Period: {start_date} to {end_date}")
print(f"Benchmark Cumulative Return: {bench_cum.iloc[-1]:.4f}")
print(f"Timing Strategy Cumulative Return: {strat_cum.iloc[-1]:.4f}")

# Calculate Max Drawdown
def get_mdd(returns):
    cum = (1 + returns).cumprod()
    roll_max = cum.cummax()
    drawdown = cum / roll_max - 1.0
    return drawdown.min()

print(f"Benchmark MDD: {get_mdd(bench_df['bench_ret']):.4f}")
print(f"Timing Strategy MDD: {get_mdd(bench_df['strat_ret']):.4f}")

# Distribution of risk degrees
print("\nRisk Degree Distribution over the period:")
print(bench_df['risk_degree'].value_counts())
