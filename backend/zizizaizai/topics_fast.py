import os
import sys
import json
import yaml
import datetime
import pandas as pd
from pathlib import Path

# Add project paths
CUR_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CUR_DIR.parent
sys.path.append(str(PROJECT_DIR))
sys.path.append(str(PROJECT_DIR.parent / "scripts"))

from market_data.adapters.research import IwencaiAdapter

def fetch_fast_topics():
    print("=====================================")
    print("Running Fast Topics (iWencai Fallback)")
    print("=====================================")
    
    config_path = PROJECT_DIR / "secret.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    adapter = IwencaiAdapter(config)
    
    # 1. Fetch Today's Limit Ups and their concepts
    print("1. Fetching today's limit-up stocks and concepts...")
    res_limit_ups = adapter.query2data("今日涨停及其所属概念")
    
    # 2. Fetch Today's Concept Performance
    print("2. Fetching today's concept performance...")
    res_concepts = adapter.query2data("今日所有概念板块及涨跌幅排行")
    
    if not res_limit_ups or not res_concepts:
        print("Failed to fetch data from iWencai. Aborting fast topics.")
        return
        
    df_lu = pd.DataFrame(res_limit_ups)
    df_cp = pd.DataFrame(res_concepts)
    
    # Parse concepts
    # iWencai usually returns something like "所属同花顺行业" or "所属概念"
    concept_col = next((c for c in df_lu.columns if "概念" in c or "行业" in c), None)
    symbol_col = next((c for c in df_lu.columns if "代码" in c), None)
    name_col = next((c for c in df_lu.columns if "简称" in c), None)
    reason_col = next((c for c in df_lu.columns if "涨停原因" in c), None)
    
    if not concept_col or not symbol_col or not name_col:
        print(f"Could not parse required columns from limit ups. Columns: {df_lu.columns}")
        return
        
    # Build mapping: concept -> list of limit up stocks
    concept_stocks = {}
    for _, row in df_lu.iterrows():
        concepts = row[concept_col]
        if not isinstance(concepts, list):
            if isinstance(concepts, str):
                concepts = [c.strip() for c in concepts.replace(";", ",").replace("；", ",").split(",")]
            else:
                continue
                
        symbol = row[symbol_col]
        name = row[name_col]
        reason = row[reason_col] if reason_col in df_lu.columns else ""
        
        for c in concepts:
            if c not in concept_stocks:
                concept_stocks[c] = []
            concept_stocks[c].append({
                "个股": name,
                "相关性": str(reason) if pd.notna(reason) else "",
                "symbol": symbol
            })
            
    # Process Concept Performance to get top hot concepts
    # We want concepts that have the most limit-ups, and sort them
    topics_output = []
    
    cp_name_col = next((c for c in df_cp.columns if "简称" in c or "名称" in c), None)
    cp_pct_col = next((c for c in df_cp.columns if "涨跌幅" in c), None)
    cp_code_col = next((c for c in df_cp.columns if "代码" in c), None)
    
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    
    for concept, stocks in concept_stocks.items():
        if len(stocks) < 2:
            continue # Skip concepts with only 1 limit up to reduce noise
            
        # Find performance
        pct_chg = 0.0
        c_code = concept
        if cp_name_col and not df_cp.empty:
            match = df_cp[df_cp[cp_name_col] == concept]
            if not match.empty:
                val = match.iloc[0][cp_pct_col]
                if pd.notna(val):
                    pct_chg = float(val)
                c_code = str(match.iloc[0][cp_code_col])
                
        topics_output.append({
            "id": c_code,
            "name": f"{concept}({today_str})",
            "content": f"今日涨跌幅: {pct_chg:.2f}%. 涨停家数: {len(stocks)}",
            "rows": stocks,
            "pct_chg": pct_chg,
            "is_top": 1 if len(stocks) >= 5 else 0,
            "updated_time": datetime.datetime.now().isoformat()
        })
        
    # Sort topics by number of limit-ups
    topics_output.sort(key=lambda x: (len(x["rows"]), x["pct_chg"]), reverse=True)
    
    # Save output
    save_dir = PROJECT_DIR.parent / "data/cn_stock/hierarchical/signals"
    save_dir.mkdir(parents=True, exist_ok=True)
    
    topics_path = save_dir / "iwencai_topics.json"
    with open(topics_path, "w", encoding="utf-8") as f:
        json.dump(topics_output, f, ensure_ascii=False, indent=2)
        
    klines_path = save_dir / "iwencai_klines.json"
    with open(klines_path, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2) # Empty K-lines for now
        
    print(f"Successfully generated Fast Topics: {len(topics_output)} concepts.")
    print(f"Saved to {topics_path}")

if __name__ == "__main__":
    fetch_fast_topics()
