
import qlib
from qlib.utils import init_instance_by_config, flatten_dict
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, PortAnaRecord, SigAnaRecord
import pandas as pd

if __name__ == "__main__":
    # provider_uri = "data/cn_stock/standard/qlib_data"
    # Actually, I should use absolute path to be safe
    import os
    provider_uri = os.path.abspath("data/cn_stock/standard/qlib_data")
    
    qlib.init(provider_uri=provider_uri, region="cn")

    market = "all"
    benchmark = "SH600000" # Using one of the stocks as benchmark for simplicity if CSI300 is not available

    import datetime
    # Use dynamic end dates to automatically run up to the latest date
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    data_handler_config = {
        "start_time": "2022-03-15",
        "end_time": today_str,
        "fit_start_time": "2022-03-15",
        "fit_end_time": "2023-12-31",
        "instruments": market,
    }

    dataset_config = {
        "class": "DatasetH",
        "module_path": "qlib.data.dataset",
        "kwargs": {
            "handler": {
                "class": "DataHandlerLP",
                "module_path": "qlib.data.dataset.handler",
                "kwargs": {
                    "instruments": market,
                    "start_time": "2022-03-15",
                    "end_time": today_str,
                    "infer_processors": [],
                    "learn_processors": [{"class": "DropnaLabel"}],
                    "data_loader": {
                        "class": "QlibDataLoader",
                        "kwargs": {
                            "config": {
                                "feature": (["$close"], ["close"]),
                                "label": (["Ref($close, -2)/Ref($close, -1) - 1"], ["label"]),
                            }
                        }
                    }
                }
            },
            "segments": {
                "train": ("2022-03-15", "2023-12-31"),
                "valid": ("2024-01-01", "2024-03-31"),
                "test": ("2024-04-01", today_str),
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

    port_analysis_config = {
        "executor": {
            "class": "SimulatorExecutor",
            "module_path": "qlib.backtest.executor",
            "kwargs": {
                "time_per_step": "day",
                "generate_portfolio_metrics": True,
            },
        },
        "strategy": {
            "class": "TimingTopkDropoutStrategy",
            "module_path": "timing_strategy",
            "kwargs": {
                "signal": "<PRED>", 
                "topk": 2, 
                "n_drop": 1,
                "timing_signal_path": "data/cn_stock/hierarchical/signals/market_sentiment.csv"
            },
        },
        "backtest": {
            "start_time": "2024-04-01",
            "end_time": (datetime.date.today() - datetime.timedelta(days=2)).strftime("%Y-%m-%d"),
            "account": 100000000,
            "benchmark": benchmark,
            "exchange_kwargs": {
                "freq": "day",
                "limit_threshold": 0.095,
                "deal_price": "close",
                "open_cost": 0.0005,
                "close_cost": 0.0015,
                "min_cost": 5,
            },
        },
    }

    # Initialize model and dataset
    model = init_instance_by_config(model_config)
    dataset = init_instance_by_config(dataset_config)

    # Start experiment
    with R.start(experiment_name="custom_workflow"):
        R.log_params(**flatten_dict(model_config))
        print("Fitting model...")
        model.fit(dataset)
        R.save_objects(**{"params.pkl": model})

        recorder = R.get_recorder()
        
        print("Generating signals...")
        sr = SignalRecord(model, dataset, recorder)
        sr.generate()

        print("Generating signal analysis...")
        sar = SigAnaRecord(recorder)
        sar.generate()

        print("Generating portfolio analysis...")
        # Note: Signal will be automatically retrieved from the recorder in PortAnaRecord if not provided in strategy kwargs
        par = PortAnaRecord(recorder, port_analysis_config, "day")
        par.generate()
        
        print("Workflow completed successfully!")
