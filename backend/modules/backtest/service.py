import sys
import subprocess
import json
import pandas as pd
from loguru import logger
from core.config import WORKSPACE_DIR, resolver, PROJECT_DIR


def _cache_name(enable_ml_filter, model_version, top_k, enable_market_timing):
    """生成缓存文件名，区分择时/无择时"""
    ml_prefix = "_ml" if enable_ml_filter else "_signal"
    timing_suffix = "_timed" if enable_market_timing else "_raw"
    return f"{ml_prefix}_{model_version}_top{top_k}{timing_suffix}_backtest_cache.json"


def get_signal_backtest_results(enable_ml_filter: bool = False, model_version: str = "v1_default", top_k: int = 10, enable_market_timing: bool = True):
    """Returns cached signal backtest results, or runs the backtest if no cache exists."""
    cache_name = _cache_name(enable_ml_filter, model_version, top_k, enable_market_timing)
    cache_path = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv" / cache_name

    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load backtest cache: {e}")

    # No cache — auto-run the backtest
    logger.info(f"No cache found at {cache_name}, auto-running backtest...")
    return run_signal_backtest_service(enable_ml_filter=enable_ml_filter, model_version=model_version, top_k=top_k, enable_market_timing=enable_market_timing)


def run_signal_backtest_service(enable_ml_filter: bool = False, model_version: str = "v1_default", top_k: int = 10, enable_market_timing: bool = True):
    """
    Runs the signal backtest and caches results.
    This is the main entry point called from the router.
    """
    from modules.backtest.signal_backtest import run_signal_backtest, BacktestConfig

    exit_timing = "close" if model_version == "v3_open2close" else "open"
    logger.info(f"Running AI signal backtest... (ML Filter: {enable_ml_filter}, Model: {model_version}, Top K: {top_k}, Exit: {exit_timing}, Timing: {enable_market_timing})")
    config = BacktestConfig(enable_ml_filter=enable_ml_filter, model_version=model_version, top_k=top_k, exit_timing=exit_timing, enable_market_timing=enable_market_timing)
    result = run_signal_backtest(config)

    # Cache to disk (separate caches for timing on/off)
    cache_name = _cache_name(enable_ml_filter, model_version, top_k, enable_market_timing)
    cache_path = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv" / cache_name
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

    logger.info("Signal backtest completed and cached.")
    return result

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
            # Parse filename: _ml_{model}_top{k}{_timed|_raw}_backtest_cache.json
            core = filename.replace("_ml_", "").replace("_backtest_cache.json", "")
            parts = core.split("_top")
            if len(parts) != 2:
                continue

            model_version = parts[0]
            rest = parts[1]  # e.g. "4_timed" or "4_raw" or "4" (legacy)
            if "_timed" in rest:
                top_k = int(rest.replace("_timed", ""))
                timed_label = "择时"
            elif "_raw" in rest:
                top_k = int(rest.replace("_raw", ""))
                timed_label = "无择时"
            else:
                top_k = int(rest)
                timed_label = ""
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            metrics = data.get("metrics")
            if not metrics:
                continue
                
            leaderboard.append({
                "model_version": model_version,
                "top_k": top_k,
                "enable_market_timing": timed_label == "择时",
                "timing_label": timed_label,
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
