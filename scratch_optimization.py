import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

# ============================================================
# LOAD DATA
# ============================================================
# Sentiment data (2021~2026)
sent_df = pd.read_csv('data/cn_stock/hierarchical/signals/market_sentiment.csv', index_col='date')
sent_df.index = pd.to_datetime(sent_df.index)
sent_df = sent_df.ffill()

# Use sentiment_score's own up_down_ratio as a proxy for market direction
# since Qlib standard data only covers 2026.
# We need a benchmark return. Use up_down_ratio to approximate market health,
# but for actual returns we need real price data.

# Load a long-running kline CSV as benchmark proxy (Shanghai Composite Index SH000001)
kline = pd.read_csv('data/cn_stock/hierarchical/market/sh000001_daily.csv')
kline['date'] = pd.to_datetime(kline['date'])
kline = kline.set_index('date').sort_index()
kline['bench_ret'] = kline['close'].pct_change()

print(f"Kline range: {kline.index.min()} to {kline.index.max()}, rows={len(kline)}")
print(f"Sentiment range: {sent_df.index.min()} to {sent_df.index.max()}, rows={len(sent_df)}")

# Merge
merged = kline[['close', 'bench_ret']].join(
    sent_df[['sentiment_score', 'uplimit_num', 'up_down_ratio', 'tiandi_num', 'lb_2_num']],
    how='inner'
)
merged = merged.dropna(subset=['bench_ret', 'sentiment_score'])
print(f"Merged range: {merged.index.min()} to {merged.index.max()}, rows={len(merged)}")
print(f"Sentiment missing after merge: {merged['sentiment_score'].isnull().sum()}")
print(f"uplimit_num missing after merge: {merged['uplimit_num'].isnull().sum()}")

# ============================================================
# HELPER
# ============================================================
def calc_metrics(returns, name):
    n = len(returns)
    ann_factor = 252
    cum_ret = (1 + returns).prod() - 1
    ann_ret = (1 + cum_ret) ** (ann_factor / n) - 1 if n > 0 else 0
    ann_vol = returns.std() * np.sqrt(ann_factor)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    downside = returns[returns < 0].std() * np.sqrt(ann_factor)
    sortino = ann_ret / downside if downside > 0 else 0
    cum = (1 + returns).cumprod()
    mdd = (cum / cum.cummax() - 1).min()
    calmar = ann_ret / abs(mdd) if mdd != 0 else 0
    win_rate = (returns > 0).mean()
    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    pf = gains / losses if losses > 0 else float('inf')
    return {
        'Name': name, 'CumRet': cum_ret, 'AnnRet': ann_ret, 'AnnVol': ann_vol,
        'Sharpe': sharpe, 'Sortino': sortino, 'MDD': mdd, 'Calmar': calmar,
        'WinRate': win_rate, 'PF': pf, 'Days': n
    }

def run_strategy(data, signal_col, name):
    data = data.copy()
    data['strat_ret'] = data['bench_ret'] * data[signal_col].shift(1)
    data = data.dropna(subset=['strat_ret'])
    data['cum_bench'] = (1 + data['bench_ret']).cumprod()
    data['cum_strat'] = (1 + data['strat_ret']).cumprod()
    flips = (data[signal_col].diff().abs() > 0).sum()
    long_days = (data[signal_col].shift(1) == 1.0).sum()
    m = calc_metrics(data['strat_ret'], name)
    m['Flips'] = flips
    m['LongDays'] = long_days
    m['LongPct'] = long_days / len(data) if len(data) > 0 else 0
    return m, data

# ============================================================
# STRATEGY VARIANTS (using full merged period)
# ============================================================

# V0: Baseline
merged['sig_v0'] = np.where(merged['sentiment_score'] >= 50.0, 1.0, 0.0)
m_bench = calc_metrics(merged['bench_ret'].dropna(), 'Benchmark (SH000001)')
m_v0, d_v0 = run_strategy(merged, 'sig_v0', 'V0: Sent>=50')

# V1: Optimized Sentiment
merged['sig_v1'] = np.where(merged['sentiment_score'] >= 55.0, 1.0, 0.0)
m_v1, d_v1 = run_strategy(merged, 'sig_v1', 'V1: Sent>=55')

# V2: Optimized Speculation (Sentiment >= 55, UpLimit >= 40, TianDi <= 2)
has_data = merged['uplimit_num'].notna() & merged['tiandi_num'].notna()
merged['sig_v2'] = 0.0
merged.loc[has_data, 'sig_v2'] = np.where(
    (merged.loc[has_data, 'sentiment_score'] >= 55.0) & 
    (merged.loc[has_data, 'uplimit_num'] >= 40) &
    (merged.loc[has_data, 'tiandi_num'] <= 2), 1.0, 0.0)
# Fallback for 2021 where Ziruxing data is missing
merged.loc[~has_data, 'sig_v2'] = np.where(
    merged.loc[~has_data, 'sentiment_score'] >= 55.0, 1.0, 0.0)
m_v2, d_v2 = run_strategy(merged, 'sig_v2', 'V2: Sent>=55 & UpLim>=40 & TD<=2')

# V3: V2 + MinHold 2d
sig_v3 = merged['sig_v2'].values.copy()
hold_count = 0
for i in range(1, len(sig_v3)):
    if sig_v3[i] != sig_v3[i-1]:
        if hold_count < 2:
            sig_v3[i] = sig_v3[i-1]
            hold_count += 1
        else:
            hold_count = 0
    else:
        hold_count += 1
merged['sig_v3'] = sig_v3
m_v3, d_v3 = run_strategy(merged, 'sig_v3', 'V3: V2 + MinHold(2d)')

# V4: V2 + MinHold 3d
sig_v4 = merged['sig_v2'].values.copy()
hold_count = 0
for i in range(1, len(sig_v4)):
    if sig_v4[i] != sig_v4[i-1]:
        if hold_count < 3:
            sig_v4[i] = sig_v4[i-1]
            hold_count += 1
        else:
            hold_count = 0
    else:
        hold_count += 1
merged['sig_v4'] = sig_v4
m_v4, d_v4 = run_strategy(merged, 'sig_v4', 'V4: V2 + MinHold(3d)')

# ============================================================
# RESULTS
# ============================================================
print("\n" + "=" * 130)
print(f"STRATEGY COMPARISON | Period: {merged.index.min().date()} to {merged.index.max().date()} | {len(merged)} trading days")
print("=" * 130)
all_metrics = [m_bench, m_v0, m_v1, m_v2, m_v3, m_v4]
header = f"{'Strategy':<35} {'CumRet':>8} {'AnnRet':>8} {'Sharpe':>7} {'Sortino':>8} {'MDD':>8} {'Calmar':>7} {'WinRate':>8} {'PF':>6} {'Flips':>6} {'Long%':>7} {'Days':>5}"
print(header)
print("-" * 130)
for m in all_metrics:
    flips = m.get('Flips', '-')
    long_pct = m.get('LongPct', '-')
    print(f"{m['Name']:<35} {m['CumRet']:>7.2%} {m['AnnRet']:>7.2%} {m['Sharpe']:>7.3f} "
          f"{m['Sortino']:>8.3f} {m['MDD']:>7.2%} {m['Calmar']:>7.3f} {m['WinRate']:>7.2%} {m['PF']:>6.2f} "
          f"{str(flips):>6} {str(f'{long_pct:.0%}') if isinstance(long_pct, float) else long_pct:>7} {m['Days']:>5}")

# Yearly Breakdown
print("\n" + "=" * 130)
print("YEARLY RETURN BREAKDOWN")
print("=" * 130)

for label, data, sig_col in [
    ('V0: Sent>=50', d_v0, 'sig_v0'),
    ('V1: Sent>=55', d_v1, 'sig_v1'),
    ('V2: Sent>=55 & UpLim>=40 & TD<=2', d_v2, 'sig_v2'),
    ('V3: V2 + MinHold(2d)', d_v3, 'sig_v3'),
]:
    print(f"\n--- {label} ---")
    data['year'] = data.index.year
    for year in sorted(data['year'].unique()):
        yr = data[data['year'] == year]
        yr_b = (1 + yr['bench_ret']).prod() - 1
        yr_s = (1 + yr['strat_ret']).prod() - 1
        yr_ex = yr_s - yr_b
        cum = (1 + yr['strat_ret']).cumprod()
        yr_mdd = (cum / cum.cummax() - 1).min()
        yr_long = (yr[sig_col].shift(1) == 1.0).mean()
        print(f"  {year}: Bench={yr_b:>7.2%}  Strat={yr_s:>7.2%}  Excess={yr_ex:>7.2%}  MDD={yr_mdd:>7.2%}  Long%={yr_long:>5.0%}")

# ============================================================
# PLOT
# ============================================================
fig = plt.figure(figsize=(18, 16))
gs = GridSpec(3, 2, figure=fig, hspace=0.35, wspace=0.3)

# (a) Cumulative returns
ax1 = fig.add_subplot(gs[0, :])
ax1.plot(d_v0.index, d_v0['cum_bench'], color='#888', label='Benchmark (SH000001)', alpha=0.6, linewidth=1)
ax1.plot(d_v0.index, d_v0['cum_strat'], color='#4A90D9', label='V0: Sent>=50', linewidth=1.2)
ax1.plot(d_v1.index, d_v1['cum_strat'], color='#E8833A', label='V1: Sent>=55', linewidth=1.2)
ax1.plot(d_v2.index, d_v2['cum_strat'], color='#9B59B6', label='V2: Sent>=55 & UpLim>=40 & TD<=2', linewidth=2.0)
ax1.plot(d_v3.index, d_v3['cum_strat'], color='#D9534F', label='V3: V2 + MinHold(2d)', linewidth=2.5)
ax1.set_title(f'Cumulative Returns: {merged.index.min().date()} ~ {merged.index.max().date()}', fontsize=13, fontweight='bold')
ax1.set_ylabel('Cumulative Return')
ax1.legend(loc='best', fontsize=9)
ax1.grid(alpha=0.3)

# (b) Sentiment Score
ax2 = fig.add_subplot(gs[1, 0])
ax2.plot(merged.index, merged['sentiment_score'], color='#666', alpha=0.5, linewidth=0.8)
ax2.axhline(50, color='red', linestyle='--', alpha=0.5, label='50 line')
ax2.axhline(55, color='green', linestyle='--', alpha=0.7, label='55 line')
ax2.fill_between(merged.index, merged['sentiment_score'], 55,
                  where=merged['sentiment_score'] >= 55, alpha=0.2, color='green')
ax2.fill_between(merged.index, merged['sentiment_score'], 55,
                  where=merged['sentiment_score'] < 55, alpha=0.2, color='red')
ax2.set_title('Sentiment Score with Signal Zones', fontsize=12, fontweight='bold')
ax2.set_ylabel('Sentiment Score')
ax2.legend(loc='upper right', fontsize=8)
ax2.grid(alpha=0.3)

# (c) Drawdown comparison
ax3 = fig.add_subplot(gs[1, 1])
dd_bench = d_v0['cum_bench'] / d_v0['cum_bench'].cummax() - 1
dd_v0 = d_v0['cum_strat'] / d_v0['cum_strat'].cummax() - 1
dd_v1 = d_v1['cum_strat'] / d_v1['cum_strat'].cummax() - 1
ax3.fill_between(d_v0.index, dd_bench, 0, alpha=0.3, color='#888', label='Benchmark DD')
ax3.fill_between(d_v0.index, dd_v0, 0, alpha=0.4, color='#4A90D9', label='V0 DD')
ax3.fill_between(d_v1.index, dd_v1, 0, alpha=0.4, color='#E8833A', label='V1 DD')
ax3.set_title('Drawdown Comparison', fontsize=12, fontweight='bold')
ax3.set_ylabel('Drawdown')
ax3.legend(loc='lower left', fontsize=8)
ax3.grid(alpha=0.3)

# (d) Yearly performance comparison
ax4 = fig.add_subplot(gs[2, 0])
d_v0['year'] = d_v0.index.year
d_v1['year'] = d_v1.index.year
years = sorted(d_v0['year'].unique())
bench_yr = [(1 + d_v0[d_v0['year']==y]['bench_ret']).prod() - 1 for y in years]
v0_yr = [(1 + d_v0[d_v0['year']==y]['strat_ret']).prod() - 1 for y in years]
v1_yr = [(1 + d_v1[d_v1['year']==y]['strat_ret']).prod() - 1 for y in years]

x = np.arange(len(years))
w = 0.25
ax4.bar(x - w, bench_yr, w, label='Benchmark', color='#888', alpha=0.8)
ax4.bar(x, v0_yr, w, label='V0: Sent>=50', color='#4A90D9', alpha=0.8)
ax4.bar(x + w, v1_yr, w, label='V1: Sent>=55', color='#E8833A', alpha=0.8)
ax4.set_xticks(x)
ax4.set_xticklabels([str(y) for y in years])
ax4.set_title('Yearly Returns by Strategy', fontsize=12, fontweight='bold')
ax4.set_ylabel('Annual Return')
ax4.legend(fontsize=8)
ax4.axhline(0, color='black', linewidth=0.5)
ax4.grid(alpha=0.3)

# (e) Sharpe / MDD comparison
ax5 = fig.add_subplot(gs[2, 1])
names_short = ['V0', 'V1', 'V2', 'V3', 'V4']
sharpes = [m_v0['Sharpe'], m_v1['Sharpe'], m_v2['Sharpe'], m_v3['Sharpe'], m_v4['Sharpe']]
mdds = [abs(m_v0['MDD']), abs(m_v1['MDD']), abs(m_v2['MDD']), abs(m_v3['MDD']), abs(m_v4['MDD'])]
x = np.arange(len(names_short))
w = 0.35
ax5.bar(x - w/2, sharpes, w, label='Sharpe', color='#4A90D9', alpha=0.8)
ax5_t = ax5.twinx()
ax5_t.bar(x + w/2, mdds, w, label='|MDD|', color='#D9534F', alpha=0.8)
ax5.set_xticks(x)
ax5.set_xticklabels(names_short)
ax5.set_ylabel('Sharpe Ratio', color='#4A90D9')
ax5_t.set_ylabel('|Max Drawdown|', color='#D9534F')
ax5.set_title('Strategy Variants: Sharpe vs MDD', fontsize=12, fontweight='bold')
ax5.legend(loc='upper left', fontsize=8)
ax5_t.legend(loc='upper right', fontsize=8)
ax5.grid(alpha=0.3)

output_path = '/Users/walox/.gemini/antigravity-ide/brain/5160ce4a-1957-49e7-8ba8-d74fde576f48/optimization_dashboard.png'
plt.savefig(output_path, dpi=200, bbox_inches='tight')
print(f"\nDashboard saved to {output_path}")
