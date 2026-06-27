"""
AlphaShortLine 二分类版：预测次日涨跌方向（非连续收益）

优化方向：
1. 标签改为二分类：1 = open2close > 0, 0 = 下跌/平盘
2. 追加持续性特征：连涨天数、放量天数、日内强度
3. LightGBM 改用 binary logloss + AUC 评估
4. 训练后输出特征重要性 Top 30

输出: v3_binary.pkl → 被 signal_backtest.py 加载（概率值，越高越看好）
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
from qlib.data.dataset.handler import DataHandlerLP

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_dir))
from core.config import WORKSPACE_DIR

# 复用 AlphaShortLine 基础特征
from train_v3_shortline import AlphaShortLine


# ============================================================
# 二分类 Handler
# ============================================================

class AlphaShortLineBinary(AlphaShortLine):
    """
    特征继承 AlphaShortLine，额外追加持续性特征。
    标签改为二分类：1 = 上涨（open2close > 0），0 = 下跌或平盘。
    """
    def get_feature_config(self):
        fields, names = super().get_feature_config()

        # 追加持续性/强度特征
        extra_fields = [
            # 13. 连续2日上涨计数（近2日 close>open 的天数）
            "If($close > $open, 1, 0) + If(Ref($close, 1) > Ref($open, 1), 1, 0)",
            # 14. 连续3日上涨计数
            "If($close > $open, 1, 0) + If(Ref($close, 1) > Ref($open, 1), 1, 0) + If(Ref($close, 2) > Ref($open, 2), 1, 0)",
            # 15. 近5日放量天数（成交量 > 5日均量）
            "Sum(If($volume > Mean($volume, 5), 1, 0), 5)",
            # 16. 近5日缩量天数（成交量 < 5日均量*0.7）
            "Sum(If($volume < Mean($volume, 5) * 0.7, 1, 0), 5)",
            # 17. 日内涨幅（%）
            "($close - $open) / $open * 100",
            # 18. 5日涨幅 rank（用 MinMax 近似）
            "($close - $open) / ($open - Min($low, 5) + 1e-12)",
            # 19. 量比 rank（当日量 / 近20日最大量）
            "$volume / (Max($volume, 20) + 1e-12)",
            # 20. 近3日累计涨幅
            "$close / Ref($close, 3) - 1",
        ]
        extra_names = [
            "CUMUP2", "CUMUP3", "VOLUP5", "VOLDN5",
            "INTRARET", "POS_STR", "VOLRANK20", "CUMRET3",
        ]

        fields += extra_fields
        names += extra_names
        return fields, names

    def get_label_config(self):
        # 二分类：1 = 上涨, 0 = 下跌/平盘
        return (["If(Ref($close, -1) / $open - 1 > 0, 1, 0)"], ["LABEL0"])


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
                "class": "AlphaShortLineBinary",
                "module_path": "__main__",
                "kwargs": {
                    "start_time": train_start,
                    "end_time": test_end,
                    "fit_start_time": train_start,
                    "fit_end_time": train_end,
                    "instruments": market,
                    "infer_processors": [
                        {"class": "RobustZScoreNorm", "kwargs": {"fields_group": "feature", "clip_outlier": True}},
                        {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
                    ],
                    "learn_processors": [
                        {"class": "DropnaLabel"},
                    ],
                    "label": ["If(Ref($close, -1) / $open - 1 > 0, 1, 0)"],
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


# LightGBM 二分类配置（loss=binary）
model_config = {
    "class": "LGBModel",
    "module_path": "qlib.contrib.model.gbdt",
    "kwargs": {
        "loss": "binary",
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
        "metric": "auc",
    },
}


# ============================================================
# 特征重要性输出
# ============================================================

def report_feature_importance(model, dataset, save_path=None):
    """输出特征重要性 Top 30"""
    if model.model is None:
        print("Model not fitted, skip feature importance.")
        return

    # 获取特征名
    try:
        df = dataset.prepare("train", col_set="feature", data_key=DataHandlerLP.DK_L)
        feature_names = [str(n) for n in df.columns]
    except Exception:
        feature_names = None

    # gain importance
    importance_gain = model.model.feature_importance(importance_type="gain")
    # split importance
    importance_split = model.model.feature_importance(importance_type="split")

    imp_df = pd.DataFrame({
        "feature": feature_names if feature_names else range(len(importance_gain)),
        "gain": importance_gain,
        "split": importance_split,
    })
    imp_df = imp_df.sort_values("gain", ascending=False)

    print("\n" + "=" * 70)
    print("Feature Importance Top 30 (by gain)")
    print("=" * 70)
    for _, row in imp_df.head(30).iterrows():
        print(f"  {row['feature']:20s}  gain={row['gain']:8.0f}  split={row['split']:6.0f}")

    # 输出零 importance 特征数
    zero_count = (imp_df["gain"] == 0).sum()
    total = len(imp_df)
    print(f"\n  Zero-gain features: {zero_count}/{total} ({zero_count/total*100:.1f}%)")

    if save_path:
        imp_df.to_csv(save_path, index=False)
        print(f"  Saved to: {save_path}")

    return imp_df


# ============================================================
# 数据集标签分布统计
# ============================================================

def report_label_distribution(dataset):
    """输出各段标签分布"""
    print("\n" + "=" * 70)
    print("Label Distribution (1=up, 0=down/flat)")
    print("=" * 70)
    for seg in ["train", "valid", "test"]:
        if seg in dataset.segments:
            try:
                df = dataset.prepare(seg, col_set="label", data_key=DataHandlerLP.DK_L)
                total = len(df)
                up = int((df.iloc[:, 0] > 0.5).sum())
                print(f"  {seg:8s}: up={up}/{total} ({up/total*100:.1f}%), down/flat={total-up}/{total} ({(total-up)/total*100:.1f}%)")
            except Exception as e:
                print(f"  {seg:8s}: error - {e}")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    init_qlib()
    print("Building AlphaShortLineBinary dataset...")
    dataset = build_dataset()
    print("Dataset ready.")

    report_label_distribution(dataset)

    print("\nTraining binary classifier (loss=binary)...")
    model = init_instance_by_config(model_config)
    with R.start(experiment_name="train_v3_binary"):
        model.fit(dataset)
        R.save_objects(trained_model=model)

        # 特征重要性
        imp_path = WORKSPACE_DIR / "data" / "cn_stock" / "predictions" / "v3_binary_importance.csv"
        report_feature_importance(model, dataset, save_path=str(imp_path))

        # 预测（输出概率，越高越看涨）
        # 预测 valid+test 全段（保证 2025-07 起有预测值可用于回测）
        pred_valid = model.predict(dataset, segment="valid")
        pred_test = model.predict(dataset, segment="test")
        pred = pd.concat([pred_valid, pred_test])
        print(f"\nPrediction date range: {pred.index.get_level_values(0).min().date()} → {pred.index.get_level_values(0).max().date()}")
        print(f"Prediction stats: min={pred.min():.4f}, max={pred.max():.4f}, "
              f"mean={pred.mean():.4f}, median={pred.median():.4f}")

        pred_dir = WORKSPACE_DIR / "data" / "cn_stock" / "predictions"
        out_path = pred_dir / "v3_binary.pkl"
        pred.to_pickle(str(out_path))
        print(f"Predictions saved to: {out_path}")

    print("\nDone! Binary classifier training complete.")
