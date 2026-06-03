import qlib
from qlib.data import D
import os

qlib.init(provider_uri=os.path.abspath("data/cn_stock/standard/qlib_data"), region="cn")
instruments = D.instruments(market='all')
features = D.list_instruments(instruments=instruments, as_list=True)
if features:
    first_stock = features[0]
    print(f"Stock: {first_stock}")
    df = D.features([first_stock], ['$close', '$open', '$high', '$low', '$volume', '$factor', '$pe_ttm', '$pb'], start_time='2021-01-04', end_time='2021-01-08')
    print(df)
