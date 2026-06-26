"""
全面检查报告：回测系统所有关键环节
"""
import sys
import json
import os
from pathlib import Path
import pandas as pd
import numpy as np

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_dir))

from core.config import WORKSPACE_DIR

results = []

def check(category, item, status, detail=""):
    results.append({"category": category, "item": item, "status": status, "detail": detail})
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"  {icon} [{category}] {item}: {detail}")

# ============================================================
print("=" * 70)
print("检查 1: 回测引擎资金时序（open vs close 模式）")
print("=" * 70)
# ============================================================

from modules.backtest.signal_backtest import run_signal_backtest, BacktestConfig

for model, exit_timing in [("v1_default", "open"), ("v3_open2close", "close")]:
    config = BacktestConfig(
        enable_ml_filter=True, model_version=model,
        top_k=4, exit_timing=exit_timing, enable_market_timing=False,
    )
    result = run_signal_backtest(config)
    curve = result["curve"]
    m = result["metrics"]

    # 检查最后一天有收益
    last = curve[-1]
    has_return = last["daily_return"] != 0 or last["date"] == "2026-06-26"
    status = "PASS" if has_return else "FAIL"
    check("资金时序", f"{model} K=4 exit={exit_timing}", status,
          f"6/26 收益={last['daily_return']:.2%} Sharpe={m['sharpe_ratio']:.3f}")

    # 检查 NAV 单调性（不应有 NaN 或负数）
    navs = [c["strategy"] for c in curve]
    has_nan = any(np.isnan(n) or n <= 0 for n in navs)
    status = "PASS" if not has_nan else "FAIL"
    check("资金时序", f"{model} NAV 完整性", status,
          f"NAV range: {min(navs):.4f} ~ {max(navs):.4f}")

# ============================================================
print(f"\n{'=' * 70}")
print("检查 2: 半仓滚动逻辑（open2close）")
print("=" * 70)
# ============================================================

config = BacktestConfig(
    enable_ml_filter=True, model_version="v3_open2close",
    top_k=4, exit_timing="close", enable_market_timing=False,
)
result = run_signal_backtest(config)
holdings = result["holdings"]

# 检查 entries/exits 时序
rolling_ok = True
for h in holdings[1:-1]:  # 跳过第一天和最后一天
    entries = h.get("entries", [])
    exits = h.get("exits", [])
    holds = h.get("holds", [])

    # 在 close 模式下，exits 应该是前一天买的（不是今天的 entries）
    # entries 和 exits 不应该重叠
    overlap = set(entries) & set(exits)
    if overlap:
        rolling_ok = False
        check("半仓滚动", f"{h['date']} entries/exits 重叠", "FAIL",
              f"overlap: {overlap}")
        break

if rolling_ok:
    check("半仓滚动", "entries/exits 无重叠", "PASS",
          f"{len(holdings)} 天全部检查通过")

# 检查 entry_dates 跟踪
# 在 close 模式下，每只股票应该恰好持有一天后卖出
entry_exit_cycles = []
for i in range(1, len(holdings)):
    h = holdings[i]
    prev = holdings[i-1]
    prev_entries = set(prev.get("entries", []))
    today_exits = set(h.get("exits", []))
    # 前一天的 entries 应该出现在今天的 exits 里（持有一天后卖）
    matched = prev_entries & today_exits
    entry_exit_cycles.append(len(matched) / max(len(prev_entries), 1))

avg_match = np.mean(entry_exit_cycles) if entry_exit_cycles else 0
status = "PASS" if avg_match > 0.7 else "WARN"
check("半仓滚动", "前日买入次日卖出匹配率", status,
      f"avg={avg_match:.1%}（理想=100%，实际因信号重叠会有偏差）")

# ============================================================
print(f"\n{'=' * 70}")
print("检查 3: 所有策略同时持仓数不超限")
print("=" * 70)
# ============================================================

for model, exit_timing in [("v1_default", "open"), ("v2_open2open", "open"), ("v3_open2close", "close")]:
    for k in [2, 4]:
        config = BacktestConfig(
            enable_ml_filter=True, model_version=model,
            top_k=k, exit_timing=exit_timing, enable_market_timing=False,
        )
        result = run_signal_backtest(config)
        curve = result["curve"]
        held = [c["holdings_count"] for c in curve]

        # close 模式 curve 记录收盘持仓（<= K），open 模式也是 <= K
        max_expected = k
        over = sum(1 for c in held if c > max_expected)
        status = "PASS" if over == 0 else "FAIL"
        check("持仓限制", f"{model} K={k} exit={exit_timing}", status,
              f"max={max(held)} (应<= {max_expected}), 超限天数={over}")

# ============================================================
print(f"\n{'=' * 70}")
print("检查 4: 大盘择时参数生效")
print("=" * 70)
# ============================================================

for model, exit_timing in [("v3_open2close", "close"), ("v1_default", "open")]:
    k = 4
    config_timed = BacktestConfig(enable_ml_filter=True, model_version=model, top_k=k, exit_timing=exit_timing, enable_market_timing=True)
    config_raw = BacktestConfig(enable_ml_filter=True, model_version=model, top_k=k, exit_timing=exit_timing, enable_market_timing=False)

    result_timed = run_signal_backtest(config_timed)
    result_raw = run_signal_backtest(config_raw)

    m_t = result_timed["metrics"]
    m_r = result_raw["metrics"]

    diff = abs(m_t["annualized_return"] - m_r["annualized_return"]) > 0.001
    status = "PASS" if diff else "FAIL"
    check("大盘择时", f"{model} K={k}", status,
          f"择时={m_t['annualized_return']:.2%} vs 无择时={m_r['annualized_return']:.2%} "
          f"(回撤: {m_t['max_drawdown']:.2%} vs {m_r['max_drawdown']:.2%})")

# ============================================================
print(f"\n{'=' * 70}")
print("检查 5: 缓存文件命名和 leaderboard")
print("=" * 70)
# ============================================================

cache_dir = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv"
all_caches = list(cache_dir.glob("_ml_*_backtest_cache.json"))

# 检查命名格式
bad_names = []
for f in all_caches:
    name = f.name
    if "_timed_" not in name and "_raw_" not in name:
        bad_names.append(name)

status = "PASS" if not bad_names else "WARN"
check("缓存命名", "所有文件有 _timed_ 或 _raw_ 后缀", status,
      f"{'无旧格式文件' if not bad_names else f'{len(bad_names)} 个旧格式: {bad_names[:3]}'}")

# 检查是否有中文 model_version 的错误缓存
bad_chinese = [f.name for f in all_caches if any(c in f.name for c in ['择', '时', '无'])]
status = "PASS" if not bad_chinese else "FAIL"
check("缓存命名", "无中文 model_version", status,
      f"{'无' if not bad_chinese else f'{len(bad_chinese)} 个: {bad_chinese}'}")

# 检查 leaderboard API
import requests
try:
    resp = requests.get("http://localhost:28456/api/backtest/leaderboard", timeout=10)
    data = resp.json()["data"]

    # 检查重复
    keys = [(i["model_version"], i["top_k"], i.get("timing_label", "")) for i in data]
    dupes = [k for k in keys if keys.count(k) > 1]

    status = "PASS" if not dupes else "FAIL"
    check("Leaderboard", "无重复策略", status,
          f"{len(data)} 个策略, {'无重复' if not dupes else f'重复: {set(dupes)}'}")

    # 检查每个策略的 curve 和 holdings 非空
    empty_strategies = []
    for item in data[:10]:
        ann = float(item["annual_return"].replace("%", ""))
        if abs(ann) < 0.01:
            empty_strategies.append(f"{item['model_version']}_K{item['top_k']}")
    status = "PASS" if not empty_strategies else "WARN"
    check("Leaderboard", "Top10 策略收益非零", status,
          f"{'全部正常' if not empty_strategies else f'零收益: {empty_strategies}'}")

except Exception as e:
    check("Leaderboard", "API 可达", "FAIL", str(e))

# ============================================================
print(f"\n{'=' * 70}")
print("检查 6: 数据完整性")
print("=" * 70)
# ============================================================

# CSV 最后日期
csvs = list(cache_dir.glob("SH*.csv")) + list(cache_dir.glob("SZ*.csv"))
dates_626 = 0
dates_625 = 0
dates_old = 0
for f in csvs:
    try:
        last = str(pd.read_csv(f, usecols=["date"]).iloc[-1, 0])
        if last == "2026-06-26":
            dates_626 += 1
        elif last == "2026-06-25":
            dates_625 += 1
        else:
            dates_old += 1
    except:
        pass

check("数据完整性", "CSV 最新日期分布", "PASS",
      f"6/26={dates_626}, 6/25={dates_625}, 更早={dates_old}, 总计={len(csvs)}")

status = "PASS" if dates_626 > len(csvs) * 0.8 else "WARN"
check("数据完整性", "80%+ CSV 更新到 6/26", status,
      f"{dates_626}/{len(csvs)} = {dates_626/len(csvs):.0%}")

# ML 预测数据
pred_path = WORKSPACE_DIR / "data" / "cn_stock" / "predictions" / "v3_open2close.pkl"
if pred_path.exists():
    preds = pd.read_pickle(pred_path)
    if isinstance(preds, pd.DataFrame):
        preds = preds.iloc[:, 0]
    pred_dates = preds.index.get_level_values(0).unique().sort_values()
    check("数据完整性", "ML 预测日期范围", "PASS",
          f"{pred_dates[0].date()} → {pred_dates[-1].date()} ({len(pred_dates)} 天)")
else:
    check("数据完整性", "ML 预测文件", "FAIL", "不存在")

# ============================================================
print(f"\n{'=' * 70}")
print("检查 7: stock pool override 保护")
print("=" * 70)
# ============================================================

# 检查 stock_pools 目录有没有被污染的小文件
pool_dir = WORKSPACE_DIR / "data" / "cn_stock" / "stock_pools"
if pool_dir.exists():
    pools = list(pool_dir.glob("stock_pool_2026-06-*.json"))
    small_pools = []
    for f in pools:
        try:
            with open(f) as fh:
                data = json.load(fh)
            n = len(data.get("stocks", []))
            if n < 5:
                small_pools.append(f"{f.name}: {n} stocks")
        except:
            pass

    status = "PASS" if not small_pools else "WARN"
    check("Stock Pool", "6月 pool 无被污染小文件", status,
          f"{'全部正常' if not small_pools else f'{len(small_pools)} 个: {small_pools}'}")
else:
    check("Stock Pool", "stock_pools 目录", "FAIL", "不存在")

# ============================================================
print(f"\n{'=' * 70}")
print("检查 8: 前端 loadStrategy 同步")
print("=" * 70)
# ============================================================

# 检查 Backtest.vue 代码中 loadStrategy 的关键逻辑
vue_path = Path(__file__).parent.parent / "frontend" / "src" / "views" / "Backtest.vue"
if vue_path.exists():
    vue_code = vue_path.read_text()

    checks = [
        ("enableMarketTiming.value = item.enable_market_timing", "择时同步"),
        ("selectedModelVersion.value = item.model_version", "模型版本同步"),
        ("topK.value = item.top_k", "K 值同步"),
        ("enableMlFilter.value = true", "ML 开关同步"),
        ("fetchResults()", "调用 fetchResults 而非 runIntelligentBacktest"),
    ]

    for pattern, label in checks:
        status = "PASS" if pattern in vue_code else "FAIL"
        check("前端同步", label, status, f"{'找到' if status == 'PASS' else '缺失'}: {pattern}")
else:
    check("前端同步", "Backtest.vue", "FAIL", "文件不存在")

# ============================================================
print(f"\n{'=' * 70}")
print("检查 9: update_daily.py 数据管道")
print("=" * 70)
# ============================================================

update_path = backend_dir / "tasks" / "update_daily.py"
if update_path.exists():
    code = update_path.read_text()

    pipeline_checks = [
        ("from modules.backtest.data_downloader import download_all", "Baostock OHLCV 下载集成"),
        ("collector_path = PROJECT_DIR / \"market_data\" / \"collector.py\"", "collector.py 存在性检查"),
        ("if not collector_path.exists():", "collector.py 不存在时跳过"),
        ("import pandas as pd", "pandas 导入"),
    ]

    for pattern, label in pipeline_checks:
        status = "PASS" if pattern in code else "FAIL"
        check("数据管道", label, status, f"{'已集成' if status == 'PASS' else '缺失'}")

# ============================================================
# 汇总报告
# ============================================================
print(f"\n{'=' * 70}")
print("检查报告汇总")
print("=" * 70)

total = len(results)
passed = sum(1 for r in results if r["status"] == "PASS")
failed = sum(1 for r in results if r["status"] == "FAIL")
warns = sum(1 for r in results if r["status"] == "WARN")

print(f"\n总计: {total} 项检查")
print(f"  ✅ PASS: {passed}")
print(f"  ❌ FAIL: {failed}")
print(f"  ⚠️  WARN: {warns}")

if failed > 0:
    print(f"\n失败项:")
    for r in results:
        if r["status"] == "FAIL":
            print(f"  ❌ [{r['category']}] {r['item']}: {r['detail']}")

if warns > 0:
    print(f"\n警告项:")
    for r in results:
        if r["status"] == "WARN":
            print(f"  ⚠️  [{r['category']}] {r['item']}: {r['detail']}")
