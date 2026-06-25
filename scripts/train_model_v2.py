import sys
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
from pathlib import Path
import pandas as pd
import qlib
from qlib.constant import REG_CN
from qlib.utils import init_instance_by_config
from qlib.workflow import R

def train_v2():
    # Add backend to path to import config
    backend_dir = Path(__file__).parent.parent / "backend"
    sys.path.append(str(backend_dir))
    from core.config import DATA_DIR, WORKSPACE_DIR

    # Initialize Qlib
    provider_uri = str(WORKSPACE_DIR / "data" / "cn_stock" / "standard" / "qlib_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)

    print("Qlib initialized. Starting V2 Open-to-Open Model Training...")

    # Use 'llm_pool' as the universe for training
    market = "llm_pool"
    train_start = "2024-01-01"
    train_end = "2025-06-30"
    valid_start = "2025-07-01"
    valid_end = "2025-12-31"
    test_start = "2026-01-01"
    test_end = "2026-12-31"

    data_handler_config = {
        "start_time": train_start,
        "end_time": test_end,
        "fit_start_time": train_start,
        "fit_end_time": train_end,
        "instruments": market,
        "infer_processors": [
            {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
            {"class": "Fillna", "kwargs": {"fields_group": "feature"}}
        ],
        "learn_processors": [
            {"class": "DropnaLabel"},
            {"class": "CSRankNorm", "kwargs": {"fields_group": "label"}}
        ],
        "label": ["Ref($open, -2) / Ref($open, -1) - 1"]
    }

    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "Alpha158Open2Open",
                "module_path": "__main__",
                "kwargs": {
                    "start_time": train_start,
                    "end_time": test_end,
                    "fit_start_time": train_start,
                    "fit_end_time": train_end,
                    "instruments": market,
                }
            },
            "segments": {
                "train": [train_start, train_end],
                "valid": [valid_start, valid_end],
                "test": [test_start, test_end],
            }
        }
    }

    model_config = {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt",
        "kwargs": {
            "loss": "mse",
            "colsample_bytree": 0.8879,
            "learning_rate": 0.05,
            "subsample": 0.8789,
            "lambda_l1": 205.6999,
            "lambda_l2": 580.9768,
            "max_depth": 8,
            "num_leaves": 210,
            "num_threads": 20,
            "early_stopping_rounds": 50,
            "num_boost_round": 1000
        }
    }

    print("Initializing Dataset with custom Open2Open Label...")
    dataset = init_instance_by_config(dataset_config)

    print("Initializing Model...")
    model = init_instance_by_config(model_config)

    print("Starting Training (this may take a few minutes)...")
    with R.start(experiment_name="train_v2_open2open"):
        model.fit(dataset)
        R.save_objects(trained_model=model)
        print("Training finished.")
        
        print("Generating Predictions for Test Data...")
        pred = model.predict(dataset)
        
        pred_dir = WORKSPACE_DIR / "data" / "cn_stock" / "predictions"
        pred_dir.mkdir(parents=True, exist_ok=True)
        
        out_path = pred_dir / "v2_open2open.pkl"
        pred.to_pickle(str(out_path))
        print(f"Predictions saved successfully to: {out_path}")

    print("V2 Open2Open Pipeline Completed Successfully!")

# Define the custom handler at the top level so it can be pickled if needed
from qlib.contrib.data.handler import Alpha158
class Alpha158Open2Open(Alpha158):
    def get_label_config(self):
        return (["Ref($open, -2) / Ref($open, -1) - 1"], ["LABEL0"])

if __name__ == '__main__':
    train_v2()
