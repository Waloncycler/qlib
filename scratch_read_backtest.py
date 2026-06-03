import qlib
from qlib.workflow import R
import os
import pandas as pd

if __name__ == "__main__":
    provider_uri = os.path.abspath("data/cn_stock/standard/qlib_data")
    qlib.init(provider_uri=provider_uri, region="cn")
    
    exp = R.get_exp(experiment_name="custom_workflow")
    # Get latest run
    recorder = exp.list_recorders()
    for rec_id, rec in recorder.items():
        try:
            report = rec.load_object("report_normal_1day.pkl")
            print(f"Found in {rec_id}!")
            print(report.columns)
            print(report.tail())
            
            ana = rec.load_object("port_analysis_1day.pkl")
            print(ana)
            break
        except Exception as e:
            pass
