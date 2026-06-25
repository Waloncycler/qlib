import akshare as ak
import pandas as pd
import logging
from modules.market.adapters.research import IwencaiAdapter

logger = logging.getLogger("PopularityAdapter")

class EastmoneyPopularityAdapter:
    """Adapter for fetching EastMoney real-time popularity ranking."""
    
    def __init__(self, config=None):
        self.config = config or {}

    def get_realtime_rank(self, symbol: str) -> int:
        """Fetch the latest real-time popularity rank for a specific symbol on EastMoney."""
        try:
            # akshare requires standard format e.g. SZ000001
            df = ak.stock_hot_rank_detail_realtime_em(symbol=symbol)
            if not df.empty and '排名' in df.columns:
                return int(df.iloc[-1]['排名'])
        except Exception as e:
            logger.error(f"Failed to fetch Eastmoney rank for {symbol}: {e}")
        return 99999  # Safe default if missing

class TonghuashunPopularityAdapter:
    """Adapter for fetching TongHuaShun real-time popularity ranking via iWencai."""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.iwc = IwencaiAdapter(self.config)

    def get_batch_data(self, symbols: list) -> dict:
        """Fetch real-time popularity rank and risk data for multiple symbols in one query."""
        results = {}
        if not symbols:
            return results
            
        try:
            # Clean symbols (e.g., SZ002149 -> 002149)
            raw_codes = [''.join([c for c in sym if c.isdigit()]) for sym in symbols]
            codes_str = " ".join(raw_codes)
            
            # Single combined query
            query = f"{codes_str} 个股热度排名 违规 立案调查 业绩预亏 风险提示 减持 监管函"
            data = self.iwc.query2data(query, limit=len(symbols) + 10)
            
            if data:
                for row in data:
                    sym_code = row.get("股票代码", "")
                    # Try to reconstruct the Qlib symbol (e.g., 002149.SZ -> SZ002149)
                    if "." in sym_code:
                        parts = sym_code.split(".")
                        qlib_sym = f"{parts[1].upper()}{parts[0]}"
                    else:
                        qlib_sym = sym_code  # Fallback
                        
                    rank = 99999
                    is_risky = False
                    
                    row_str = str(row)
                    for k, v in row.items():
                        if "热度排名" in str(k) or "人气排名" in str(k):
                            try:
                                rank = int(float(v))
                            except:
                                pass
                                
                    if "立案" in row_str or "监管函" in row_str or "减持计划" in row_str or "退市" in row_str:
                        is_risky = True
                        
                    # Also map back via name just in case symbol parsing is weird
                    name = row.get("股票简称", "")
                    
                    # Store by Qlib symbol if possible, or we will match by code in the caller
                    raw_c = ''.join([c for c in sym_code if c.isdigit()])
                    results[raw_c] = {"rank": rank, "is_risky": is_risky, "name": name}
                    
        except Exception as e:
            logger.error(f"Failed to fetch THS batch popularity/risk data: {e}")
            
        return results
