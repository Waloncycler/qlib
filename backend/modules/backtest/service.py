import sys
import os
import glob
import subprocess
import json
import pandas as pd
from loguru import logger
from fastapi import HTTPException
from core.config import WORKSPACE_DIR, DATA_DIR, resolver, PROJECT_DIR


def get_signal_backtest_results(enable_ml_filter: bool = False):
    """Returns cached signal backtest results, or runs the backtest if no cache exists."""
    cache_name = "_ml_backtest_cache.json" if enable_ml_filter else "_signal_backtest_cache.json"
    cache_path = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv" / cache_name

    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load backtest cache: {e}")

    # No cache — return empty (user needs to trigger backtest first)
    return {
        "metrics": {},
        "curve": [],
        "holdings": [],
        "concept_attribution": [],
    }


def run_signal_backtest_service(enable_ml_filter: bool = False):
    """
    Runs the signal backtest and caches results.
    This is the main entry point called from the router.
    """
    from modules.backtest.signal_backtest import run_signal_backtest, BacktestConfig

    logger.info(f"Running AI signal backtest... (ML Filter: {enable_ml_filter})")
    config = BacktestConfig(enable_ml_filter=enable_ml_filter)
    result = run_signal_backtest(config)

    # Cache to disk (separate caches)
    cache_name = "_ml_backtest_cache.json" if enable_ml_filter else "_signal_backtest_cache.json"
    cache_path = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv" / cache_name
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)

    logger.info("Signal backtest completed and cached.")
    return result

def get_todays_picks_service():
    """Fetches the latest AI pre-market report and scores it with ML."""
    # 1. Find latest OpenClaw stock pool
    openclaw_dir = WORKSPACE_DIR.parent / "YMOS" / "OpenClaw" / "3_Quant" / "Stock_Pools"
    if not openclaw_dir.exists():
        return {"status": "error", "message": f"OpenClaw directory not found at {openclaw_dir}"}
        
    pool_files = glob.glob(str(openclaw_dir / "stock_pool_*.json"))
    if not pool_files:
        return {"status": "error", "message": "No stock_pool JSON files found in OpenClaw."}
        
    latest_pool_file = max(pool_files, key=os.path.getmtime)
    
    with open(latest_pool_file, 'r', encoding='utf-8') as f:
        pool_data = json.load(f)
        
    pool = pool_data.get('stocks', [])
    date = pool_data.get('date', '')
    
    # Construct Qlib symbols
    def to_qlib_symbol(code):
        if code.startswith('6'):
            return 'SH' + code
        elif code.startswith('0') or code.startswith('3'):
            return 'SZ' + code
        else:
            return 'BJ' + code
            
    candidates = {to_qlib_symbol(s['code']): s for s in pool}
    
    # 2. Load ML predictions
    pred_path = WORKSPACE_DIR / "data" / "cn_stock" / "ml_predictions.pkl"
    if not pred_path.exists():
        return {"status": "error", "message": "ML predictions file not found. Run backtest first."}
        
    preds = pd.read_pickle(pred_path)
    if isinstance(preds, pd.DataFrame) and preds.shape[1] > 0:
        preds = preds.iloc[:, 0]
        
    latest_date = preds.index.get_level_values(0).max()
    day_preds = preds.loc[latest_date]
    valid_preds = day_preds.reindex(list(candidates.keys())).dropna()
    
    # Map scores back
    results = []
    for sym, score in valid_preds.items():
        s_info = candidates[sym]
        results.append({
            'symbol': sym,
            'name': s_info['name'],
            'theme': s_info.get('theme', ''),
            'score': round(float(score), 4)
        })
        
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        "status": "success",
        "date": date,
        "prediction_date": latest_date.strftime("%Y-%m-%d"),
        "top_picks": results[:10],
        "other_candidates": results[10:]
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
