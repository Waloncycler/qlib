"""梳理所有数据资产"""
import pandas as pd, json
from pathlib import Path

base = Path("/Users/walox/qlib/data/cn_stock")

print("=" * 60)
print("系统数据资产全景")
print("=" * 60)

# 1. sentiment CSV
df = pd.read_csv(base / "hierarchical/signals/market_sentiment.csv")
print(f"\n1. market_sentiment.csv")
print(f"   {len(df)} 天, {len(df.columns)} 列")
print(f"   日期: {df.iloc[0]['date']} → {df.iloc[-1]['date']}")
print(f"   列: {df.columns.tolist()}")

# 2. predictions
print(f"\n2. ML 预测")
for f in sorted((base / "predictions").glob("*.pkl")):
    p = pd.read_pickle(f)
    if isinstance(p, pd.DataFrame): p = p.iloc[:, 0]
    dates = p.index.get_level_values(0).unique()
    print(f"   {f.name}: {len(p)} 条, {dates.min().date()} → {dates.max().date()} ({len(dates)} 天)")

# 3. AI reports
with open(base / "hierarchical/signals/zizizaizai_reports.json") as f:
    reports = json.load(f)
topics = set()
for r in reports:
    for g in r.get("stock_pool", []):
        topics.add(g.get("concept", ""))
print(f"\n3. AI 早报: {len(reports)} 篇, {len(topics)} 个独立题材")

# 4. stock pools
pools = sorted((base / "stock_pools").glob("*.json"))
print(f"\n4. stock_pools: {len(pools)} 个文件")

# 5. backtest OHLCV
csvs = list((base / "backtest_ohlcv").glob("*.csv"))
# 统计日期范围
sample = pd.read_csv(csvs[0])
print(f"\n5. backtest_ohlcv: {len(csvs)} 只股票")
print(f"   日期范围: {sample.iloc[0]['date']} → {sample.iloc[-1]['date']}")

# 6. market_pulse history
pulses = sorted((base / "hierarchical/market_pulse").glob("*"))
print(f"\n6. market_pulse: {len(pulses)} 天")

# 7. 近5日情绪趋势
print(f"\n{'=' * 60}")
print("近5日情绪趋势")
print("=" * 60)
recent = df.tail(5)
for _, r in recent.iterrows():
    print(f"  {r['date']}: 涨停={r['limit_up_count']:.0f} 跌停={r['limit_down_count']:.0f} "
          f"炸板={r['broken_limit_up_count']:.0f} 情绪={r['sentiment_score']:.0f} "
          f"涨/跌={r['up_count']:.0f}/{r['down_count']:.0f}")

# 8. ML 预测 vs 实际表现
print(f"\n{'=' * 60}")
print("ML 预测准确度（近5日）")
print("=" * 60)
pred = pd.read_pickle(base / "predictions/v3_open2close.pkl")
if isinstance(pred, pd.DataFrame): pred = pred.iloc[:, 0]
pred_dates = sorted(pred.index.get_level_values(0).unique())

for d in pred_dates[-5:]:
    day_preds = pred.loc[d].dropna().sort_values(ascending=False)
    top5 = day_preds.head(5).index.tolist()
    # 检查这些股票的实际收益
    correct = 0
    total = 0
    for sym in top5:
        csv_file = base / "backtest_ohlcv" / f"{sym}.csv"
        if csv_file.exists():
            df_s = pd.read_csv(csv_file)
            df_s["date"] = df_s["date"].astype(str)
            row = df_s[df_s["date"] == str(d.date())]
            if not row.empty:
                r = row.iloc[0]
                ret = (r["close"] - r["open"]) / r["open"]
                if ret > 0:
                    correct += 1
                total += 1
    print(f"  {d.date()}: Top5 ML 预测 {correct}/{total} 上涨")

# 9. 题材连续性分析
print(f"\n{'=' * 60}")
print("近期热门题材（AI 早报推荐频次）")
print("=" * 60)
from collections import Counter
topic_counts = Counter()
recent_reports = [r for r in reports if r.get("stock_pool")][-10:]
for r in recent_reports:
    for g in r.get("stock_pool", []):
        topic_counts[g.get("concept", "")] += 1
for topic, cnt in topic_counts.most_common(10):
    print(f"  [{cnt}次] {topic}")
