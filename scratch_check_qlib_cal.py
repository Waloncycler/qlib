import qlib
from qlib.data import D
import os

qlib.init(provider_uri=os.path.abspath("data/cn_stock/standard/qlib_data"), region="cn")
cal = D.calendar(start_time='2010-01-01')
print(f"Calendar dates: {len(cal)}")
if len(cal) > 0:
    print(f"First date: {cal[0]}, Last date: {cal[-1]}")
    
instruments = D.instruments(market='all')
features = D.list_instruments(instruments=instruments, as_list=True)
if features:
    first_stock = features[0]
    print(f"Stock: {first_stock}")
    df = D.features([first_stock], ['$close', '$pe_ttm'], start_time=cal[-1], end_time=cal[-1])
    print(df)
