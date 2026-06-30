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
from loguru import logger
from typing import Dict, List, Set, Optional, Any, cast

from core.config import WORKSPACE_DIR
from modules.backtest.data_downloader import load_benchmark

# Expose dataclasses and parser at module level for external imports
from modules.backtest.config import BacktestConfig, DailyRecord
from modules.backtest.helpers import (
    _parse_reports,
    _compute_target_weights,
    _filter_by_volume,
    _rank_select_by_factor,
    _load_selection_history,
    _compute_selection_boost,
    _load_all_prices,
)
from modules.backtest.metrics import calculate_backtest_metrics


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
        pred_path = WORKSPACE_DIR / "data" / "cn_stock" / "predictions" / f"{config.model_version}.pkl"
        if pred_path.exists():
            logger.info("Loading ML predictions for filtering...")
            ml_preds = pd.read_pickle(pred_path)
            # Ensure it's a series or dataframe
            if isinstance(ml_preds, pd.DataFrame) and ml_preds.shape[1] == 1:
                ml_preds = ml_preds.iloc[:, 0]
            
            # Convert instrument index to uppercase to match signal_backtest logic
            if isinstance(ml_preds.index, pd.MultiIndex):
                # The second level is usually 'instrument'
                new_idx = ml_preds.index.set_levels(ml_preds.index.levels[1].str.upper(), level=1)  # type: ignore
                ml_preds.index = new_idx
        else:
            logger.warning(f"ML filter enabled but {pred_path} not found. Skipping ML filter.")
            config.enable_ml_filter = False

    # Load crash filter predictions if enabled
    crash_preds = None
    if config.enable_crash_filter:
        crash_path = WORKSPACE_DIR / "data" / "cn_stock" / "predictions" / "crash_filter.pkl"
        if crash_path.exists():
            logger.info(f"Loading crash filter predictions (threshold={config.crash_threshold})...")
            crash_preds = pd.read_pickle(crash_path)
            if isinstance(crash_preds, pd.DataFrame) and crash_preds.shape[1] == 1:
                crash_preds = crash_preds.iloc[:, 0]
            if isinstance(crash_preds.index, pd.MultiIndex):
                new_idx = crash_preds.index.set_levels(crash_preds.index.levels[1].str.upper(), level=1)  # type: ignore
                crash_preds.index = new_idx
        else:
            logger.warning(f"Crash filter enabled but {crash_path} not found. Skipping crash filter.")
            config.enable_crash_filter = False

    # Load AI selection history for consecutive-selection boost
    selection_history = {}
    if config.enable_selection_boost:
        selection_history = _load_selection_history()
        if selection_history:
            logger.info(f"Loaded AI selection history: {len(selection_history)} days for selection boost")

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

    for day_idx, date_str in enumerate(sorted_dates):
        date_ts = pd.Timestamp(date_str)  # type: ignore
        today_pool = daily_pools[date_str]

        # ML Filter: Keep only Top K scored stocks in today's pool
        latest_ml_date = None
        if config.enable_ml_filter and ml_preds is not None:
            try:
                available_dates = ml_preds.index.get_level_values(0).unique()
                # STRICTLY LESS THAN date_ts to prevent look-ahead bias
                valid_dates = available_dates[available_dates < date_ts]
                
                if not valid_dates.empty:
                    latest_ml_date = valid_dates.max()
                    day_preds = ml_preds.loc[latest_ml_date]
                    
                    # Filter to only stocks in today_pool
                    pool_syms = list(today_pool.keys())
                    valid_preds = day_preds.reindex(pool_syms).dropna()
                    
                    if not valid_preds.empty:
                        # Apply Historical Proxy Multipliers (Hybrid Scoring for Backtest)
                        adjusted_preds = valid_preds.copy()
                        for sym in valid_preds.index:
                            info = today_pool.get(sym, {})
                            multiplier = 1.0
                            if info.get("weight_type") == "core":
                                multiplier += 0.5
                            if info.get("is_new"):
                                multiplier += 0.2
                            adjusted_preds[sym] = adjusted_preds[sym] * multiplier
                        
                        # AI 连续入选加分
                        if config.enable_selection_boost and selection_history:
                            boosts = _compute_selection_boost(
                                set(adjusted_preds.index), date_str,
                                selection_history,
                                boost_factor=config.selection_boost_factor,
                            )
                            if boosts:
                                for sym, boost in boosts.items():
                                    if sym in adjusted_preds.index:
                                        adjusted_preds[sym] = adjusted_preds[sym] * boost
                                logger.debug(f"Selection boost applied to {len(boosts)} stocks on {date_str}")
                        
                        # Crash Filter
                        if config.enable_crash_filter and crash_preds is not None:
                            try:
                                crash_avail = crash_preds.index.get_level_values(0).unique()
                                crash_valid_dates = crash_avail[crash_avail < date_ts]
                                if not crash_valid_dates.empty:
                                    latest_crash_date = crash_valid_dates.max()
                                    day_crash = crash_preds.loc[latest_crash_date]
                                    pool_crash = day_crash.reindex(adjusted_preds.index).fillna(0)
                                    vetoed = pool_crash[pool_crash > config.crash_threshold].index.tolist()
                                    if vetoed:
                                        adjusted_preds = adjusted_preds.drop(vetoed)
                                        logger.info(f"Crash filter vetoed {len(vetoed)} stocks on {date_str}: {vetoed}")
                            except Exception as e:
                                logger.warning(f"Crash filter error on {date_str}: {e}")

                        # Volume Filter
                        if config.enable_turnover_filter:
                            vol_filtered_pool = _filter_by_volume(
                                {s: today_pool.get(s, {}) for s in adjusted_preds.index},
                                prices, date_ts, config  # type: ignore
                            )
                            removed = set(adjusted_preds.index) - set(vol_filtered_pool.keys())
                            if removed:
                                adjusted_preds = adjusted_preds.drop(list(removed))

                        # Sort by adjusted score descending and take Top K
                        top_syms = adjusted_preds.sort_values(ascending=False).head(config.top_k).index.tolist()
                        
                        # --- OVERRIDE FOR THE FINAL DAY ---
                        if day_idx == len(sorted_dates) - 1:
                            logger.info(f"Checking override for final day: {date_str}, day_idx={day_idx}, len={len(sorted_dates)}")
                            try:
                                from modules.backtest.scoring import get_todays_picks_service
                                live_res = get_todays_picks_service(model_version=config.model_version, top_k=config.top_k)
                                logger.info(f"live_res: {str(live_res)[:500]}")
                                if live_res.get("status") == "success" and "top_picks" in live_res:
                                    live_syms = [p["symbol"] for p in live_res["top_picks"]]  # type: ignore
                                    if live_syms:
                                        top_syms = live_syms
                                        logger.info(f"Final day override: using {len(top_syms)} live picks for {date_str}: {top_syms}")
                                        
                                        # SAVE TO FILE SO IT IS NOT WIPED OUT TOMORROW
                                        try:
                                            fpath = WORKSPACE_DIR / "data" / "cn_stock" / "stock_pools" / f"stock_pool_{date_str}.json"
                                            
                                            # 安全检查
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
                                                            "code": p["symbol"].replace("SH", "").replace("SZ", "").replace("BJ", ""),  # type: ignore
                                                            "name": p["name"],  # type: ignore
                                                            "theme": p.get("popularity", "人气热点叠加")  # type: ignore
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
                        today_pool = {}
                else:
                    logger.warning(f"valid_dates is empty for {date_str}")
                    today_pool = {}
            except Exception as e:
                logger.error(f"Error applying ML filter on {date_str}: {e}")
                today_pool = {}

        # Determine target portfolio
        if config.enable_turnover_filter:
            today_pool = _filter_by_volume(today_pool, prices, date_ts, config)  # type: ignore

        if config.enable_factor_rank and not config.enable_ml_filter:
            today_pool = _rank_select_by_factor(today_pool, prices, date_ts, config)  # type: ignore

        target_weights = _compute_target_weights(today_pool, config)

        # Intended trades
        prev_symbols_intended = set(current_holdings.keys())
        target_symbols_intended = set(target_weights.keys())
        intended_entries = list(target_symbols_intended - prev_symbols_intended)
        intended_exits = list(prev_symbols_intended - target_symbols_intended)
        intended_holds = list(prev_symbols_intended & target_symbols_intended)

        # Check if market data for today exists
        required_syms = prev_symbols_intended.union(target_symbols_intended)
        missing_required = 0
        if len(required_syms) > 0:
            missing_required = sum(1 for sym in required_syms if sym not in prices or date_ts not in prices[sym].index)
            
        if len(required_syms) > 0 and missing_required >= (len(required_syms) * 0.5):
            logger.warning(f"Market data missing for {date_str}. Rolling forward previous NAV. Recording intended trades.")
            records.append({
                "date": date_str,
                "nav": round(float(prev_nav), 2),
                "daily_return": 0.0,
                "benchmark_return": 0.0,
                "holdings_count": len(current_shares),
                "turnover": 0.0,
            })
            
            synthetic_trades = []
            live_quotes: Dict[str, dict] = {}
            if date_str == pd.Timestamp.now().strftime("%Y-%m-%d"):
                try:
                    from modules.backtest.live_quotes import get_live_quotes_service
                    all_query_syms = list(set(current_shares.keys()).union(set(intended_entries)).union(set(intended_exits)))
                    res = get_live_quotes_service(all_query_syms)
                    if res and res.get("status") == "success":
                        data = res.get("data")
                        if isinstance(data, dict):
                            live_quotes = data
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
                current_holdings.pop(sym, None)
                current_shares.pop(sym, None)
                current_entry_prices.pop(sym, None)
                current_entry_dates.pop(sym, None)
                
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
                current_holdings[sym] = 1.0
                current_shares[sym] = 1.0
                current_entry_prices[sym] = live_quotes[sym]["open_price"] if sym in live_quotes else 0.0
                current_entry_dates[sym] = date_str
            
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
                    except Exception:
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
                        pct = float(cast(Any, prices[sym].loc[date_ts, "pct_change"]))
                        if not math.isnan(pct):
                            ret = round(pct / 100.0, 4)
                    except Exception:
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
            bench_close = float(cast(Any, benchmark_df.loc[date_ts, "close"]))
            bench_ma = float(cast(Any, benchmark_df.loc[date_ts, ma_col]))
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
            exits = set()
            for sym in prev_symbols:
                entry_date = current_entry_dates.get(sym, "")
                if entry_date != date_str:  # 不是今天买的
                    if sym not in target_symbols:
                        exits.add(sym)
            new_entries = target_symbols - prev_symbols
            holds = prev_symbols - exits
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
                    sell_price = float(cast(Any, prices[sym].loc[date_ts, "close"]))
                else:
                    sell_price = float(cast(Any, prices[sym].loc[date_ts, "open"]))
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

        # Remove exited positions from tracking
        close_exit_pending_proceeds = 0.0
        if config.exit_timing == "close":
            close_exit_pending_proceeds = exit_proceeds
            for sym in exits:
                current_holdings.pop(sym, None)
                current_shares.pop(sym, None)
                current_entry_prices.pop(sym, None)
                current_entry_dates.pop(sym, None)

            portfolio_value_at_open = cash
            for sym in holds:
                if sym in prices and date_ts in prices[sym].index:
                    portfolio_value_at_open += current_shares[sym] * float(cast(Any, prices[sym].loc[date_ts, "open"]))
                else:
                    portfolio_value_at_open += current_shares.get(sym, 0) * current_entry_prices.get(sym, 0)

            available_capital = min(cash, portfolio_value_at_open * 0.5 * intended_total_weight)

            entry_targets = {s: w for s, w in tradeable_targets.items() if s in new_entries}
            if entry_targets:
                entry_total = sum(entry_targets.values())
                for s in entry_targets:
                    entry_targets[s] = (entry_targets[s] / entry_total) * available_capital
        else:
            for sym in exits:
                current_holdings.pop(sym, None)
                current_shares.pop(sym, None)
                current_entry_prices.pop(sym, None)
            portfolio_value_at_open = cash + exit_proceeds
            for sym in holds:
                if sym in prices and date_ts in prices[sym].index:
                    portfolio_value_at_open += current_shares[sym] * float(cast(Any, prices[sym].loc[date_ts, "open"]))
                else:
                    portfolio_value_at_open += current_shares.get(sym, 0) * current_entry_prices.get(sym, 0)
            entry_targets = None

        # --- Rebalance: We rebalance all holdings to target weights ---
        entry_symbols = []
        new_shares = {}
        new_entry_prices = {}
        new_entry_dates = {}

        if config.exit_timing == "close" and entry_targets is not None:
            new_cash = cash
            for sym in list(current_shares.keys()):
                new_shares[sym] = current_shares[sym]
                new_entry_prices[sym] = current_entry_prices.get(sym, 0)
                new_entry_dates[sym] = current_entry_dates.get(sym, "")

            for sym, allocated_amount in entry_targets.items():
                if sym in prices and date_ts in prices[sym].index:
                    buy_price = float(cast(Any, prices[sym].loc[date_ts, "open"]))
                    if buy_price > 0:
                        trade_fee = allocated_amount * config.buy_cost
                        net_allocated = allocated_amount - trade_fee
                        shares = net_allocated / buy_price
                        new_shares[sym] = shares
                        new_entry_prices[sym] = buy_price
                        new_entry_dates[sym] = date_str
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
            new_cash = portfolio_value_at_open
            for sym, weight in tradeable_targets.items():
                if sym in prices and date_ts in prices[sym].index:
                    buy_price = float(cast(Any, prices[sym].loc[date_ts, "open"]))
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
        current_holdings = {sym: 1.0 for sym in new_shares}
        current_entry_prices.update(new_entry_prices)
        if config.exit_timing == "close":
            current_entry_dates = new_entry_dates
        cash = new_cash + close_exit_pending_proceeds

        # --- Calculate end-of-day NAV (mark to close) ---
        eod_nav = cash
        stock_returns_today: Dict[str, float] = {}
        for sym, shares in current_shares.items():
            if sym in prices and date_ts in prices[sym].index:
                close_price = float(cast(Any, prices[sym].loc[date_ts, "close"]))
                open_price = float(cast(Any, prices[sym].loc[date_ts, "open"]))
                eod_nav += shares * close_price
                if open_price > 0:
                    stock_returns_today[sym] = (close_price - open_price) / open_price
            else:
                eod_nav += shares * current_entry_prices.get(sym, 0)

        if eod_nav == 0 and len(current_shares) > 0:
            eod_nav = prev_nav

        daily_return = (eod_nav - prev_nav) / prev_nav if prev_nav > 0 else 0.0

        bench_return = 0.0
        if not benchmark_df.empty and date_ts in benchmark_df.index:
            bench_close = float(cast(Any, benchmark_df.loc[date_ts, "close"]))
            bench_open = float(cast(Any, benchmark_df.loc[date_ts, "open"]))
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
                        score = round(float(cast(Any, ml_preds.loc[latest_ml_date, sym])), 4)
                except Exception:
                    pass
            
            ret = None
            if sym in prices and date_ts in prices[sym].index:
                try:
                    open_p = float(cast(Any, prices[sym].loc[date_ts, "open"]))
                    close_p = float(cast(Any, prices[sym].loc[date_ts, "close"]))
                    pct = float(cast(Any, prices[sym].loc[date_ts, "pct_change"])) / 100.0
                    
                    if not math.isnan(pct):
                        if sym in entry_symbols:
                            if open_p > 0:
                                ret = round((close_p - open_p) / open_p, 4)
                        elif sym in exit_symbols:
                            if config.exit_timing == "close":
                                ret = round(pct, 4)
                            else:
                                pre_close = close_p / (1 + pct) if pct != -1.0 else open_p
                                if pre_close > 0:
                                    ret = round((open_p - pre_close) / pre_close, 4)
                        else:
                            ret = round(pct, 4)
                except Exception:
                    pass
                    
            weight = 0.0
            if eod_nav > 0 and sym in current_shares:
                if sym in prices and date_ts in prices[sym].index:
                    try:
                        c_p = float(cast(Any, prices[sym].loc[date_ts, "close"]))
                        weight = round((current_shares[sym] * c_p) / eod_nav, 4)
                    except Exception:
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
    metrics_res = calculate_backtest_metrics(records, concept_returns)
    logger.info(f"Backtest complete: {len(records)} days, total return={metrics_res['metrics']['total_return']:.2%}")

    return {
        "curve": metrics_res["curve"],
        "metrics": metrics_res["metrics"],
        "holdings": daily_holdings_log,
        "concept_attribution": metrics_res["concept_attribution"],
    }


if __name__ == "__main__":
    result = run_signal_backtest()
    print(f"Metrics: {json.dumps(result['metrics'], indent=2)}")
    print(f"Curve points: {len(result['curve'])}")
    print("Top 5 concepts:")
    for c in result["concept_attribution"][:5]:
        print(f"  {c['concept']}: {c['total_return']:.2%} ({c['days_active']} days, hit={c['hit_rate']:.0%})")
