import concurrent.futures
import time
from modules.market.adapters.popularity import EastmoneyPopularityAdapter, TonghuashunPopularityAdapter
from modules.market.adapters.research import IwencaiAdapter
from core.config import config

em_pop = EastmoneyPopularityAdapter(config)
ths_pop = TonghuashunPopularityAdapter(config)
iwc = IwencaiAdapter(config)

def fetch_stock_data(sym):
    em_rank = em_pop.get_realtime_rank(sym)
    ths_rank = ths_pop.get_realtime_rank(sym)
    raw_code = ''.join([c for c in sym if c.isdigit()])
    risk_query = f"{raw_code} 违规 立案调查 业绩预亏 风险提示 减持 监管函"
    risk_data = iwc.query2data(risk_query, limit=1)
    
    is_risky = False
    if risk_data and len(risk_data) > 0:
        row_str = str(risk_data[0])
        if "立案" in row_str or "监管函" in row_str or "减持计划" in row_str or "退市" in row_str:
            is_risky = True
            
    return sym, em_rank, ths_rank, is_risky

syms = ["SZ002149", "SZ300007", "SZ300065", "SZ002342", "SH603698"]

start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(fetch_stock_data, sym) for sym in syms]
    for future in concurrent.futures.as_completed(futures):
        print(future.result())

print(f"Time taken: {time.time() - start:.2f}s")
