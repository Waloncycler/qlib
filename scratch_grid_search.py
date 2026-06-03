import pandas as pd
import numpy as np
import itertools

# Load market sentiment
df = pd.read_csv('data/cn_stock/hierarchical/signals/market_sentiment.csv', index_col='date')
df.index = pd.to_datetime(df.index)

# Drop columns with massive missing data
columns_to_drop = ['high20', 'high60', 'high120', 'low20', 'low60', 'low120', 'dt_net_buy_wan', 'highest_consecutive_limit_up', 'consecutive_limit_up_2_count']
df = df.drop(columns=[c for c in columns_to_drop if c in df.columns])

# We keep sentiment_score, uplimit_num, lb_2_num, tiandi_num
# Ffill the small gaps
df = df.ffill()

start_date = '2022-01-01' # using Ziruxing data range
end_date = '2026-06-02'

# Load index benchmark
bench_df = pd.read_csv('data/cn_stock/hierarchical/market/sh000001_daily.csv')
bench_df['date'] = pd.to_datetime(bench_df['date'])
bench_df = bench_df.set_index('date').sort_index()
bench_df = bench_df.loc[start_date:end_date]
bench_df['bench_ret'] = bench_df['close'].pct_change()

# Join with sentiment
merged = bench_df.join(df, how='inner')
merged = merged.dropna(subset=['bench_ret', 'sentiment_score', 'uplimit_num', 'lb_2_num', 'tiandi_num'])

print(f"Backtest period: {merged.index.min().date()} to {merged.index.max().date()}, days={len(merged)}")
bench_cum = (1 + merged['bench_ret'].fillna(0)).prod() - 1
print(f"Benchmark Cumulative Return: {bench_cum:.2%}")

# Grid Search
sentiment_thresholds = [45, 48, 50, 52, 55]
uplimit_thresholds = [20, 25, 30, 35, 40]
lb2_thresholds = [0, 2, 4, 6, 8]
tiandi_thresholds = [2, 5, 10, 15]

results = []

for s, u, b, t in itertools.product(sentiment_thresholds, uplimit_thresholds, lb2_thresholds, tiandi_thresholds):
    # Rule: long if sentiment > s AND uplimit > u AND lb_2 > b AND tiandi <= t
    condition = (merged['sentiment_score'] >= s) & \
                (merged['uplimit_num'] >= u) & \
                (merged['lb_2_num'] >= b) & \
                (merged['tiandi_num'] <= t)
    
    merged['risk'] = np.where(condition, 1.0, 0.0)
    
    # Calculate Strategy Returns
    merged['strat_ret'] = merged['bench_ret'] * merged['risk'].shift(1)
    
    strat_returns = merged['strat_ret'].dropna()
    
    if len(strat_returns) == 0:
        continue
        
    cum_strat = (1 + strat_returns).prod() - 1
    
    # MDD
    cum_prod = (1 + strat_returns).cumprod()
    roll_max = cum_prod.cummax()
    mdd = (cum_prod / roll_max - 1.0).min()
    
    # Win rate of strategy days (excluding 0 return days)
    active_returns = strat_returns[merged['risk'].shift(1) == 1.0]
    win_rate = (active_returns > 0).mean() if len(active_returns) > 0 else 0
    num_long_days = len(active_returns)
    long_pct = num_long_days / len(merged)
    
    results.append({
        'Sent': s, 'UpLimit': u, 'LB2': b, 'Tiandi': t,
        'CumRet': f"{cum_strat:.2%}", 'MDD': f"{mdd:.2%}", 
        'WinRate': f"{win_rate:.2%}", 'LongDays': num_long_days,
        'Long%': f"{long_pct:.0%}", 'RawCumRet': cum_strat
    })

res_df = pd.DataFrame(results)
res_df = res_df.sort_values(by='RawCumRet', ascending=False)
res_df = res_df.drop(columns=['RawCumRet'])

print("\nTop 20 Threshold Combinations by Cumulative Return:")
print(res_df.head(20).to_string(index=False))
