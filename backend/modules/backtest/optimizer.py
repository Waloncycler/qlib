import json
import logging
import pandas as pd
from loguru import logger
from core.config import config, WORKSPACE_DIR
from modules.backtest.service import run_signal_backtest_service

def optimize_top_k(model_version: str = "v3_binary", k_values: list = None):
    """
    Grid search for the optimal Top K parameter by running historical backtests.
    """
    if k_values is None:
        k_values = list(range(2, 11))  # 2~10

    logger.info(f"Starting Top K Grid Search for model: {model_version} with Ks: {k_values}")
    
    results_summary = []
    
    for k in k_values:
        logger.info(f"===> Testing K = {k}")
        try:
            # Run the backtest for this K (force recalculation)
            res = run_signal_backtest_service(enable_ml_filter=True, model_version=model_version, top_k=k)
            
            if "metrics" in res:
                metrics = res.get("metrics", {})
                
                ann_ret = metrics.get("annualized_return", 0.0)
                mdd = metrics.get("max_drawdown", 0.0)
                sharpe = metrics.get("sharpe_ratio", 0.0)
                win = metrics.get("hit_rate", 0.0)
                
                results_summary.append({
                    "K": k,
                    "Annual Return": f"{ann_ret:.2%}",
                    "Max Drawdown": f"{mdd:.2%}",
                    "Sharpe Ratio": sharpe,
                    "Win Rate": f"{win:.2%}"
                })
                logger.info(f"Result for K={k}: Return={ann_ret:.2%}, Sharpe={sharpe}")
            else:
                logger.error(f"Failed backtest for K={k}: no metrics returned")
        except Exception as e:
            logger.error(f"Error during backtest for K={k}: {e}")
            
    # Save the summary to disk
    summary_df = pd.DataFrame(results_summary)
    save_path = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv" / f"{model_version}_optimize_k_results.csv"
    summary_df.to_csv(save_path, index=False)
    logger.info(f"Grid search complete. Results saved to {save_path}")
    
    return summary_df
