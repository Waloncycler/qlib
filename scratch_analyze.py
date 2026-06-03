import pandas as pd

df = pd.read_csv('data/cn_stock/hierarchical/signals/market_sentiment.csv', index_col='date')
df.index = pd.to_datetime(df.index)

features = [
    'sentiment_score', 'up_down_ratio', 'up_count', 'down_count',
    'high20', 'high60', 'high120',
    'low20', 'low60', 'low120',
    'uplimit_num', 'highest_consecutive_limit_up', 'consecutive_limit_up_2_count',
    'zb_num', 'lb_2_num', 'lb_3_num',
    'dt_net_buy_wan',
    'tiandi_num', 'ditian_num'
]

print("Total rows:", len(df))
print("Missing values for requested features:")
missing = df[features].isnull().sum()
print(missing)

print("\nQuantiles for available features:")
print(df[features].quantile([0.1, 0.25, 0.5, 0.75, 0.9]))

