import os
import qlib
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, PortAnaRecord, SigAnaRecord
import datetime
from loguru import logger
from core.config import DATA_DIR, WORKSPACE_DIR
from modules.backtest.pool_generator import get_topic_universe

# Fix for mlflow filestore error
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

def run_intelligent_backtest():
    provider_uri = str(WORKSPACE_DIR / "data" / "cn_stock" / "standard" / "qlib_data")
    qlib.init(provider_uri=provider_uri, region="cn")
    
    # 1. Get Static Topic Universe (all dumped CSVs)
    csv_dir = WORKSPACE_DIR / "data" / "cn_stock" / "backtest_ohlcv"
    symbols = [f.replace('.csv', '') for f in os.listdir(csv_dir) if f.endswith('.csv') and not f.startswith('_')]
    topic_universe = sorted(symbols)
    
    min_date = "2024-03-19"
    max_date = "2026-06-23"
    
    logger.info(f"Targeting ML Universe: {len(topic_universe)} symbols from {min_date} to {max_date}")
    
    # Alpha158 Dataset Config
    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158",
                "module_path": "qlib.contrib.data.handler",
                "kwargs": {
                    "start_time": min_date,
                    "end_time": max_date,
                    "fit_start_time": min_date,
                    "fit_end_time": "2025-06-30",
                    "instruments": topic_universe,
                    "infer_processors": [
                        {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
                        {"class": "Fillna", "kwargs": {"fields_group": "feature"}}
                    ],
                    "learn_processors": [
                        {"class": "DropnaLabel"},
                        {"class": "CSZScoreNorm", "kwargs": {"fields_group": "label"}}
                    ],
                }
            },
            "segments": {
                "train": ("2024-03-19", "2025-06-30"),
                "valid": ("2025-07-01", "2025-10-27"),
                "test": ("2025-10-28", "2026-06-23"),
            },
        },
    }

    # LightGBM Config
    model_config = {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt",
        "kwargs": {
            "loss": "mse",
            "colsample_bytree": 0.8879,
            "learning_rate": 0.0421,
            "subsample": 0.8789,
            "lambda_l1": 205.69,
            "lambda_l2": 580.97,
            "max_depth": 8,
            "num_leaves": 210,
            "num_threads": 20,
        },
    }
    
    # Execute Workflow
    with R.start(experiment_name="Topic_Alpha158_LGBM"):
        logger.info("Initializing dataset (Alpha158 extraction)...")
        dataset = init_instance_by_config(dataset_config)
        
        logger.info("Initializing and training LightGBM model...")
        model = init_instance_by_config(model_config)
        model.fit(dataset)
        R.save_objects(trained_model=model)
        
        logger.info("Running signal predictions for Test segment...")
        rec = SignalRecord(model, dataset, recorder=R.get_recorder())
        rec.generate()
        
        # Verify pred.pkl exists
        pred_df = R.get_recorder().load_object("pred.pkl")
        logger.info(f"Predictions generated successfully. Shape: {pred_df.shape}")
        
        # Save explicit copy for our ML backtester to find easily without querying MLflow
        pred_path = WORKSPACE_DIR / "data" / "cn_stock" / "ml_predictions.pkl"
        pred_df.to_pickle(pred_path)
        logger.info(f"Predictions saved directly to: {pred_path}")
        
        logger.info("ML Training & Prediction completed!")

if __name__ == "__main__":
    run_intelligent_backtest()
