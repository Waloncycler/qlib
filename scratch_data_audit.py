import pandas as pd
import numpy as np

df = pd.read_csv('data/cn_stock/hierarchical/signals/market_sentiment.csv', index_col='date')
df.index = pd.to_datetime(df.index)

print(f"Dataset range: {df.index.min()} to {df.index.max()}")
print(f"Total rows: {len(df)}")
print()

# Check ALL columns
print("=" * 80)
print("FULL COLUMN COMPLETENESS REPORT")
print("=" * 80)
for col in df.columns:
    total = len(df)
    missing = df[col].isnull().sum()
    available = total - missing
    first_valid = df[col].first_valid_index()
    last_valid = df[col].last_valid_index()
    
    # Count missing AFTER first valid index (real gap analysis)
    if first_valid is not None:
        after_first = df.loc[first_valid:]
        gaps_after_start = after_first[col].isnull().sum()
    else:
        gaps_after_start = total
    
    print(f"{col:<35} | Available: {available:>5}/{total} ({available/total*100:5.1f}%) | "
          f"First: {str(first_valid)[:10] if first_valid else 'N/A':<12} | "
          f"Last: {str(last_valid)[:10] if last_valid else 'N/A':<12} | "
          f"Gaps after start: {gaps_after_start}")

# Focus on our key indicators
print("\n" + "=" * 80)
print("KEY INDICATORS - YEARLY COMPLETENESS")
print("=" * 80)
key_cols = ['sentiment_score', 'uplimit_num', 'up_down_ratio', 'up_count', 'down_count']
df['year'] = df.index.year

for col in key_cols:
    print(f"\n--- {col} ---")
    yearly = df.groupby('year')[col].agg(
        total='count',
        missing=lambda x: x.isnull().sum(),
        available=lambda x: x.notna().sum()
    )
    yearly['pct'] = (yearly['available'] / yearly['total'] * 100).round(1)
    print(yearly.to_string())

# Check sentiment_score distribution by year
print("\n" + "=" * 80)
print("SENTIMENT_SCORE QUANTILES BY YEAR")
print("=" * 80)
for year in sorted(df['year'].unique()):
    subset = df[df['year'] == year]['sentiment_score'].dropna()
    if len(subset) > 0:
        q = subset.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
        print(f"{year}: n={len(subset):>4} | "
              f"10%={q[0.1]:5.1f} | 25%={q[0.25]:5.1f} | "
              f"50%={q[0.5]:5.1f} | 75%={q[0.75]:5.1f} | 90%={q[0.9]:5.1f}")
