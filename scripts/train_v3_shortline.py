"""
AlphaShortLine: 短线专属特征 Handler

继承 Alpha158 全部特征 + 追加 12 个日频短线特征。
去掉 CSRankNorm，用原始收益率做 Label。

短线特征全部从现有 Qlib K 线数据（OHLCV+amount）构造，不需要外部数据。
"""

import sys
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
from pathlib import Path

import qlib
from qlib.constant import REG_CN
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.contrib.data.handler import Alpha158
from qlib.contrib.data.loader import Alpha158DL

backend_dir = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_dir))
from core.config import WORKSPACE_DIR


# ============================================================
# 自定义短线 Handler
# ============================================================

class AlphaShortLine(Alpha158):
    """
    Alpha158 基础特征 + 短线专属特征
    Label: Ref($close, -1) / $open - 1（T开盘→T+1收盘）
    """

    def get_feature_config(self):
        # 先拿到 Alpha158 的标准特征
        fields, names = super().get_feature_config()

        # 追加短线专属特征
        short_fields = [
            # 1. 竞价缺口（隔夜跳空）
            "$open / Ref($close, 1) - 1",
            # 2. 量比（今日成交量 / 5日均量）
            "$volume / Mean($volume, 5)",
            # 3. 振幅
            "($high - $low) / $close",
            # 4. 实体比率（日内涨跌幅 / 振幅）
            "($close - $open) / ($high - $low + 1e-12)",
            # 5. 上影线比率
            "($high - Greater($open, $close)) / ($high - $low + 1e-12)",
            # 6. 下影线比率
            "(Less($open, $close) - $low) / ($high - $low + 1e-12)",
            # 7. 日内动量
            "($close - $open) / $open",
            # 8. 5日收益动量
            "$close / Ref($close, 5) - 1",
            # 9. 成交额变化率
            "$factor * $volume / (Ref($factor, 1) * Ref($volume, 1) + 1e-12)",
            # 10. 封板强度（涨幅接近涨停的程度）
            "($close / Ref($close, 1) - 1)",
            # 11. 近3日平均涨幅
            "Mean($close / Ref($close, 1) - 1, 3)",
            # 12. 近5日波动率
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
    """构建 AlphaShortLine 数据集（去掉 CSRankNorm）"""
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
                        {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
                    ],
                    # 去掉 CSRankNorm，只用 DropnaLabel
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


# 使用 Optuna 优化后的最优参数
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
    print("Building AlphaShortLine dataset (Alpha158 + 12 short-line features, no CSRankNorm)...")
    dataset = build_dataset()
    print("Dataset ready.")

    print("Training v3_open2close with AlphaShortLine...")
    model = init_instance_by_config(model_config)
    with R.start(experiment_name="train_v3_shortline"):
        model.fit(dataset)
        R.save_objects(trained_model=model)
        pred = model.predict(dataset)

        pred_dir = WORKSPACE_DIR / "data" / "cn_stock" / "predictions"
        out_path = pred_dir / "v3_open2close.pkl"
        pred.to_pickle(str(out_path))
        print(f"Predictions saved to: {out_path}")

    print("Done! AlphaShortLine v3 training complete.")
