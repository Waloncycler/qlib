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
from modules.backtest.data_downloader import load_ohlcv, load_benchmark, OHLCV_DIR


@dataclass
class BacktestConfig:
    """Configuration for signal backtest."""
    initial_capital: float = 10_000_000.0
    buy_cost: float = 0.0013       # 0.03% commission + 0.1% slippage
    sell_cost: float = 0.0018      # 0.03% commission + 0.05% stamp duty + 0.1% slippage
    core_weight_multiplier: float = 2.0
    new_concept_multiplier: float = 1.5
    enable_ml_filter: bool = False
    top_k: int = 10


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

    # --- Native Qlib Flow (Faction 1) ---
    # We rely entirely on zizizaizai_reports.json. No external overrides.
    return daily_pools


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
        pred_path = WORKSPACE_DIR / "data" / "cn_stock" / "ml_predictions.pkl"
        if pred_path.exists():
            logger.info("Loading ML predictions for filtering...")
            ml_preds = pd.read_pickle(pred_path)
            # Ensure it's a series or dataframe. Qlib pred.pkl is usually a pd.Series or pd.DataFrame with multi-index (datetime, instrument)
            if isinstance(ml_preds, pd.DataFrame) and ml_preds.shape[1] == 1:
                ml_preds = ml_preds.iloc[:, 0]
        else:
            logger.warning(f"ML filter enabled but {pred_path} not found. Skipping ML filter.")
            config.enable_ml_filter = False

    # Load benchmark
    benchmark_df = load_benchmark()
    if not benchmark_df.empty:
        benchmark_df = benchmark_df.set_index("date").sort_index()

    # --- Core backtest loop ---
    capital = config.initial_capital
    current_holdings: Dict[str, float] = {}  # symbol -> weight
    current_shares: Dict[str, float] = {}    # symbol -> num_shares
    current_entry_prices: Dict[str, float] = {}  # symbol -> entry open price

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
                valid_dates = available_dates[available_dates <= date_ts]
                
                if not valid_dates.empty:
                    latest_ml_date = valid_dates.max()
                    day_preds = ml_preds.loc[latest_ml_date]
                    
                    # Filter to only stocks in today_pool
                    pool_syms = list(today_pool.keys())
                    valid_preds = day_preds.reindex(pool_syms).dropna()
                    
                    if not valid_preds.empty:
                        # Sort by score descending and take Top K
                        top_syms = valid_preds.sort_values(ascending=False).head(config.top_k).index.tolist()
                        # Truncate today_pool to only include the top syms
                        today_pool = {s: info for s, info in today_pool.items() if s in top_syms}
                    else:
                        today_pool = {}  # No ML scores available for today's pool
                else:
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
            
            holding_syms = []
            all_involved = set(current_shares.keys()).union(set(intended_exits))
            for sym in sorted(all_involved):
                info = today_pool.get(sym, {})
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
                "trades": [],
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

        # Re-normalize after filtering
        total_w = sum(tradeable_targets.values())
        if total_w > 0:
            tradeable_targets = {s: w / total_w for s, w in tradeable_targets.items()}

        # Identify entries and exits
        prev_symbols = set(current_holdings.keys())
        target_symbols = set(tradeable_targets.keys())
        new_entries = target_symbols - prev_symbols
        exits = prev_symbols - target_symbols
        holds = prev_symbols & target_symbols

        # --- Process exits: sell at today's open ---
        daily_trades = []
        exit_proceeds = 0.0
        exit_symbols = []
        for sym in exits:
            if sym in prices and date_ts in prices[sym].index:
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

        # Remove exited positions
        for sym in exits:
            current_holdings.pop(sym, None)
            current_shares.pop(sym, None)
            current_entry_prices.pop(sym, None)

        # --- Rebalance: We rebalance all holdings to target weights ---
        # First, calculate total portfolio value at today's OPEN
        portfolio_value_at_open = cash + exit_proceeds
        for sym in holds:
            if sym in prices and date_ts in prices[sym].index:
                portfolio_value_at_open += current_shares[sym] * prices[sym].loc[date_ts, "open"]
            else:
                portfolio_value_at_open += current_shares.get(sym, 0) * current_entry_prices.get(sym, 0)

        # Re-allocate all capital according to new target weights
        entry_symbols = []
        new_shares = {}
        new_entry_prices = {}
        new_cash = portfolio_value_at_open

        for sym, weight in tradeable_targets.items():
            if sym in prices and date_ts in prices[sym].index:
                buy_price = prices[sym].loc[date_ts, "open"]
                if buy_price > 0:
                    allocated = portfolio_value_at_open * weight
                    # If this is a hold, we are adjusting position (buy or sell diff). 
                    # For simplicity, we assume we sell everything and buy it back (rebalance),
                    # BUT we only charge cost on the NEW capital entering the position to avoid massive costs.
                    current_val = 0
                    if sym in holds:
                        current_val = current_shares[sym] * buy_price
                    diff = allocated - current_val
                    trade_action = ""
                    trade_fee = 0.0
                    trade_amount = abs(diff)
                    if diff > 0:
                        # Buying
                        trade_fee = diff * config.buy_cost
                        allocated -= trade_fee
                        trade_action = "buy"
                    elif diff < 0:
                        # Selling
                        trade_fee = abs(diff) * config.sell_cost
                        allocated += trade_fee
                        trade_action = "sell"

                    if sym in new_entries:
                        entry_symbols.append(sym)

                    shares = allocated / buy_price
                    new_shares[sym] = shares
                    new_entry_prices[sym] = buy_price
                    new_cash -= allocated
                    
                    if trade_amount > 100:  # Ignore tiny rounding rebalances
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
        current_holdings = tradeable_targets.copy()
        current_entry_prices.update(new_entry_prices)
        cash = max(0, new_cash)  # Avoid precision issues making cash slightly negative

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
        all_involved = set(current_shares.keys()).union(set(exits))
        for sym in sorted(all_involved):
            info = today_pool.get(sym, {})
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
                    
            holding_syms.append({
                "symbol": sym,
                "name": info.get("name", ""),
                "type": info.get("weight_type", ""),
                "concept": info.get("concept", ""),
                "score": score,
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
    max_drawdown = drawdown.min()

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
