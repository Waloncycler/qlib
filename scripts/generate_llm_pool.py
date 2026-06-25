import json
from pathlib import Path
import glob

def to_qlib_symbol(code):
    code = str(code)
    if code.startswith('6'):
        return 'SH' + code
    elif code.startswith('0') or code.startswith('3'):
        return 'SZ' + code
    else:
        return 'BJ' + code

def main():
    backend_dir = Path(__file__).parent.parent / "backend"
    pools_dir = backend_dir.parent / "data" / "cn_stock" / "stock_pools"
    
    pool_files = glob.glob(str(pools_dir / "stock_pool_*.json"))
    
    unique_symbols = set()
    for fpath in pool_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for stock in data.get("stocks", []):
                sym = to_qlib_symbol(stock.get("code", ""))
                if sym and not sym.startswith("BJ"):
                    unique_symbols.add(sym)
        except Exception as e:
            print(f"Error parsing {fpath}: {e}")
            
    instruments_dir = backend_dir.parent / "data" / "cn_stock" / "standard" / "qlib_data" / "instruments"
    instruments_dir.mkdir(parents=True, exist_ok=True)
    out_file = instruments_dir / "llm_pool.txt"
    
    with open(out_file, "w") as f:
        for sym in sorted(unique_symbols):
            f.write(f"{sym.lower()}\t2000-01-01\t2099-12-31\n")
            
    print(f"Successfully extracted {len(unique_symbols)} unique symbols from {len(pool_files)} LLM reports.")
    print(f"Saved to {out_file}")

if __name__ == "__main__":
    main()
