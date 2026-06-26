"""
AI Morning Report Signal Backtest Engine.

Logic:
- Entry: Buy at open price on the day a stock first appears in a report.
- Exit: Sell at open price on the day the stock disappears from the report.
- Weight: core_stocks get 2x weight, is_new concepts get 1.5x multiplier.
- Costs: Configurable buy/sell costs.
- Benchmark: Equal-weight all-A index.
"""
import json
import math
import pandas as pd
import numpy as np
from pathlib import Path
from loguru import logger
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple

from core.config import DATA_DIR
from modules.backtest.data_downloader import load_ohlcv, load_benchmark


@dataclass
class BacktestConfig:
    """Configuration for signal backtest."""
    initial_capital: float = 10_000_000.0
    buy_cost: float = 0.0013       # 0.03% commission + 0.1% slippage
    sell_cost: float = 0.0018      # 0.03% commission + 0.05% stamp duty + 0.1% slippage
    core_weight_multiplier: float = 2.0
    new_concept_multiplier: float = 1.5
    enable_ml_filter: bool = False
    model_version: str = "v1_default"
    exit_timing: str = "open" # "open" or "close"
    top_k: int = 10
    enable_market_timing: bool = True     # 是否开启大盘择时
    market_timing_ma_days: int = 20       # 均线周期 (默认 20天)
    market_timing_down_weight: float = 0.3 # 跌破均线后的目标总仓位 (30%)


@dataclass
class DailyRecord:
    """Record for a single trading day."""
    date: str
    nav: float                        # Net asset value
    daily_return: float               # Strategy daily return
    benchmark_return: float           # Benchmark daily return
    holdings_count: int               # Number of stocks held
    turnover: float                   # Turnover ratio (0~1)
    new_entries: List[str] = field(default_factory=list)
    exits: List[str] = field(default_factory=list)


def _parse_reports() -> Dict[str, dict]:
    """Parse AI Morning Reports and return structured daily pools.
    
    For dates where a curated OpenClaw stock pool exists locally
    (data/cn_stock/stock_pools/), it OVERRIDES the zizi report pool
    to ensure trades match the curated Top Picks.
    """
    reports_path = DATA_DIR / "signals" / "zizizaizai_reports.json"
    if not reports_path.exists():
        logger.error(f"Reports file not found: {reports_path}")
        return {}

    with open(reports_path, "r", encoding="utf-8") as f:
        reports = json.load(f)

    # Build per-day pool: {date -> {symbol -> {"weight_type": "core"|"other", "is_new": bool, "concept": str}}}
    daily_pools = {}
    for r in reports:
        raw_date = r.get("created_time", "")
        if not raw_date:
            continue
        date = raw_date.split(" ")[0]

        if date not in daily_pools:
            daily_pools[date] = {}

        for pool in r.get("stock_pool", []):
            concept = pool.get("concept", "Unknown")
            is_new = pool.get("is_new", False)

            for stock in pool.get("core_stocks", []):
                sym = stock.get("symbol", "")
                if sym and not sym.startswith("BJ"):
                    existing = daily_pools[date].get(sym)
                    if not existing or existing["weight_type"] != "core":
                        daily_pools[date][sym] = {
                            "weight_type": "core",
                            "is_new": is_new or (existing["is_new"] if existing else False),
                            "concept": concept,
                            "name": stock.get("name", ""),
                        }

            for stock in pool.get("other_stocks", []):
                sym = stock.get("symbol", "")
                if sym and not sym.startswith("BJ"):
                    if sym not in daily_pools[date]:
                        daily_pools[date][sym] = {
                            "weight_type": "other",
                            "is_new": is_new,
                            "concept": concept,
                            "name": stock.get("name", ""),
                        }

    # --- Apply curated pool overrides (moved to pool_generator) ---
    from modules.backtest.pool_generator import apply_curated_overrides
    return apply_curated_overrides(daily_pools)


def _compute_target_weights(
    pool: Dict[str, dict],
    config: BacktestConfig
) -> Dict[str, float]:
    """Compute normalized target weights for a daily pool."""
    raw_weights = {}
    for sym, info in pool.items():
        w = 1.0
        if info["weight_type"] == "core":
            w *= config.core_weight_multiplier
        if info["is_new"]:
            w *= config.new_concept_multiplier
        raw_weights[sym] = w

    total = sum(raw_weights.values())
    if total == 0:
        return {}
    return {sym: w / total for sym, w in raw_weights.items()}


def _load_all_prices(symbols: Set[str]) -> Dict[str, pd.DataFrame]:
    """Load OHLCV DataFrames for all symbols, indexed by date."""
    prices = {}
    for sym in symbols:
        df = load_ohlcv(sym)
        if not df.empty:
            df = df.set_index("date").sort_index()
            prices[sym] = df
    return prices


def run_signal_backtest(config: Optional[BacktestConfig] = None) -> dict:
    """
    Run the full signal backtest.

    Returns dict with:
        - curve: [{date, strategy_nav, benchmark_nav, strategy_return, benchmark_return, holdings_count, turnover}]
        - metrics: {annualized_return, max_drawdown, sharpe, information_ratio, hit_rate, profit_loss_ratio}
        - holdings: [{date, entries: [...], exits: [...], holding: [...]}]
        - concept_attribution: [{concept, total_return, avg_daily_return, days_active, hit_rate}]
    """
    if config is None:
        config = BacktestConfig()

    logger.info("Parsing AI Morning Reports...")
    daily_pools = _parse_reports()
    if not daily_pools:
        return {"curve": [], "metrics": {}, "holdings": [], "concept_attribution": []}

    sorted_dates = sorted(daily_pools.keys())
    logger.info(f"Report dates: {sorted_dates[0]} → {sorted_dates[-1]} ({len(sorted_dates)} days)")

    # Collect all unique symbols
    all_symbols = set()
    for pool in daily_pools.values():
        all_symbols.update(pool.keys())
    logger.info(f"Total unique symbols: {len(all_symbols)}")

    # Load prices
    logger.info("Loading OHLCV data...")
    prices = _load_all_prices(all_symbols)
    logger.info(f"Loaded prices for {len(prices)} / {len(all_symbols)} symbols")

    # Load ML predictions if enabled
    ml_preds = None
    if config.enable_ml_filter:
        from core.config import WORKSPACE_DIR
        pred_path = WORKSPACE_DIR / "data" / "cn_stock" / "predictions" / f"{config.model_version}.pkl"
        if pred_path.exists():
            logger.info("Loading ML predictions for filtering...")
            ml_preds = pd.read_pickle(pred_path)
            # Ensure it's a series or dataframe. Qlib pred.pkl is usually a pd.Series or pd.DataFrame with multi-index (datetime, instrument)
            if isinstance(ml_preds, pd.DataFrame) and ml_preds.shape[1] == 1:
                ml_preds = ml_preds.iloc[:, 0]
            
            # Convert instrument index to uppercase to match signal_backtest logic
            if isinstance(ml_preds.index, pd.MultiIndex):
                # The second level is usually 'instrument'
                new_idx = ml_preds.index.set_levels(ml_preds.index.levels[1].str.upper(), level=1)
                ml_preds.index = new_idx
        else:
            logger.warning(f"ML filter enabled but {pred_path} not found. Skipping ML filter.")
            config.enable_ml_filter = False

    # Load benchmark
    benchmark_df = load_benchmark()
    if not benchmark_df.empty:
        benchmark_df = benchmark_df.set_index("date").sort_index()
        # Calculate Moving Average for Market Timing
        if config.enable_market_timing:
            ma_col = f"ma{config.market_timing_ma_days}"
            benchmark_df[ma_col] = benchmark_df["close"].rolling(window=config.market_timing_ma_days).mean()

    # --- Core backtest loop ---
    capital = config.initial_capital
    current_holdings: Dict[str, float] = {}  # symbol -> weight
    current_shares: Dict[str, float] = {}    # symbol -> num_shares
    current_entry_prices: Dict[str, float] = {}  # symbol -> entry open price
    current_entry_dates: Dict[str, str] = {}  # symbol -> 买入日期（用于判断持仓天数）

    records: List[dict] = []
    concept_returns: Dict[str, List[float]] = {}  # concept -> [daily_returns]
    daily_holdings_log: List[dict] = []

    prev_nav = capital
    cash = capital
    cumulative_strategy = 0.0

    for day_idx, date_str in enumerate(sorted_dates):
        date_ts = pd.Timestamp(date_str)
        today_pool = daily_pools[date_str]

        # ML Filter: Keep only Top K scored stocks in today's pool
        latest_ml_date = None
        if config.enable_ml_filter and ml_preds is not None:
            try:
                available_dates = ml_preds.index.get_level_values(0).unique()
                # STRICTLY LESS THAN date_ts to prevent look-ahead bias (未来函数)
                # We trade at the open of date_ts, so we can only use ML scores generated after the close of the PREVIOUS day.
                valid_dates = available_dates[available_dates < date_ts]
                
                if not valid_dates.empty:
                    latest_ml_date = valid_dates.max()
                    day_preds = ml_preds.loc[latest_ml_date]
                    
                    # Filter to only stocks in today_pool
                    pool_syms = list(today_pool.keys())
                    valid_preds = day_preds.reindex(pool_syms).dropna()
                    
                    if not valid_preds.empty:
                        # Apply Historical Proxy Multipliers (Hybrid Scoring for Backtest)
                        # We use LLM tags as a proxy for Popularity/Risk to avoid 10,000+ API calls during backtest
                        adjusted_preds = valid_preds.copy()
                        for sym in valid_preds.index:
                            info = today_pool.get(sym, {})
                            multiplier = 1.0
                            if info.get("weight_type") == "core":
                                multiplier += 0.5
                            if info.get("is_new"):
                                multiplier += 0.2
                            adjusted_preds[sym] = adjusted_preds[sym] * multiplier
                        
                        # Sort by adjusted score descending and take Top K
                        top_syms = adjusted_preds.sort_values(ascending=False).head(config.top_k).index.tolist()
                        
                        # --- OVERRIDE FOR THE FINAL DAY ---
                        # To ensure the backtest's "today" perfectly matches the live "Today's Top Picks",
                        # we fetch the real-time popularity-filtered picks on the very last day of the backtest.
                        if day_idx == len(sorted_dates) - 1:
                            logger.info(f"Checking override for final day: {date_str}, day_idx={day_idx}, len={len(sorted_dates)}")
                            try:
                                from modules.backtest.service import get_todays_picks_service
                                live_res = get_todays_picks_service(model_version=config.model_version, top_k=config.top_k)
                                logger.info(f"live_res: {str(live_res)[:500]}")
                                if live_res.get("status") == "success" and "top_picks" in live_res:
                                    live_syms = [p["symbol"] for p in live_res["top_picks"]]
                                    if live_syms:
                                        top_syms = live_syms
                                        logger.info(f"Final day override: using {len(top_syms)} live picks for {date_str}: {top_syms}")
                                        
                                        # SAVE TO FILE SO IT IS NOT WIPED OUT TOMORROW
                                        try:
                                            from core.config import WORKSPACE_DIR
                                            fpath = WORKSPACE_DIR / "data" / "cn_stock" / "stock_pools" / f"stock_pool_{date_str}.json"
                                            
                                            # 安全检查：如果已有 pool 文件包含更多股票，不要覆盖
                                            skip_write = False
                                            if fpath.exists():
                                                try:
                                                    with open(fpath, "r", encoding="utf-8") as ef:
                                                        existing = json.load(ef)
                                                    existing_count = len(existing.get("stocks", []))
                                                    if existing_count > len(live_res["top_picks"]):
                                                        logger.info(f"Skip override: existing pool has {existing_count} stocks > live {len(live_res['top_picks'])} picks")
                                                        skip_write = True
                                                except Exception:
                                                    pass
                                            
                                            if not skip_write:
                                                pool_data_to_save = {
                                                    "date": f"{date_str} 09:00:00",
                                                    "stocks": [
                                                        {
                                                            "code": p["symbol"].replace("SH", "").replace("SZ", "").replace("BJ", ""),
                                                            "name": p["name"],
                                                            "theme": p.get("popularity", "人气热点叠加")
                                                        } for p in live_res["top_picks"]
                                                    ]
                                                }
                                                with open(fpath, "w", encoding="utf-8") as f:
                                                    json.dump(pool_data_to_save, f, ensure_ascii=False, indent=2)
                                                logger.info(f"Persisted final day override to {fpath}")
                                        except Exception as write_err:
                                            logger.error(f"Failed to persist final day override: {write_err}")
                                            
                                    else:
                                        logger.warning("live_syms is empty")
                                else:
                                    logger.warning(f"live_res is invalid: {str(live_res)[:500]}")
                            except Exception as e:
                                import traceback
                                logger.error(f"Failed to override final day picks: {traceback.format_exc()}")
                        # Truncate today_pool to only include the top syms
                        today_pool = {s: info for s, info in today_pool.items() if s in top_syms}
                    else:
                        logger.warning(f"valid_preds is empty for {date_str}")
                        today_pool = {}  # No ML scores available for today's pool
                else:
                    logger.warning(f"valid_dates is empty for {date_str}")
                    today_pool = {} # No ML predictions available before this date
            except Exception as e:
                logger.error(f"Error applying ML filter on {date_str}: {e}")
                today_pool = {} # Fail-safe to avoid buying the entire pool

        # Determine target portfolio
        target_weights = _compute_target_weights(today_pool, config)

        # ---------------------------------------------------------
        # Intended trades (for UI display even if data is missing)
        # ---------------------------------------------------------
        prev_symbols_intended = set(current_holdings.keys())
        target_symbols_intended = set(target_weights.keys())
        intended_entries = list(target_symbols_intended - prev_symbols_intended)
        intended_exits = list(prev_symbols_intended - target_symbols_intended)
        intended_holds = list(prev_symbols_intended & target_symbols_intended)

        # ---------------------------------------------------------
        # Critical Fix: Check if market data for today exists
        # We only need to verify if the required symbols for today (holds + entries + exits) have prices.
        # If the majority of our specific target portfolio is missing data, assume data isn't published yet.
        # ---------------------------------------------------------
        required_syms = prev_symbols_intended.union(target_symbols_intended)
        missing_required = 0
        if len(required_syms) > 0:
            missing_required = sum(1 for sym in required_syms if sym not in prices or date_ts not in prices[sym].index)
            
        if len(required_syms) > 0 and missing_required >= (len(required_syms) * 0.5):
            # Log missing data and carry over previous state
            logger.warning(f"Market data missing for {date_str}. Rolling forward previous NAV. Recording intended trades.")
            records.append({
                "date": date_str,
                "nav": round(prev_nav, 2),
                "daily_return": 0.0,
                "benchmark_return": 0.0,
                "holdings_count": len(current_shares),
                "turnover": 0.0,
            })
            
            synthetic_trades = []
            live_quotes = {}
            if date_str == pd.Timestamp.now().strftime("%Y-%m-%d"):
                try:
                    from modules.backtest.service import get_live_quotes_service
                    all_query_syms = list(set(current_shares.keys()).union(set(intended_entries)).union(set(intended_exits)))
                    res = get_live_quotes_service(all_query_syms)
                    if res and res.get("status") == "success":
                        live_quotes = res.get("data", {})
                except Exception as e:
                    logger.error(f"Failed to fetch live quotes for missing day fallback: {e}")

            for sym in intended_exits:
                if sym in live_quotes and live_quotes[sym].get("open_price", 0) > 0:
                    shares = current_shares.get(sym, 0)
                    oprice = live_quotes[sym]["open_price"]
                    amount = shares * oprice
                    fee = amount * config.sell_cost
                    synthetic_trades.append({
                        "symbol": sym,
                        "action": "sell",
                        "reason": "exit",
                        "price": round(oprice, 3),
                        "shares": round(shares, 2),
                        "amount": round(amount, 2),
                        "fee": round(fee, 2)
                    })
            for sym in intended_entries:
                if sym in live_quotes and live_quotes[sym].get("open_price", 0) > 0:
                    synthetic_trades.append({
                        "symbol": sym,
                        "action": "buy",
                        "reason": "entry",
                        "price": round(live_quotes[sym]["open_price"], 3),
                        "shares": "-",
                        "amount": "-",
                        "fee": "-"
                    })
            
            holding_syms = []
            all_involved = set(current_shares.keys()).union(set(intended_exits)).union(set(intended_entries))
            for sym in sorted(all_involved):
                info = today_pool.get(sym)
                if not info:
                    info = daily_pools[date_str].get(sym)
                if not info and day_idx > 0:
                    info = daily_pools[sorted_dates[day_idx-1]].get(sym)
                if not info:
                    info = {"name": "", "weight_type": "", "concept": ""}
                
                score = None
                if config.enable_ml_filter and ml_preds is not None and latest_ml_date is not None:
                    try:
                        if sym in ml_preds.loc[latest_ml_date].index:
                            score = round(float(ml_preds.loc[latest_ml_date, sym]), 4)
                    except:
                        pass
                
                ret = None
                if sym in live_quotes:
                    lq = live_quotes[sym]
                    if sym in intended_exits and lq.get("yesterday_close", 0) > 0:
                        if config.exit_timing == "close" and lq.get("price", 0) > 0:
                            ret = round((lq["price"] - lq["yesterday_close"]) / lq["yesterday_close"], 4)
                        elif config.exit_timing == "open" and lq.get("open_price", 0) > 0:
                            ret = round((lq["open_price"] - lq["yesterday_close"]) / lq["yesterday_close"], 4)
                    elif sym in intended_holds and lq.get("pct_change") is not None:
                        ret = round(float(lq["pct_change"]) / 100.0, 4)
                        
                if ret is None and sym in prices and date_ts in prices[sym].index:
                    try:
                        pct = float(prices[sym].loc[date_ts, "pct_change"])
                        if not math.isnan(pct):
                            ret = round(pct / 100.0, 4)
                    except:
                        pass

                holding_syms.append({
                    "symbol": sym,
                    "name": info.get("name", sym),
                    "type": "carry_over",
                    "concept": info.get("concept", ""),
                    "score": score,
                    "ret": ret
                })
                
            daily_holdings_log.append({
                "date": date_str,
                "entries": intended_entries,
                "exits": intended_exits,
                "holds": intended_holds,
                "holdings": holding_syms,
                "trades": synthetic_trades,
                "daily_return": 0.0,
            })
            continue

        # Filter to symbols we have price data for
        tradeable_targets = {}
        for sym, w in target_weights.items():
            if sym in prices:
                pdf = prices[sym]
                if date_ts in pdf.index:
                    tradeable_targets[sym] = w

        # Calculate intended total weight (Market Timing Filter)
        intended_total_weight = 1.0
        if config.enable_market_timing and not benchmark_df.empty and date_ts in benchmark_df.index:
            ma_col = f"ma{config.market_timing_ma_days}"
            bench_close = benchmark_df.loc[date_ts, "close"]
            bench_ma = benchmark_df.loc[date_ts, ma_col]
            if pd.notna(bench_ma) and bench_close < bench_ma:
                intended_total_weight = config.market_timing_down_weight

        # Re-normalize after filtering, applying the intended total weight
        total_w = sum(tradeable_targets.values())
        if total_w > 0:
            tradeable_targets = {s: (w / total_w) * intended_total_weight for s, w in tradeable_targets.items()}

        # Identify entries and exits
        prev_symbols = set(current_holdings.keys())
        target_symbols = set(tradeable_targets.keys())

        if config.exit_timing == "close":
            # === 半仓滚动模式 ===
            # 规则：
            # 1. 昨天买的股票如果今天还在 ML Top K → 继续持有（holds），不卖不买，省手续费
            # 2. 昨天买的股票如果今天不在 ML Top K → 收盘卖出（exits）
            # 3. 今天 ML Top K 中的新股票 → 开盘买入（entries）
            exits = set()
            for sym in prev_symbols:
                entry_date = current_entry_dates.get(sym, "")
                if entry_date != date_str:  # 不是今天买的 → 持了一天以上
                    if sym not in target_symbols:
                        exits.add(sym)  # 不在今天的信号里 → 卖出
                    # else: 信号重叠 → 继续持有，省手续费
            new_entries = target_symbols - prev_symbols  # 只有全新的才买入
            holds = prev_symbols - exits  # 继续持有的（今天买的 + 信号重叠的）
        else:
            # === 开盘卖出模式 ===
            new_entries = target_symbols - prev_symbols
            exits = prev_symbols - target_symbols
            holds = prev_symbols & target_symbols

        # --- Process exits: sell at today's open ---
        daily_trades = []
        exit_proceeds = 0.0
        exit_symbols = []
        for sym in exits:
            if sym in prices and date_ts in prices[sym].index:
                if config.exit_timing == "close":
                    sell_price = prices[sym].loc[date_ts, "close"]
                else:
                    sell_price = prices[sym].loc[date_ts, "open"]
                shares = current_shares.get(sym, 0)
                gross_proceeds = shares * sell_price
                fee = gross_proceeds * config.sell_cost
                proceeds = gross_proceeds - fee
                exit_proceeds += proceeds
                exit_symbols.append(sym)
                if shares > 0:
                    daily_trades.append({
                        "symbol": sym,
                        "action": "sell",
                        "reason": "exit",
                        "price": round(sell_price, 3),
                        "shares": round(shares, 2),
                        "amount": round(gross_proceeds, 2),
                        "fee": round(fee, 2)
                    })

        # Remove exited positions from tracking (but capital not yet available if close exit)
        # For exit_timing="close": 固定半仓滚动模式
        #   - 开盘买入只用 50% 总资金
        #   - 收盘卖出上一交易日的仓位（资金次日才可用）
        # For exit_timing="open": 开盘卖出+开盘买入，资金立即可用，100%仓位
        close_exit_pending_proceeds = 0.0
        if config.exit_timing == "close":
            # === 固定半仓滚动模式 ===
            # 收盘卖出旧仓的资金要到收盘才到账
            close_exit_pending_proceeds = exit_proceeds
            for sym in exits:
                current_holdings.pop(sym, None)
                current_shares.pop(sym, None)
                current_entry_prices.pop(sym, None)
                current_entry_dates.pop(sym, None)

            # 计算当前总资产（开盘价）
            portfolio_value_at_open = cash
            for sym in holds:
                if sym in prices and date_ts in prices[sym].index:
                    portfolio_value_at_open += current_shares[sym] * prices[sym].loc[date_ts, "open"]
                else:
                    portfolio_value_at_open += current_shares.get(sym, 0) * current_entry_prices.get(sym, 0)

            # 半仓买入：只用 50% 的总资产分配给新目标
            # 大盘择时：跌破均线时降低仓位（intended_total_weight 已在上面计算）
            available_capital = portfolio_value_at_open * 0.5 * intended_total_weight

            # 重新分配权重：只在新 entries 之间分配 available_capital
            entry_targets = {s: w for s, w in tradeable_targets.items() if s in new_entries}
            hold_targets = {s: w for s, w in tradeable_targets.items() if s in holds}

            # 合并：holds 保持原仓位不变，entries 用半仓资金分配
            # 重写 tradeable_targets，让 entries 用半仓资金等权分配
            if entry_targets:
                entry_total = sum(entry_targets.values())
                for s in entry_targets:
                    entry_targets[s] = (entry_targets[s] / entry_total) * available_capital  # 绝对金额
        else:
            # === 开盘卖出模式（100% 仓位）===
            for sym in exits:
                current_holdings.pop(sym, None)
                current_shares.pop(sym, None)
                current_entry_prices.pop(sym, None)
            portfolio_value_at_open = cash + exit_proceeds
            for sym in holds:
                if sym in prices and date_ts in prices[sym].index:
                    portfolio_value_at_open += current_shares[sym] * prices[sym].loc[date_ts, "open"]
                else:
                    portfolio_value_at_open += current_shares.get(sym, 0) * current_entry_prices.get(sym, 0)
            entry_targets = None  # 使用默认逻辑

        # --- Rebalance: We rebalance all holdings to target weights ---
        entry_symbols = []
        new_shares = {}
        new_entry_prices = {}

        if config.exit_timing == "close" and entry_targets is not None:
            # === 半仓滚动模式 ===
            # holds 保持原仓位不变，entries 用半仓资金买入
            new_cash = cash  # 初始 cash（不含收盘到账的 exit_proceeds）
            new_entry_dates = {}
            for sym in list(current_shares.keys()):
                new_shares[sym] = current_shares[sym]  # 保持 holds
                new_entry_prices[sym] = current_entry_prices.get(sym, 0)
                new_entry_dates[sym] = current_entry_dates.get(sym, "")

            for sym, allocated_amount in entry_targets.items():
                if sym in prices and date_ts in prices[sym].index:
                    buy_price = prices[sym].loc[date_ts, "open"]
                    if buy_price > 0:
                        trade_fee = allocated_amount * config.buy_cost
                        net_allocated = allocated_amount - trade_fee
                        shares = net_allocated / buy_price
                        new_shares[sym] = shares
                        new_entry_prices[sym] = buy_price
                        new_entry_dates[sym] = date_str  # 记录买入日期
                        new_cash -= allocated_amount
                        entry_symbols.append(sym)

                        daily_trades.append({
                            "symbol": sym,
                            "action": "buy",
                            "reason": "entry",
                            "price": round(buy_price, 3),
                            "shares": round(allocated_amount / buy_price, 2),
                            "amount": round(allocated_amount, 2),
                            "fee": round(trade_fee, 2)
                        })
        else:
            # === 100% 仓位模式（open2open）===
            new_cash = portfolio_value_at_open
            for sym, weight in tradeable_targets.items():
                if sym in prices and date_ts in prices[sym].index:
                    buy_price = prices[sym].loc[date_ts, "open"]
                    if buy_price > 0:
                        allocated = portfolio_value_at_open * weight
                        current_val = 0
                        if sym in holds:
                            current_val = current_shares[sym] * buy_price
                        diff = allocated - current_val
                        trade_action = ""
                        trade_fee = 0.0
                        trade_amount = abs(diff)
                        if diff > 0:
                            trade_fee = diff * config.buy_cost
                            allocated -= trade_fee
                            trade_action = "buy"
                        elif diff < 0:
                            trade_fee = abs(diff) * config.sell_cost
                            allocated += trade_fee
                            trade_action = "sell"

                        if sym in new_entries:
                            entry_symbols.append(sym)

                        shares = allocated / buy_price
                        new_shares[sym] = shares
                        new_entry_prices[sym] = buy_price
                        new_cash -= allocated

                        if trade_amount > 100:
                            daily_trades.append({
                                "symbol": sym,
                                "action": trade_action,
                                "reason": "entry" if sym in new_entries else "rebalance",
                                "price": round(buy_price, 3),
                                "shares": round(trade_amount / buy_price, 2),
                                "amount": round(trade_amount, 2),
                                "fee": round(trade_fee, 2)
                            })

        current_shares = new_shares
        # current_holdings 应反映所有持仓（holds + entries），不只 targets
        current_holdings = {sym: 1.0 for sym in new_shares.keys()}
        current_entry_prices.update(new_entry_prices)
        if config.exit_timing == "close":
            current_entry_dates = new_entry_dates
        # 收盘卖出资金到账 + 扣除买入支出
        cash = max(0, new_cash + close_exit_pending_proceeds)

        # --- Calculate end-of-day NAV (mark to close) ---
        eod_nav = cash
        stock_returns_today = {}
        for sym, shares in current_shares.items():
            if sym in prices and date_ts in prices[sym].index:
                close_price = prices[sym].loc[date_ts, "close"]
                open_price = prices[sym].loc[date_ts, "open"]
                eod_nav += shares * close_price
                if open_price > 0:
                    stock_returns_today[sym] = (close_price - open_price) / open_price
            else:
                eod_nav += shares * current_entry_prices.get(sym, 0)

        if eod_nav == 0 and len(current_shares) > 0:
            eod_nav = prev_nav  # Fallback

        daily_return = (eod_nav - prev_nav) / prev_nav if prev_nav > 0 else 0.0

        # Benchmark return
        bench_return = 0.0
        if not benchmark_df.empty and date_ts in benchmark_df.index:
            bench_close = benchmark_df.loc[date_ts, "close"]
            bench_open = benchmark_df.loc[date_ts, "open"]
            if bench_open > 0:
                bench_return = (bench_close - bench_open) / bench_open

        # Turnover
        turnover = (len(new_entries) + len(exits)) / max(len(target_symbols), 1)

        # Track concept attribution
        for sym, ret in stock_returns_today.items():
            if sym in today_pool:
                concept = today_pool[sym]["concept"]
                if concept not in concept_returns:
                    concept_returns[concept] = []
                concept_returns[concept].append(ret)

        records.append({
            "date": date_str,
            "nav": round(eod_nav, 2),
            "daily_return": round(daily_return, 6),
            "benchmark_return": round(bench_return, 6),
            "holdings_count": len(current_shares),
            "turnover": round(turnover, 4),
        })

        # Holdings log
        holding_syms = []
        all_involved = set(current_shares.keys()).union(set(exits)).union(set(entry_symbols))
        for sym in sorted(all_involved):
            info = today_pool.get(sym)
            if not info:
                info = daily_pools[date_str].get(sym)
            if not info and day_idx > 0:
                info = daily_pools[sorted_dates[day_idx-1]].get(sym)
            if not info:
                info = {"name": "", "weight_type": "", "concept": ""}
                
            score = None
            if config.enable_ml_filter and ml_preds is not None and latest_ml_date is not None:
                try:
                    if sym in ml_preds.loc[latest_ml_date].index:
                        score = round(float(ml_preds.loc[latest_ml_date, sym]), 4)
                except:
                    pass
            
            ret = None
            if sym in prices and date_ts in prices[sym].index:
                try:
                    open_p = float(prices[sym].loc[date_ts, "open"])
                    close_p = float(prices[sym].loc[date_ts, "close"])
                    pct = float(prices[sym].loc[date_ts, "pct_change"]) / 100.0
                    
                    if not math.isnan(pct):
                        if sym in entry_symbols:
                            if open_p > 0:
                                ret = round((close_p - open_p) / open_p, 4)
                        elif sym in exit_symbols:
                            pre_close = close_p / (1 + pct) if pct != -1.0 else open_p
                            if pre_close > 0:
                                ret = round((open_p - pre_close) / pre_close, 4)
                        else:
                            ret = round(pct, 4)
                except:
                    pass
                    
            weight = 0.0
            if eod_nav > 0 and sym in current_shares:
                if sym in prices and date_ts in prices[sym].index:
                    try:
                        c_p = float(prices[sym].loc[date_ts, "close"])
                        weight = round((current_shares[sym] * c_p) / eod_nav, 4)
                    except:
                        pass
                else:
                    weight = round((current_shares[sym] * current_entry_prices.get(sym, 0)) / eod_nav, 4)

            holding_syms.append({
                "symbol": sym,
                "name": info.get("name", ""),
                "type": info.get("weight_type", ""),
                "concept": info.get("concept", ""),
                "score": score,
                "weight": weight,
                "ret": ret
            })

        daily_holdings_log.append({
            "date": date_str,
            "entries": entry_symbols,
            "exits": exit_symbols,
            "holds": list(holds),
            "holdings": holding_syms,
            "trades": daily_trades,
            "daily_return": round(daily_return, 6),
        })

        prev_nav = eod_nav

    # --- Compute aggregate metrics ---
    if not records:
        return {"curve": [], "metrics": {}, "holdings": [], "concept_attribution": []}

    returns_series = pd.Series([r["daily_return"] for r in records])
    bench_series = pd.Series([r["benchmark_return"] for r in records])

    # NAV curves
    strategy_cumulative = (1 + returns_series).cumprod()
    benchmark_cumulative = (1 + bench_series).cumprod()

    # Annualized return (assume 244 trading days)
    total_days = len(records)
    total_return = strategy_cumulative.iloc[-1] - 1
    ann_return = (1 + total_return) ** (244 / max(total_days, 1)) - 1

    # Max drawdown
    running_max = strategy_cumulative.cummax()
    drawdown = (strategy_cumulative - running_max) / running_max
    
    drawdown_periods = []
    if len(drawdown) > 0 and not drawdown.isna().all():
        end_idx = drawdown.idxmin()
        max_drawdown = drawdown.min()
        start_idx = strategy_cumulative.iloc[:end_idx + 1].idxmax()
        max_dd_start = records[start_idx]["date"]
        max_dd_end = records[end_idx]["date"]
        
        # Find all drawdowns > 20% + the max drawdown
        underwater = drawdown < 0
        blocks = (~underwater).cumsum()
        for block_id, group in drawdown.groupby(blocks):
            group_min = group.min()
            if group_min < 0:
                is_global_max = (group.idxmin() == end_idx)
                if group_min <= -0.20 or is_global_max:
                    trough_idx = group.idxmin()
                    peak_idx = max(0, group.index[0] - 1)
                    drawdown_periods.append({
                        "start": records[peak_idx]["date"],
                        "end": records[trough_idx]["date"],
                        "drawdown": round(float(group_min), 4)
                    })
    else:
        max_drawdown = 0.0
        max_dd_start = ""
        max_dd_end = ""

    # Sharpe ratio (annualized, rf=0)
    sharpe = (returns_series.mean() / returns_series.std() * np.sqrt(244)) if returns_series.std() > 0 else 0.0

    # Information ratio (excess return vs benchmark)
    excess = returns_series - bench_series
    ir = (excess.mean() / excess.std() * np.sqrt(244)) if excess.std() > 0 else 0.0

    # Hit rate (% of days with positive return)
    hit_rate = (returns_series > 0).sum() / max(len(returns_series), 1)

    # Profit/loss ratio
    gains = returns_series[returns_series > 0]
    losses = returns_series[returns_series < 0]
    avg_gain = gains.mean() if len(gains) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 1
    profit_loss_ratio = avg_gain / avg_loss if avg_loss > 0 else 0

    # Benchmark metrics
    bench_total = benchmark_cumulative.iloc[-1] - 1
    bench_ann = (1 + bench_total) ** (244 / max(total_days, 1)) - 1

    metrics = {
        "total_return": round(float(total_return), 4),
        "annualized_return": round(float(ann_return), 4),
        "max_drawdown": round(float(max_drawdown), 4),
        "max_drawdown_start": max_dd_start,
        "max_drawdown_end": max_dd_end,
        "drawdown_periods": drawdown_periods,
        "sharpe_ratio": round(float(sharpe), 3),
        "information_ratio": round(float(ir), 3),
        "hit_rate": round(float(hit_rate), 4),
        "profit_loss_ratio": round(float(profit_loss_ratio), 3),
        "total_trading_days": total_days,
        "avg_holdings_count": round(float(np.mean([r["holdings_count"] for r in records])), 1),
        "avg_turnover": round(float(np.mean([r["turnover"] for r in records])), 4),
        "benchmark_total_return": round(float(bench_total), 4),
        "benchmark_annualized_return": round(float(bench_ann), 4),
    }

    # Build curve output
    curve_data = []
    for i, rec in enumerate(records):
        curve_data.append({
            "date": rec["date"],
            "strategy": round(float(strategy_cumulative.iloc[i]) - 1, 6),
            "benchmark": round(float(benchmark_cumulative.iloc[i]) - 1, 6),
            "daily_return": round(float(rec["daily_return"]), 6),
            "holdings_count": rec["holdings_count"],
            "turnover": rec["turnover"],
        })

    # Concept attribution
    concept_attr = []
    for concept, rets in concept_returns.items():
        rets_arr = np.array(rets)
        concept_attr.append({
            "concept": concept,
            "total_return": round(float(rets_arr.sum()), 4),
            "avg_daily_return": round(float(rets_arr.mean()), 6),
            "days_active": len(rets),
            "hit_rate": round(float((rets_arr > 0).sum() / max(len(rets_arr), 1)), 4),
        })

    # Sort by total return descending
    concept_attr.sort(key=lambda x: x["total_return"], reverse=True)

    logger.info(f"Backtest complete: {total_days} days, total return={total_return:.2%}, sharpe={sharpe:.3f}")

    return {
        "curve": curve_data,
        "metrics": metrics,
        "holdings": daily_holdings_log,
        "concept_attribution": concept_attr,
    }


if __name__ == "__main__":
    result = run_signal_backtest()
    print(f"Metrics: {json.dumps(result['metrics'], indent=2)}")
    print(f"Curve points: {len(result['curve'])}")
    print(f"Top 5 concepts:")
    for c in result["concept_attribution"][:5]:
        print(f"  {c['concept']}: {c['total_return']:.2%} ({c['days_active']} days, hit={c['hit_rate']:.0%})")
