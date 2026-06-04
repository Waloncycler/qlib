import os
import argparse
import datetime
import json
import warnings
import pandas as pd
warnings.filterwarnings("ignore")

# Force MLFlow to allow file store
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

import qlib
from qlib.utils import init_instance_by_config
from qlib.backtest import backtest, executor
from qlib.contrib.strategy.signal_strategy import WeightStrategyBase

class SingleStockThresholdStrategy(WeightStrategyBase):
    def __init__(self, signal, threshold_buy=0.001, threshold_sell=-0.001, **kwargs):
        super().__init__(signal=signal, **kwargs)
        self.threshold_buy = threshold_buy
        self.threshold_sell = threshold_sell

    def generate_target_weight_position(self, score, current, **kwargs):
        target_weight = {}
        for stock, signal_val in score.items():
            if signal_val > self.threshold_buy:
                target_weight[stock] = 1.0
            elif signal_val < self.threshold_sell:
                target_weight[stock] = 0.0
            else:
                # hold current weight if between thresholds
                if current and stock in current.get_stock_list():
                    target_weight[stock] = current.get_stock_weight(stock)
                else:
                    target_weight[stock] = 0.0
        return target_weight


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", type=str, required=True, help="Stock symbol, e.g., SZ002199")
    parser.add_argument("--start", type=str, required=True, help="Backtest start date")
    parser.add_argument("--end", type=str, required=True, help="Backtest end date")
    args = parser.parse_args()

    # The script is in scripts/data_collector/cn_stock/
    provider_uri = os.path.abspath("../../../data/cn_stock/standard/qlib_data")
    qlib.init(provider_uri=provider_uri, region="cn")

    # Add 1 year to training start time to ensure we have enough data
    # Actually, let's train from 2020-01-01 to start date
    start_dt = pd.to_datetime(args.start)
    train_start = "2020-01-01"
    train_end = (start_dt - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "DataHandlerLP",
                "module_path": "qlib.data.dataset.handler",
                "kwargs": {
                    "instruments": [args.symbol],
                    "start_time": train_start,
                    "end_time": args.end,
                    "infer_processors": [],
                    "learn_processors": [{"class": "DropnaLabel"}],
                    "data_loader": {
                        "class": "QlibDataLoader",
                        "kwargs": {
                            "config": {
                                "feature": (
                                    ["$close", "$open", "$high", "$low", "$volume"], 
                                    ["close", "open", "high", "low", "volume"]
                                ),
                                "label": (["Ref($close, -2)/Ref($close, -1) - 1"], ["label"]),
                            }
                        }
                    }
                }
            },
            "segments": {
                "train": (train_start, train_end),
                "valid": (train_start, train_end), # use train as valid for speed
                "test": (args.start, args.end),
            },
        },
    }

    model_config = {
        "class": "LinearModel",
        "module_path": "qlib.contrib.model.linear",
        "kwargs": {
            "estimator": "ols",
        },
    }

    try:
        dataset = init_instance_by_config(dataset_config)
        model = init_instance_by_config(model_config)
        
        # Train on the fly for the single stock
        model.fit(dataset)
        pred = model.predict(dataset)
        
        strategy = SingleStockThresholdStrategy(
            signal=pred,
            threshold_buy=0.001,
            threshold_sell=-0.001,
        )

        trade_executor = executor.SimulatorExecutor(time_per_step="day", generate_portfolio_metrics=True)

        port_metrics, _ = backtest(
            executor=trade_executor,
            strategy=strategy,
            start_time=args.start,
            end_time=args.end,
            account=100000,
            benchmark=args.symbol,
            exchange_kwargs={
                "freq": "day",
                "limit_threshold": 0.095,
                "deal_price": "close",
                "open_cost": 0.0005,
                "close_cost": 0.0015,
                "min_cost": 5,
            }
        )

        report_data = port_metrics.get("1day")
        if report_data is None:
            print(json.dumps({"status": "error", "message": "No backtest results generated. Stock might be suspended or lacking data."}))
            return
            
        if isinstance(report_data, tuple):
            report_normal = report_data[0]
        else:
            report_normal = report_data
            
        if report_normal.empty:
            print(json.dumps({"status": "error", "message": "Backtest result is empty."}))
            return

        # Parse cumulative return curve
        cum_strategy = (1 + report_normal["return"] - report_normal["cost"]).cumprod() - 1
        cum_bench = (1 + report_normal["bench"]).cumprod() - 1
        
        curve_data = []
        for date, row in report_normal.iterrows():
            d_str = date.strftime("%Y-%m-%d")
            
            # extract signal from pred
            signal_val = 0.0
            if date in pred.index.get_level_values("datetime"):
                try:
                    s_val = pred.loc[(date, args.symbol)]
                    if isinstance(s_val, pd.Series): s_val = s_val.iloc[0]
                    # 1.0 for buy/hold, 0.0 for sell/empty
                    signal_val = 1.0 if s_val > 0.001 else 0.0
                except:
                    pass

            curve_data.append({
                "date": d_str,
                "strategy": float(cum_strategy.loc[date]),
                "benchmark": float(cum_bench.loc[date]),
                "timing_signal": float(signal_val)
            })

        # Calculate metrics (Information ratio requires port_analysis_1day but we can compute simplified)
        annualized_return = (cum_strategy.iloc[-1] + 1) ** (252 / len(cum_strategy)) - 1 if len(cum_strategy) > 0 else 0
        drawdown = (cum_strategy + 1) / (cum_strategy + 1).cummax() - 1
        max_drawdown = drawdown.min()

        res = {
            "status": "success",
            "data": {
                "metrics": {
                    "annualized_return": float(annualized_return),
                    "max_drawdown": float(max_drawdown),
                    "information_ratio": 0.0 # Placeholder
                },
                "curve": curve_data
            }
        }
        
        print(json.dumps(res))

    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()
