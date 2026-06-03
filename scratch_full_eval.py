import pandas as pd
import qlib
from qlib.data import D
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from matplotlib.gridspec import GridSpec

# Initialize qlib
provider_uri = os.path.abspath("data/cn_stock/standard/qlib_data")
qlib.init(provider_uri=provider_uri, region="cn")

# Load market sentiment
df = pd.read_csv('data/cn_stock/hierarchical/signals/market_sentiment.csv', index_col='date')
df.index = pd.to_datetime(df.index)
df = df.ffill()

start_date = '2021-01-01'
end_date = '2026-05-18'

# Fetch Benchmark
bench_df = D.features(["SH600000"], ["$close"], start_time=start_date, end_time=end_date)
bench_df = bench_df.reset_index(level='instrument', drop=True)
bench_df.index = pd.to_datetime(bench_df.index)
bench_df['bench_ret'] = bench_df['$close'].pct_change()

# Join with sentiment
merged = bench_df.join(df[['sentiment_score', 'uplimit_num', 'up_down_ratio']], how='inner')
merged = merged.dropna(subset=['bench_ret', 'sentiment_score'])

# Current Strategy: sentiment >= 50
merged['signal'] = np.where(merged['sentiment_score'] >= 50.0, 1.0, 0.0)
merged['strat_ret'] = merged['bench_ret'] * merged['signal'].shift(1)
merged = merged.dropna(subset=['strat_ret'])

merged['cum_bench'] = (1 + merged['bench_ret']).cumprod()
merged['cum_strat'] = (1 + merged['strat_ret']).cumprod()

# ============================================================
# 1. Core Performance Metrics
# ============================================================
def calc_metrics(returns, name):
    n = len(returns)
    ann_factor = 252
    cum_ret = (1 + returns).prod() - 1
    ann_ret = (1 + cum_ret) ** (ann_factor / n) - 1
    ann_vol = returns.std() * np.sqrt(ann_factor)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    
    # Sortino
    downside = returns[returns < 0].std() * np.sqrt(ann_factor)
    sortino = ann_ret / downside if downside > 0 else 0
    
    # Max Drawdown
    cum = (1 + returns).cumprod()
    roll_max = cum.cummax()
    dd = cum / roll_max - 1
    mdd = dd.min()
    
    # Calmar
    calmar = ann_ret / abs(mdd) if mdd != 0 else 0
    
    # Win rate
    win_rate = (returns > 0).mean()
    
    # Profit Factor
    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    profit_factor = gains / losses if losses > 0 else float('inf')
    
    return {
        'Name': name,
        'Cum Return': f"{cum_ret:.2%}",
        'Ann Return': f"{ann_ret:.2%}",
        'Ann Volatility': f"{ann_vol:.2%}",
        'Sharpe': f"{sharpe:.3f}",
        'Sortino': f"{sortino:.3f}",
        'Max DD': f"{mdd:.2%}",
        'Calmar': f"{calmar:.3f}",
        'Win Rate': f"{win_rate:.2%}",
        'Profit Factor': f"{profit_factor:.2f}",
        'Trading Days': n,
    }

bench_metrics = calc_metrics(merged['bench_ret'], 'Benchmark')
strat_metrics = calc_metrics(merged['strat_ret'], 'Strategy')

print("=" * 70)
print("1. CORE PERFORMANCE METRICS")
print("=" * 70)
metrics_df = pd.DataFrame([bench_metrics, strat_metrics]).set_index('Name')
print(metrics_df.T.to_string())

# ============================================================
# 2. Signal Quality Analysis
# ============================================================
print("\n" + "=" * 70)
print("2. SIGNAL QUALITY (TIMING ACCURACY)")
print("=" * 70)

long_days = merged[merged['signal'].shift(1) == 1.0]
short_days = merged[merged['signal'].shift(1) == 0.0]

long_hit = (long_days['bench_ret'] > 0).mean() if len(long_days) > 0 else 0
short_hit = (short_days['bench_ret'] < 0).mean() if len(short_days) > 0 else 0
long_avg = long_days['bench_ret'].mean() if len(long_days) > 0 else 0
short_avg = short_days['bench_ret'].mean() if len(short_days) > 0 else 0
short_avoided_loss = short_days['bench_ret'].sum() if len(short_days) > 0 else 0

print(f"Total Trading Days: {len(merged)}")
print(f"Long Days: {len(long_days)} ({len(long_days)/len(merged):.1%})")
print(f"Short Days: {len(short_days)} ({len(short_days)/len(merged):.1%})")
print(f"Long Hit Rate (benchmark up on long day): {long_hit:.2%}")
print(f"Short Hit Rate (benchmark down on short day): {short_hit:.2%}")
print(f"Avg Return on Long Days (benchmark): {long_avg:.4%}")
print(f"Avg Return on Short Days (benchmark): {short_avg:.4%}")
print(f"Total Loss Avoided by Short Signal: {short_avoided_loss:.4%}")

# ============================================================
# 3. Signal Stability (Flip Frequency)
# ============================================================
print("\n" + "=" * 70)
print("3. SIGNAL STABILITY & HOLDING PERIOD")
print("=" * 70)

signal_changes = (merged['signal'].diff().abs() > 0).sum()
total_days = len(merged)
avg_flip_freq = signal_changes / total_days

# Calculate average holding period per signal state
runs = merged['signal'].ne(merged['signal'].shift()).cumsum()
run_lengths = merged.groupby(runs)['signal'].agg(['first', 'count'])
long_runs = run_lengths[run_lengths['first'] == 1.0]['count']
short_runs = run_lengths[run_lengths['first'] == 0.0]['count']

print(f"Total Signal Flips: {signal_changes}")
print(f"Flip Frequency: {avg_flip_freq:.2%} (per day)")
print(f"Avg Consecutive Long Days: {long_runs.mean():.1f}" if len(long_runs) > 0 else "N/A")
print(f"Max Consecutive Long Days: {long_runs.max()}" if len(long_runs) > 0 else "N/A")
print(f"Avg Consecutive Short Days: {short_runs.mean():.1f}" if len(short_runs) > 0 else "N/A")
print(f"Max Consecutive Short Days: {short_runs.max()}" if len(short_runs) > 0 else "N/A")

# ============================================================
# 4. Threshold Sensitivity Analysis
# ============================================================
print("\n" + "=" * 70)
print("4. THRESHOLD SENSITIVITY (Sentiment Score)")
print("=" * 70)

thresholds = [35, 40, 45, 48, 50, 52, 55, 60, 65]
sens_results = []
for t in thresholds:
    sig = np.where(merged['sentiment_score'] >= t, 1.0, 0.0)
    ret = merged['bench_ret'] * np.roll(sig, 1)
    ret = ret.iloc[1:]  # drop first NaN
    cum = (1 + ret).prod() - 1
    cum_curve = (1 + ret).cumprod()
    mdd = (cum_curve / cum_curve.cummax() - 1).min()
    n_long = (sig == 1).sum()
    sens_results.append({
        'Threshold': t,
        'CumRet': f"{cum:.2%}",
        'MDD': f"{mdd:.2%}",
        'LongDays': n_long,
        'LongPct': f"{n_long/len(merged):.0%}",
    })
sens_df = pd.DataFrame(sens_results)
print(sens_df.to_string(index=False))

# ============================================================
# 5. Monthly Performance Breakdown
# ============================================================
print("\n" + "=" * 70)
print("5. MONTHLY RETURN BREAKDOWN")
print("=" * 70)

merged['ym'] = merged.index.to_period('M')
monthly = merged.groupby('ym').agg(
    bench=('bench_ret', lambda x: (1+x).prod()-1),
    strat=('strat_ret', lambda x: (1+x).prod()-1),
    avg_sent=('sentiment_score', 'mean'),
    long_pct=('signal', 'mean'),
).tail(18)  # Last 18 months
monthly['excess'] = monthly['strat'] - monthly['bench']
print(monthly.to_string(float_format=lambda x: f"{x:.2%}" if abs(x) < 10 else f"{x:.1f}"))

# ============================================================
# 6. Drawdown Analysis
# ============================================================
print("\n" + "=" * 70)
print("6. DRAWDOWN EPISODES (Strategy)")
print("=" * 70)

cum_strat = (1 + merged['strat_ret']).cumprod()
dd = cum_strat / cum_strat.cummax() - 1

# Find top 5 drawdown periods
in_dd = dd < 0
dd_starts = []
dd_ends = []
i = 0
dd_vals = dd.values
while i < len(dd_vals):
    if dd_vals[i] < -0.01:  # Only consider drawdowns > 1%
        start = i
        min_val = dd_vals[i]
        min_idx = i
        while i < len(dd_vals) and dd_vals[i] < 0:
            if dd_vals[i] < min_val:
                min_val = dd_vals[i]
                min_idx = i
            i += 1
        dd_starts.append((start, min_idx, i-1 if i < len(dd_vals) else len(dd_vals)-1, min_val))
    else:
        i += 1

dd_starts.sort(key=lambda x: x[3])
print(f"{'Start Date':<14} {'Trough Date':<14} {'End Date':<14} {'Depth':>8} {'Duration':>10}")
for s, t_idx, e, depth in dd_starts[:5]:
    s_date = merged.index[s].strftime('%Y-%m-%d')
    t_date = merged.index[t_idx].strftime('%Y-%m-%d')
    e_date = merged.index[e].strftime('%Y-%m-%d')
    dur = e - s
    print(f"{s_date:<14} {t_date:<14} {e_date:<14} {depth:>8.2%} {dur:>8}d")

# ============================================================
# 7. Optimization Suggestions
# ============================================================
print("\n" + "=" * 70)
print("7. POTENTIAL OPTIMIZATION DIRECTIONS")
print("=" * 70)

# Test: Adding a smoothing (MA) to reduce noise
for window in [3, 5]:
    merged[f'sent_ma{window}'] = merged['sentiment_score'].rolling(window).mean()
    sig_ma = np.where(merged[f'sent_ma{window}'] >= 50.0, 1.0, 0.0)
    ret_ma = merged['bench_ret'] * np.roll(sig_ma, 1)
    ret_ma = pd.Series(ret_ma, index=merged.index).iloc[window:]
    cum_ma = (1 + ret_ma).prod() - 1
    mdd_ma = ((1 + ret_ma).cumprod() / (1 + ret_ma).cumprod().cummax() - 1).min()
    flips_ma = (pd.Series(sig_ma).diff().abs() > 0).sum()
    print(f"MA({window}) Smoothing: CumRet={cum_ma:.2%}, MDD={mdd_ma:.2%}, Flips={flips_ma}")

# Test: Hysteresis (different thresholds for enter/exit)
for enter, exit_ in [(55, 45), (52, 48)]:
    sig_hyst = np.zeros(len(merged))
    sig_hyst[0] = 1.0 if merged['sentiment_score'].iloc[0] >= enter else 0.0
    for i in range(1, len(merged)):
        if sig_hyst[i-1] == 0.0 and merged['sentiment_score'].iloc[i] >= enter:
            sig_hyst[i] = 1.0
        elif sig_hyst[i-1] == 1.0 and merged['sentiment_score'].iloc[i] < exit_:
            sig_hyst[i] = 0.0
        else:
            sig_hyst[i] = sig_hyst[i-1]
    ret_h = merged['bench_ret'] * np.roll(sig_hyst, 1)
    ret_h = pd.Series(ret_h, index=merged.index).iloc[1:]
    cum_h = (1 + ret_h).prod() - 1
    mdd_h = ((1 + ret_h).cumprod() / (1 + ret_h).cumprod().cummax() - 1).min()
    flips_h = (pd.Series(sig_hyst).diff().abs() > 0).sum()
    print(f"Hysteresis (Enter={enter}, Exit={exit_}): CumRet={cum_h:.2%}, MDD={mdd_h:.2%}, Flips={flips_h}")

# ============================================================
# 8. Plot comprehensive dashboard
# ============================================================
fig = plt.figure(figsize=(16, 14))
gs = GridSpec(3, 2, figure=fig, hspace=0.35, wspace=0.3)

# (a) Cumulative Returns
ax1 = fig.add_subplot(gs[0, :])
ax1.plot(merged.index, merged['cum_bench'], color='#4A90D9', label='Benchmark (Buy & Hold)', alpha=0.7)
ax1.plot(merged.index, merged['cum_strat'], color='#E8833A', label='Binary Strategy (Sent>=50)', linewidth=2)
# shade long/short regions
for i in range(1, len(merged)):
    if merged['signal'].iloc[i-1] == 1.0:
        ax1.axvspan(merged.index[i-1], merged.index[i], alpha=0.05, color='green')
    else:
        ax1.axvspan(merged.index[i-1], merged.index[i], alpha=0.05, color='red')
ax1.set_title('Cumulative Returns: Strategy vs Benchmark', fontsize=13, fontweight='bold')
ax1.set_ylabel('Cumulative Return')
ax1.legend(loc='upper left')
ax1.grid(alpha=0.3)

# (b) Sentiment Score with threshold
ax2 = fig.add_subplot(gs[1, 0])
ax2.plot(merged.index, merged['sentiment_score'], color='#666', alpha=0.6, linewidth=0.8)
ax2.axhline(50, color='red', linestyle='--', alpha=0.7, label='Threshold=50')
ax2.fill_between(merged.index, merged['sentiment_score'], 50,
                  where=merged['sentiment_score'] >= 50, alpha=0.3, color='green', label='Long Zone')
ax2.fill_between(merged.index, merged['sentiment_score'], 50,
                  where=merged['sentiment_score'] < 50, alpha=0.3, color='red', label='Short Zone')
ax2.set_title('Sentiment Score & Signal Zones', fontsize=12, fontweight='bold')
ax2.set_ylabel('Sentiment Score')
ax2.legend(loc='upper right', fontsize=8)
ax2.grid(alpha=0.3)

# (c) Drawdown comparison
ax3 = fig.add_subplot(gs[1, 1])
dd_bench = merged['cum_bench'] / merged['cum_bench'].cummax() - 1
dd_strat = merged['cum_strat'] / merged['cum_strat'].cummax() - 1
ax3.fill_between(merged.index, dd_bench, 0, alpha=0.4, color='#4A90D9', label='Benchmark DD')
ax3.fill_between(merged.index, dd_strat, 0, alpha=0.6, color='#E8833A', label='Strategy DD')
ax3.set_title('Drawdown Comparison', fontsize=12, fontweight='bold')
ax3.set_ylabel('Drawdown')
ax3.legend(loc='lower left', fontsize=8)
ax3.grid(alpha=0.3)

# (d) Threshold sensitivity
ax4 = fig.add_subplot(gs[2, 0])
sens_cum = [float(r['CumRet'].strip('%'))/100 for r in sens_results]
sens_mdd = [float(r['MDD'].strip('%'))/100 for r in sens_results]
ax4.bar([str(t) for t in thresholds], sens_cum, color='#5CB85C', alpha=0.8, label='Cum Return')
ax4_t = ax4.twinx()
ax4_t.plot([str(t) for t in thresholds], sens_mdd, color='red', marker='o', label='Max DD')
ax4.set_title('Threshold Sensitivity', fontsize=12, fontweight='bold')
ax4.set_xlabel('Sentiment Threshold')
ax4.set_ylabel('Cumulative Return')
ax4_t.set_ylabel('Max Drawdown', color='red')
ax4.legend(loc='upper left', fontsize=8)
ax4_t.legend(loc='upper right', fontsize=8)
ax4.grid(alpha=0.3)

# (e) Monthly excess return heatmap style
ax5 = fig.add_subplot(gs[2, 1])
monthly_excess = merged.groupby('ym').agg(
    excess=('strat_ret', lambda x: (1+x).prod() - 1)
).tail(18)
colors = ['#D9534F' if v < 0 else '#5CB85C' for v in monthly_excess['excess']]
ax5.bar(range(len(monthly_excess)), monthly_excess['excess'], color=colors, alpha=0.8)
ax5.set_xticks(range(0, len(monthly_excess), 3))
ax5.set_xticklabels([str(monthly_excess.index[i]) for i in range(0, len(monthly_excess), 3)], rotation=45, fontsize=8)
ax5.set_title('Monthly Strategy Returns (Last 18M)', fontsize=12, fontweight='bold')
ax5.set_ylabel('Monthly Return')
ax5.axhline(0, color='black', linewidth=0.5)
ax5.grid(alpha=0.3)

output_path = '/Users/walox/.gemini/antigravity-ide/brain/5160ce4a-1957-49e7-8ba8-d74fde576f48/strategy_evaluation.png'
plt.savefig(output_path, dpi=200, bbox_inches='tight')
print(f"\nDashboard saved to {output_path}")
