import qlib
from qlib.workflow import R
import pandas as pd
provider_uri = "/Users/walox/qlib/data/cn_stock/standard/qlib_data"
qlib.init(provider_uri=provider_uri, region="cn")
exp = R.get_exp(experiment_name="Topic_Alpha158_LGBM_Timing")
rec_ids = exp.list_recorders()
for rec_id in list(rec_ids.keys())[::-1]:
    rec = exp.get_recorder(rec_id)
    try:
        pos = rec.load_object("portfolio_analysis/positions_normal_1day.pkl")
        print("Type of pos:", type(pos))
        if isinstance(pos, dict):
            print("First key:", list(pos.keys())[0])
            first_val = pos[list(pos.keys())[0]]
            print("Type of value:", type(first_val))
            if isinstance(first_val, pd.Series):
                print(first_val.head())
            elif isinstance(first_val, dict):
                print(list(first_val.items())[:5])
            else:
                print(first_val)
        break
    except Exception as e:
        pass
