"""
暴亏分类器：预测个股次日暴跌(>5%)概率

标签: 1 if Ref($close,-1)/$open-1 < -0.05 else 0
特征: 复用 AlphaShortLine 全部特征
用途: 作为 V3 选股的风控否决层

输出: crash_filter.pkl → 被 signal_backtest.py 加载
"""
import sys
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
from pathlib import Path

import numpy as np
import pandas as pd
import qlib
from qlib.constant import REG_CN
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.contrib.data.handler import Alpha158

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_dir))
from core.config import WORKSPACE_DIR

# 复用 train_v3_shortline 的 AlphaShortLine（同样特征集）
from train_v3_shortline import AlphaShortLine


# ============================================================
# 暴亏标签 Handler
# ============================================================

class CrashFilterHandler(AlphaShortLine):
    """
    特征同 AlphaShortLine，但标签改为二分类：
    1 = 次日暴跌（收益 < -5%），0 = 正常
    """
    def get_label_config(self):
        # T开盘买 -> T+1收盘卖，收益 < -5% 标记为 1（正类=危险）
        return (["If(Ref($close, -1) / $open - 1 < -0.05, 1, 0)"], ["LABEL0"])


# ============================================================
# 训练配置
# ============================================================

market = "shortline_pool"
train_start = "2024-01-01"
train_end = "2025-06-30"
valid_start = "2025-07-01"
valid_end = "2025-12-31"
test_start = "2026-01-01"
test_end = "2026-12-31"


def init_qlib():
    provider_uri = str(WORKSPACE_DIR / "data" / "cn_stock" / "standard" / "qlib_data")
    qlib.init(provider_uri=provider_uri, region=REG_CN)


def build_dataset():
    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "CrashFilterHandler",
                "module_path": "__main__",
                "kwargs": {
                    "start_time": train_start,
                    "end_time": test_end,
                    "fit_start_time": train_start,
                    "fit_end_time": train_end,
                    "instruments": market,
                    "infer_processors": [
                        {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
                        {"class": "CSRankNorm", "kwargs": {"fields_group": "feature"}},
                        {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
                    ],
                    "learn_processors": [
                        {"class": "DropnaLabel"},
                    ],
                    "label": ["If(Ref($close, -1) / $open - 1 < -0.05, 1, 0)"],
                },
            },
            "segments": {
                "train": [train_start, train_end],
                "valid": [valid_start, valid_end],
                "test": [test_start, test_end],
            },
        },
    }
    return init_instance_by_config(dataset_config)


# 分类模型参数：注重 recall（宁可误杀，不可漏网）
model_config = {
    "class": "LGBModel",
    "module_path": "qlib.contrib.model.gbdt",
    "kwargs": {
        "loss": "binary",          # 二分类（LGBModel 支持 mse 和 binary）
        "colsample_bytree": 0.5306,
        "learning_rate": 0.02,
        "subsample": 0.8040,
        "subsample_freq": 1,
        "lambda_l1": 0.4119,
        "lambda_l2": 0.0060,
        "max_depth": 8,
        "num_leaves": 60,
        "min_child_samples": 72,
        "num_threads": 20,
        "early_stopping_rounds": 50,
        "num_boost_round": 500,
    },
}


if __name__ == "__main__":
    init_qlib()
    print("Building CrashFilter dataset (AlphaShortLine features, binary crash label)...")
    dataset = build_dataset()

    # 检查正样本比例
    train_data = dataset.prepare("train", col_set=["label"])
    if isinstance(train_data, pd.DataFrame):
        train_labels = train_data.iloc[:, 0]
    else:
        train_labels = train_data
    crash_rate = train_labels.mean()
    total = len(train_labels)
    print(f"Train set: {total} samples, crash rate = {crash_rate:.2%} ({int(train_labels.sum())} crashes)")
    print(f"(即 {total - int(train_labels.sum())} 个正常 vs {int(train_labels.sum())} 个暴跌)")

    print("\nTraining crash classifier (cross_entropy loss)...")
    model = init_instance_by_config(model_config)
    with R.start(experiment_name="crash_filter"):
        model.fit(dataset)
        R.save_objects(trained_model=model)
        pred = model.predict(dataset)

        pred_dir = WORKSPACE_DIR / "data" / "cn_stock" / "predictions"
        out_path = pred_dir / "crash_filter.pkl"
        pred.to_pickle(str(out_path))
        print(f"\nCrash probabilities saved to: {out_path}")

    # 统计预测分布
    if isinstance(pred, pd.DataFrame):
        pred_series = pred.iloc[:, 0]
    else:
        pred_series = pred
    print(f"\nPrediction stats:")
    print(f"  mean={pred_series.mean():.4f}  median={pred_series.median():.4f}")
    print(f"  >0.3: {(pred_series > 0.3).mean():.1%}")
    print(f"  >0.5: {(pred_series > 0.5).mean():.1%}")
    print(f"  >0.7: {(pred_series > 0.7).mean():.1%}")

    print("\nDone! Crash filter training complete.")
