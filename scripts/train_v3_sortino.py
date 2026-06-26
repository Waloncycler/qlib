"""
AlphaShortLine v2: Sortino 加权 + 特征 Rank 化降噪

优化措施：
1. SortinoWeighter: 训练时对负收益样本加权（下行风险惩罚）
   - Label < 0 的样本权重 = 2.0（惩罚暴跌）
   - Label >= 0 的样本权重 = 1.0
2. 特征 CSRankNorm: 仅对 feature 做截面排名归一化，消除极端值主导
   - Label 保持原始收益率（不做 CSRankNorm）

Label 仍然是 T开盘 → T+1收盘 的单日收益，不变。
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
from qlib.data.dataset.weight import Reweighter

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_dir))
from core.config import WORKSPACE_DIR


# ============================================================
# Sortino 权重器：对下行风险（负收益）加大惩罚
# ============================================================

class SortinoWeighter(Reweighter):
    """
    下行风险加权器。

    对 Label < 0 的样本赋予更高权重，使模型更关注避免亏损。
    相当于 Sortino ratio 的思路：只惩罚下行波动。

    Parameters
    ----------
    down_weight : float
        负收益样本的权重倍数（默认 2.0）
    """

    def __init__(self, down_weight=2.0):
        self.down_weight = down_weight

    def reweight(self, data):
        """data 是 prepare 返回的 DataFrame，含 feature 和 label 列"""
        # 获取 label 值
        if isinstance(data, pd.DataFrame) and "label" in data:
            labels = data["label"]
            if isinstance(labels, pd.DataFrame):
                labels = labels.iloc[:, 0]
        else:
            # fallback：如果结构不同，返回等权
            return np.ones(len(data))

        # 负收益 → down_weight，正收益 → 1.0
        weights = np.where(labels.values < 0, self.down_weight, 1.0)
        return weights


# ============================================================
# 自定义短线 Handler（同 v1，保持不变）
# ============================================================

class AlphaShortLine(Alpha158):
    """
    Alpha158 基础特征 + 短线专属特征
    Label: Ref($close, -1) / $open - 1（T开盘→T+1收盘）
    """

    def get_feature_config(self):
        fields, names = super().get_feature_config()

        short_fields = [
            "$open / Ref($close, 1) - 1",
            "$volume / Mean($volume, 5)",
            "($high - $low) / $close",
            "($close - $open) / ($high - $low + 1e-12)",
            "($high - Greater($open, $close)) / ($high - $low + 1e-12)",
            "(Less($open, $close) - $low) / ($high - $low + 1e-12)",
            "($close - $open) / $open",
            "$close / Ref($close, 5) - 1",
            "$factor * $volume / (Ref($factor, 1) * Ref($volume, 1) + 1e-12)",
            "($close / Ref($close, 1) - 1)",
            "Mean($close / Ref($close, 1) - 1, 3)",
            "Std($close / Ref($close, 1) - 1, 5)",
        ]
        short_names = [
            "GAP", "VRATIO", "AMP", "BODYR", "UPSHADOW", "DOWNSHADOW",
            "INTRAMOM", "MOM5", "TURNOVER_CHG", "PCT_CHG", "MA3_RET", "VOL5",
        ]

        fields += short_fields
        names += short_names
        return fields, names

    def get_label_config(self):
        return (["Ref($close, -1) / $open - 1"], ["LABEL0"])


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
    """
    构建数据集：
    - infer_processors: RobustZScoreNorm → CSRankNorm（仅 feature）→ Fillna
      CSRankNorm 消除极端特征值的主导效应
    - learn_processors: 只用 DropnaLabel（Label 不做 CSRankNorm，保留原始收益幅度）
    """
    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "AlphaShortLine",
                "module_path": "__main__",
                "kwargs": {
                    "start_time": train_start,
                    "end_time": test_end,
                    "fit_start_time": train_start,
                    "fit_end_time": train_end,
                    "instruments": market,
                    "infer_processors": [
                        {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
                        # 特征 Rank 化：消除极端值主导
                        {"class": "CSRankNorm", "kwargs": {"fields_group": "feature"}},
                        {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
                    ],
                    # Label 不做 CSRankNorm，保留原始收益幅度
                    "learn_processors": [
                        {"class": "DropnaLabel"},
                    ],
                    "label": ["Ref($close, -1) / $open - 1"],
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


# LGBM 参数（同 v1 最优参数）
model_config = {
    "class": "LGBModel",
    "module_path": "qlib.contrib.model.gbdt",
    "kwargs": {
        "loss": "mse",
        "colsample_bytree": 0.5306,
        "learning_rate": 0.0120,
        "subsample": 0.8040,
        "subsample_freq": 1,
        "lambda_l1": 0.4119,
        "lambda_l2": 0.0060,
        "max_depth": 10,
        "num_leaves": 60,
        "min_child_samples": 72,
        "min_split_gain": 0.9678,
        "num_threads": 20,
        "early_stopping_rounds": 50,
        "num_boost_round": 1000,
    },
}


if __name__ == "__main__":
    init_qlib()
    print("Building AlphaShortLine v2 dataset (Sortino weight + Feature CSRankNorm)...")
    dataset = build_dataset()
    print("Dataset ready.")

    # 创建 Sortino 权重器
    weighter = SortinoWeighter(down_weight=2.0)
    print("SortinoWeighter: down_weight=2.0 (negative returns penalized 2x)")

    print("Training v3_open2close with Sortino weighting...")
    model = init_instance_by_config(model_config)
    with R.start(experiment_name="train_v3_sortino"):
        # 传入 reweighter 实现下行风险加权
        model.fit(dataset, reweighter=weighter)
        R.save_objects(trained_model=model)
        pred = model.predict(dataset)

        pred_dir = WORKSPACE_DIR / "data" / "cn_stock" / "predictions"
        out_path = pred_dir / "v3_open2close.pkl"
        pred.to_pickle(str(out_path))
        print(f"Predictions saved to: {out_path}")

    print("Done! AlphaShortLine v2 (Sortino) training complete.")
