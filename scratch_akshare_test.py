import akshare as ak
import sys

print("Testing akshare stock_tfp_em")
try:
    df = ak.stock_tfp_em(date="20210104")
    print("tfp_em:", len(df))
except Exception as e:
    print(e)

print("Testing akshare stock_zt_pool_em for 20210104")
try:
    df = ak.stock_zt_pool_em(date="20210104")
    print("zt_pool_em 20210104:", len(df) if df is not None else "None")
except Exception as e:
    print("zt_pool_em 20210104 failed:", e)

try:
    df = ak.stock_market_fund_flow()
    print("stock_market_fund_flow columns:", df.columns.tolist() if df is not None else "None")
except Exception as e:
    print(e)
