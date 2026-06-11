import sys
import subprocess
import json
import pandas as pd
from loguru import logger
from fastapi import HTTPException
from api.core_config import WORKSPACE_DIR, DATA_DIR, resolver, PROJECT_DIR

# Setup Qlib lazily
_qlib_initialized = False

def get_backtest_metrics_and_curve():
    """Returns the latest backtest metrics and curve."""
    global _qlib_initialized
    import qlib
    from qlib.workflow import R
    
    if not _qlib_initialized:
        provider_uri = str(WORKSPACE_DIR / "data/cn_stock/standard/qlib_data")
        qlib.init(provider_uri=provider_uri, region="cn")
        _qlib_initialized = True
        
    exp = R.get_exp(experiment_name="custom_workflow")
    recorders = exp.list_recorders()
    
    # iterate from newest to oldest
    report_normal = None
    port_analysis = None
    
    # Safely iterate through recorders
    rec_ids = sorted(recorders.keys(), reverse=True)
    for rec_id in rec_ids:
        rec = recorders[rec_id]
        try:
            report_normal = rec.load_object("portfolio_analysis/report_normal_1day.pkl")
            port_analysis = rec.load_object("portfolio_analysis/port_analysis_1day.pkl")
            if report_normal is not None and port_analysis is not None:
                break
        except Exception:
            continue
            
    if report_normal is None or port_analysis is None:
        return {
            "metrics": {"annualized_return": 0.0, "information_ratio": 0.0, "max_drawdown": 0.0},
            "curve": []
        }
        
    # Parse analysis
    def safe_float(val, default=0.0):
        if val is None or pd.isna(val):
            return default
        try:
            res = float(val)
            if pd.isna(res):
                return default
            return res
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
        
    # Parse cumulative return curve
    curve_data = []
    if not report_normal.empty:
        cum_strategy = (1 + report_normal["return"] - report_normal["cost"]).cumprod() - 1
        cum_bench = (1 + report_normal["bench"]).cumprod() - 1
        
        # Load macro signals
        macro_file = DATA_DIR / "signals" / "market_sentiment.csv"
        macro_df = pd.DataFrame()
        if macro_file.exists():
            try:
                macro_df = pd.read_csv(macro_file)
                macro_df['date'] = pd.to_datetime(macro_df['date'])
                macro_df.set_index('date', inplace=True)
                macro_df = macro_df.ffill()
            except Exception as e:
                logger.error(f"Error reading macro signals: {e}")
        
        for date, row in report_normal.iterrows():
            d_str = date.strftime("%Y-%m-%d")
            
            # Default sentiment
            sentiment = 50.0
            pe_median = 0.0
            uplimit_num = 0.0
            is_bull = 0.0
            
            if not macro_df.empty:
                try:
                    if date in macro_df.index:
                        s_row = macro_df.loc[date]
                        if isinstance(s_row, pd.DataFrame):
                            s_row = s_row.iloc[0]
                        sentiment = float(s_row.get("sentiment_score", 50.0))
                        pe_median = float(s_row.get("pe_median", 0.0))
                        uplimit_num = float(s_row.get("uplimit_num", 0.0))
                        tiandi = s_row.get("tiandi_num")
                        
                        u_val = float(uplimit_num) if uplimit_num is not None and not pd.isna(uplimit_num) else float('nan')
                        t_val = float(tiandi) if tiandi is not None and not pd.isna(tiandi) else float('nan')
                        
                        if pd.isna(u_val) or pd.isna(t_val):
                            is_bull = 1.0 if sentiment >= 55.0 else 0.0
                        else:
                            is_bull = 1.0 if (sentiment >= 55.0 and u_val >= 40 and t_val <= 2) else 0.0
                except Exception:
                    pass

            curve_data.append({
                "date": d_str,
                "strategy": safe_float(cum_strategy.loc[date]),
                "benchmark": safe_float(cum_bench.loc[date]),
                "sentiment_score": safe_float(sentiment, 50.0),
                "pe_median": safe_float(pe_median, 0.0),
                "uplimit_num": safe_float(uplimit_num, 0.0),
                "timing_signal": safe_float(is_bull, 0.0)
            })
            
    return {
        "metrics": metrics,
        "curve": curve_data
    }

def run_single_stock_backtest(symbol: str, start_date: str, end_date: str):
    # First ensure the stock data is resolved
    resolver.resolve_single_stock(symbol)
    
    # Run the single stock backtest script
    cmd = [
        sys.executable,
        str(PROJECT_DIR / "single_stock_backtest.py"),
        "--symbol", symbol,
        "--start", start_date,
        "--end", end_date
    ]
    
    logger.info(f"Running single stock backtest: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Parse the JSON from the last line of stdout
    lines = result.stdout.strip().split('\n')
    json_line = lines[-1] if lines else "{}"
    
    try:
        parsed = json.loads(json_line)
        if parsed.get("status") == "error":
            raise ValueError(parsed.get("message", "Backtest failed"))
        return parsed
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON output: {result.stdout}")
        logger.error(f"Stderr: {result.stderr}")
        raise ValueError("Backend failed to return valid JSON results.")
