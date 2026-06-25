import sys
import os
import glob
import subprocess
import json
import pandas as pd
from loguru import logger
from fastapi import HTTPException
from core.config import WORKSPACE_DIR, DATA_DIR, resolver, PROJECT_DIR, config
import concurrent.futures
from modules.market.adapters.popularity import EastmoneyPopularityAdapter, TonghuashunPopularityAdapter


def get_signal_backtest_results(enable_ml_filter: bool = False, model_version: str = "v1_default", top_k: int = 10):
    """Returns cached signal backtest results, or runs the backtest if no cache exists."""
    cache_name = f"_ml_{model_version}_top{top_k}_backtest_cache.json" if enable_ml_filter else f"_signal_top{top_k}_backtest_cache.json"
    cache_path = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv" / cache_name

    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load backtest cache: {e}")

    # No cache — auto-run the backtest
    logger.info(f"No cache found at {cache_name}, auto-running backtest...")
    return run_signal_backtest_service(enable_ml_filter=enable_ml_filter, model_version=model_version, top_k=top_k)


def run_signal_backtest_service(enable_ml_filter: bool = False, model_version: str = "v1_default", top_k: int = 10):
    """
    Runs the signal backtest and caches results.
    This is the main entry point called from the router.
    """
    from modules.backtest.signal_backtest import run_signal_backtest, BacktestConfig

    exit_timing = "close" if model_version == "v3_open2close" else "open"
    logger.info(f"Running AI signal backtest... (ML Filter: {enable_ml_filter}, Model: {model_version}, Top K: {top_k}, Exit: {exit_timing})")
    config = BacktestConfig(enable_ml_filter=enable_ml_filter, model_version=model_version, top_k=top_k, exit_timing=exit_timing)
    result = run_signal_backtest(config)

    # Cache to disk (separate caches)
    cache_name = f"_ml_{model_version}_top{top_k}_backtest_cache.json" if enable_ml_filter else f"_signal_top{top_k}_backtest_cache.json"
    cache_path = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv" / cache_name
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

    logger.info("Signal backtest completed and cached.")
    return result

def get_todays_picks_service(model_version="v3_open2close", top_k=10):
    """Fetches the latest AI pre-market report and scores it with ML."""
    from modules.backtest.signal_backtest import _parse_reports
    
    daily_pools = _parse_reports()
    if not daily_pools:
        return {"status": "error", "message": "No historical pool data found."}
        
    latest_date = max(daily_pools.keys())
    
    stock_pools_dir = WORKSPACE_DIR / "data" / "cn_stock" / "stock_pools"
    override_file = stock_pools_dir / f"stock_pool_{latest_date}.json"
    
    candidates = {}
    
    if override_file.exists():
        with open(override_file, 'r', encoding='utf-8') as f:
            pool_data = json.load(f)
        stocks = pool_data.get('stocks', [])
        
        def to_qlib_symbol(code):
            code = str(code)
            if code.startswith('6'): return 'SH' + code
            elif code.startswith('0') or code.startswith('3'): return 'SZ' + code
            else: return 'BJ' + code
            
        candidates = {to_qlib_symbol(s['code']): s for s in stocks}
    else:
        pool_data = daily_pools[latest_date]
        for sym, info in pool_data.items():
            candidates[sym] = info
    
    # Load ML predictions
    pred_path = WORKSPACE_DIR / "data" / "cn_stock" / "predictions" / f"{model_version}.pkl"
    
    if not pred_path.exists():
        return {"status": "error", "message": f"ML predictions file not found at {pred_path}. Run backtest first."}
        
    preds = pd.read_pickle(pred_path)
    if isinstance(preds, pd.DataFrame) and preds.shape[1] > 0:
        preds = preds.iloc[:, 0]
        
    # Upper-case the symbols!
    if isinstance(preds.index, pd.MultiIndex):
        preds.index = preds.index.set_levels(preds.index.levels[1].str.upper(), level=1)
        
    latest_pred_date = preds.index.get_level_values(0).max()
    day_preds = preds.loc[latest_pred_date]
    valid_preds = day_preds.reindex(list(candidates.keys())).dropna()
    
    # SORT and TRUNCATE: Only check popularity/risk for the Top 25 ML scores to avoid crashing the server
    valid_preds = valid_preds.sort_values(ascending=False).head(25)
    
    # 1. Fetch Batch Data from THS
    ths_pop = TonghuashunPopularityAdapter(config)
    ths_batch_data = ths_pop.get_batch_data(list(valid_preds.index))
    
    # 2. Fetch EM Popularity concurrently (Top 20 candidates is sufficient)
    em_pop = EastmoneyPopularityAdapter(config)
    em_ranks = {}
    
    def fetch_em(sym):
        return sym, em_pop.get_realtime_rank(sym)
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_em, sym): sym for sym in valid_preds.index}
        for future in concurrent.futures.as_completed(futures):
            sym, r = future.result()
            em_ranks[sym] = r

    # 3. Map scores back and Adjust (Hybrid Composite Scoring)
    results = []
    for sym, score in valid_preds.items():
        s_info = candidates[sym]
        base_score = float(score)
        
        # Get meta
        raw_code = ''.join([c for c in sym if c.isdigit()])
        ths_meta = ths_batch_data.get(raw_code, {})
        ths_rank = ths_meta.get("rank", 99999)
        is_risky = ths_meta.get("is_risky", False)
        em_rank = em_ranks.get(sym, 99999)
        
        # Base multiplier
        multiplier = 1.0
        
        # LLM Logic Boost
        if s_info.get("weight_type") == "core":
            multiplier += 0.5
        if s_info.get("is_new"):
            multiplier += 0.2
            
        # Popularity Boost (Top 200 Cross-validation)
        pop_boost = 0.0
        pop_status = "一般"
        if em_rank <= 200 and ths_rank <= 200:
            pop_boost += 1.0  # Massive boost
            pop_status = "双百强"
        elif em_rank <= 200 or ths_rank <= 200:
            pop_boost += 0.5  # Moderate boost
            pop_status = "人气股"
            
        # Adjust score
        adjusted_score = base_score * multiplier + pop_boost
        
        # Risk Veto
        if is_risky:
            adjusted_score = -9999.0  # Veto
            pop_status = "风控剔除"
            
        results.append({
            "symbol": sym,
            "name": s_info.get("name", ths_meta.get("name", "")),
            "theme": s_info.get("theme", s_info.get("concept", "")),
            "score": round(adjusted_score, 4),
            "original_score": round(base_score, 4),
            "em_rank": em_rank if em_rank != 99999 else "无",
            "ths_rank": ths_rank if ths_rank != 99999 else "无",
            "popularity": pop_status
        })
        
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        "status": "success",
        "date": latest_date,
        "prediction_date": latest_pred_date.strftime("%Y-%m-%d") if hasattr(latest_pred_date, 'strftime') else str(latest_pred_date),
        "data": results,
        "top_picks": [r for r in results[:top_k] if r["score"] > -9900], # Don't return vetoed
        "other_candidates": results[top_k:]
    }


def run_data_download_service():
    """Downloads OHLCV data for all stocks in the AI report universe."""
    from modules.backtest.pool_generator import get_topic_universe
    from modules.backtest.data_downloader import download_all

    universe, min_date, max_date = get_topic_universe()
    if not universe:
        raise ValueError("No symbols found in topic universe")

    success, fail, failed_syms = download_all(universe, min_date, max_date)

    return {
        "status": "success",
        "total": len(universe),
        "downloaded": success,
        "failed": fail,
        "failed_symbols": failed_syms[:20],  # Limit response size
    }


# --- Legacy Qlib-based backtest (kept for backward compatibility) ---

_qlib_initialized = False


def get_backtest_metrics_and_curve():
    """Returns the latest Qlib-based backtest metrics and curve (legacy)."""
    global _qlib_initialized
    import qlib
    from qlib.workflow import R

    if not _qlib_initialized:
        provider_uri = str(WORKSPACE_DIR / "data/cn_stock/standard/qlib_data")
        qlib.init(provider_uri=provider_uri, region="cn")
        _qlib_initialized = True

    exp = R.get_exp(experiment_name="Topic_Alpha158_LGBM_NoTiming")
    recorders = exp.list_recorders()

    report_normal = None
    port_analysis = None
    positions_df = None

    rec_ids = sorted(recorders.keys(), reverse=True)
    for rec_id in rec_ids:
        rec = recorders[rec_id]
        try:
            report_normal = rec.load_object("portfolio_analysis/report_normal_1day.pkl")
            port_analysis = rec.load_object("portfolio_analysis/port_analysis_1day.pkl")
            try:
                positions_df = rec.load_object("portfolio_analysis/positions_normal_1day.pkl")
            except Exception:
                pass
            if report_normal is not None and port_analysis is not None:
                break
        except Exception:
            continue

    if report_normal is None or port_analysis is None:
        return {
            "metrics": {"annualized_return": 0.0, "information_ratio": 0.0, "max_drawdown": 0.0},
            "curve": [],
            "holdings": []
        }

    def safe_float(val, default=0.0):
        if val is None or pd.isna(val):
            return default
        try:
            res = float(val)
            return default if pd.isna(res) else res
        except ValueError:
            return default

    try:
        excess_cost = port_analysis.loc["excess_return_with_cost", "risk"]
        metrics = {
            "annualized_return": safe_float(excess_cost.get("annualized_return", 0)),
            "information_ratio": safe_float(excess_cost.get("information_ratio", 0)),
            "max_drawdown": safe_float(excess_cost.get("max_drawdown", 0))
        }
    except Exception:
        metrics = {"annualized_return": 0.0, "information_ratio": 0.0, "max_drawdown": 0.0}

    curve_data = []
    if not report_normal.empty:
        cum_strategy = (1 + report_normal["return"] - report_normal["cost"]).cumprod() - 1
        cum_bench = (1 + report_normal["bench"]).cumprod() - 1

        for date, row in report_normal.iterrows():
            curve_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "strategy": safe_float(cum_strategy.loc[date]),
                "benchmark": safe_float(cum_bench.loc[date]),
            })

    holdings_data = []
    if positions_df is not None:
        try:
            for date_idx, pos in positions_df.items():
                d_str = date_idx.strftime("%Y-%m-%d") if hasattr(date_idx, 'strftime') else str(date_idx)
                symbols = []
                if isinstance(pos, dict):
                    symbols = [k for k in pos.keys() if not str(k).startswith('<') and str(k).lower() != 'cash']
                elif hasattr(pos, 'index'):
                    symbols = [k for k in pos.index if not str(k).startswith('<') and str(k).lower() != 'cash']
                if symbols:
                    holdings_data.append({"date": d_str, "symbols": symbols})
        except Exception as e:
            logger.error(f"Error parsing holdings: {e}")

    return {
        "metrics": metrics,
        "curve": curve_data,
        "holdings": holdings_data
    }


def run_single_stock_backtest(symbol: str, start_date: str, end_date: str):
    resolver.resolve_single_stock(symbol)
    cmd = [
        sys.executable,
        str(PROJECT_DIR / "single_stock_backtest.py"),
        "--symbol", symbol,
        "--start", start_date,
        "--end", end_date
    ]
    logger.info(f"Running single stock backtest: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')
    json_line = lines[-1] if lines else "{}"
    try:
        parsed = json.loads(json_line)
        if parsed.get("status") == "error":
            raise ValueError(parsed.get("message", "Backtest failed"))
        return parsed
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON output: {result.stdout}")
        raise ValueError("Backend failed to return valid JSON results.")


def run_intelligent_backtest_service():
    """Runs the Qlib-based intelligent backtest workflow (legacy)."""
    cmd = [sys.executable, "-m", "modules.backtest.topic_workflow"]
    logger.info(f"Running intelligent backtest workflow: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR), capture_output=True, text=True)
    if result.returncode != 0:
        # Extract only last 5 lines of stderr for cleaner error messages
        err_lines = result.stderr.strip().split('\n')
        err_msg = '\n'.join(err_lines[-5:])
        logger.error(f"Intelligent backtest failed: {err_msg}")
        raise ValueError(f"Intelligent backtest failed: {err_msg}")
    return {"status": "success", "message": "Intelligent backtest completed successfully."}

def get_live_quotes_service(symbols: list[str]):
    """Fetches real-time intraday quotes for a list of Qlib symbols from Tencent Finance."""
    import requests
    
    if not symbols:
        return {"status": "success", "data": {}}
        
    def to_tencent_code(sym):
        # Qlib: SH600519 -> Tencent: sh600519
        return sym.lower()
        
    tencent_symbols = [to_tencent_code(s) for s in symbols]
    url = f"http://qt.gtimg.cn/q={','.join(tencent_symbols)}"
    
    try:
        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
        text = resp.text
        
        results = {}
        for line in text.strip().split('\n'):
            if not line or '=' not in line:
                continue
            parts = line.split('=')
            if len(parts) != 2:
                continue
            
            var_name = parts[0]
            data_str = parts[1].strip('";')
            fields = data_str.split('~')
            
            if len(fields) > 32:
                code = var_name.split('_')[-1].upper() 
                name = fields[1]
                try:
                    current_price = float(fields[3])
                    yesterday_close = float(fields[4])
                    open_price = float(fields[5])
                    pct_change = float(fields[32])
                except ValueError:
                    continue
                    
                results[code] = {
                    "price": current_price,
                    "yesterday_close": yesterday_close,
                    "open_price": open_price,
                    "pct_change": pct_change,
                    "name": name
                }
                
                
        return {"status": "success", "data": results}
    except Exception as e:
        logger.error(f"Error fetching live quotes: {e}")
        return {"status": "error", "message": str(e)}

def get_leaderboard_service():
    """Dynamically scan all backtest cache files and compile a leaderboard."""
    import glob
    import os
    
    leaderboard = []
    
    # Path pattern for backtest cache files
    cache_dir = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv"
    search_pattern = str(cache_dir / "_ml_*_backtest_cache.json")
    
    for file_path in glob.glob(search_pattern):
        try:
            filename = os.path.basename(file_path)
            # Parse filename format: _ml_{model_version}_top{top_k}_backtest_cache.json
            parts = filename.replace("_ml_", "").replace("_backtest_cache.json", "").split("_top")
            if len(parts) != 2:
                continue
                
            model_version = parts[0]
            top_k = int(parts[1])
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            metrics = data.get("metrics")
            if not metrics:
                continue
                
            leaderboard.append({
                "model_version": model_version,
                "top_k": top_k,
                "annual_return": f"{metrics.get('annualized_return', 0) * 100:.2f}%",
                "max_drawdown": f"{metrics.get('max_drawdown', 0) * 100:.2f}%",
                "sharpe_ratio": f"{metrics.get('sharpe_ratio', 0):.3f}",
                "win_rate": f"{metrics.get('hit_rate', 0) * 100:.2f}%"
            })
        except Exception as e:
            logger.error(f"Error parsing cache file {file_path} for leaderboard: {e}")
            continue
            
    # Sort the leaderboard by Annual Return descending
    # Need to convert string percentage like '441.84%' to float
    def parse_return(x):
        try:
            return float(x.replace("%", ""))
        except:
            return 0.0
            
    leaderboard.sort(key=lambda x: parse_return(x["annual_return"]), reverse=True)
    
    # Assign Rank
    for i, item in enumerate(leaderboard):
        item["rank"] = i + 1
        
    return {"status": "success", "data": leaderboard}
