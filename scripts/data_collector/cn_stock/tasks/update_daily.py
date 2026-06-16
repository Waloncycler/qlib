import os
import sys
import yaml
import requests
import subprocess
import argparse
import time
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).resolve().parent
PROJECT_DIR = current_dir.parent
workspace_dir = PROJECT_DIR.parent.parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from core.trading_calendar import is_trading_day

def main():
    parser = argparse.ArgumentParser(description="Update Data Script")
    parser.add_argument("--mode", type=str, choices=["morning", "close", "evening", "all", "topics"], default="all",
                        help="Schedule mode: morning (check calendar), close (fetch fast layers), evening (fetch all), topics (topics and klines only)")
    parser.add_argument("--force", action="store_true", help="Force update even if not a trading day")
    args = parser.parse_args()
    
    print("\n=====================================")
    print(f"Data Collection Run - Mode: {args.mode.upper()}")
    print("=====================================")
    
    if not args.force and not is_trading_day():
        print("Today is not a trading day. Skipping update.")
        return
        
    config_path = PROJECT_DIR / "secret.yaml"
    
    if not config_path.exists():
        print(f"Error: {config_path} not found.")
        sys.exit(1)
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
        
    email = config.get("zizi_email")
    password = config.get("zizi_password")
    
    if not email or not password:
        print("Error: zizi_email or zizi_password missing in secret.yaml")
        sys.exit(1)
        
    print("=====================================")
    print("0. Logging in to ZIZIZAIZAI...")
    print("=====================================")
    url = "https://api.zizizaizai.com/v2/login/email/login"
    payload = {"email": email, "password": password}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Referer": "https://quant.zizizaizai.com/login",
        "Origin": "https://quant.zizizaizai.com"
    }
    
    login_success = False
    token = None
    for attempt in range(1, 5):
        print(f"Login attempt {attempt}/4...")
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=30)
            res.raise_for_status()
            data = res.json()
            token = data.get("data", {}).get("access_token") or data.get("data", {}).get("token") or data.get("token")
            if token:
                login_success = True
                break
            else:
                print(f"Failed to find token in response on attempt {attempt}: {data}")
        except Exception as e:
            print(f"Login attempt {attempt} failed: {e}")
            if attempt < 4:
                time.sleep(attempt * 5)
                
    if not login_success or not token:
        print("Login failed after 4 attempts.")
        sys.exit(1)
        
    print("Successfully logged in and retrieved Bearer token.")
        
    # Set the token in environment
    os.environ["ZIZIZAIZAI_TOKEN"] = token
    
    import concurrent.futures

    # Step 1 & 2 can run in parallel (Evening or All modes)
    if args.mode in ["evening", "all"]:
        print("\n=====================================")
        print("Running parallel tasks: Topics & Sentiment...")
        print("=====================================")
        
        def run_script(script_name):
            print(f"Starting {script_name}...")
            subprocess.run([sys.executable, str(PROJECT_DIR / script_name)], check=True)
            print(f"Finished {script_name}")
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_topics = executor.submit(run_script, "zizizaizai/topics.py")
            future_sentiment = executor.submit(run_script, "sentiment/fetch_ziruxing.py")
            future_reports = executor.submit(run_script, "zizizaizai/reports.py")
            concurrent.futures.wait([future_topics, future_sentiment, future_reports])
            # Re-raise exceptions if any
            future_topics.result()
            future_sentiment.result()
            future_reports.result()

        print("\n=====================================")
        print("2.5 Running backfill_sentiment.py to update Eastmoney pools...")
        print("=====================================")
        run_script("backfill/backfill_sentiment.py")

        print("\n=====================================")
        print("2.6 Running backfill_enhanced.py to fetch Zizi Timing and Hardcore Data...")
        print("=====================================")
        run_script("backfill/backfill_enhanced.py")
        
        # Step 3 depends on Topics, so it runs after
        print("\n=====================================")
        print("3. Fetching Zizizaizai K-Lines...")
        print("=====================================")
        subprocess.run([sys.executable, str(PROJECT_DIR / "zizizaizai/klines.py")], check=True)
    elif args.mode == "topics":
        print("\n=====================================")
        print("Running topics mode: Topics & K-lines...")
        print("=====================================")
        subprocess.run([sys.executable, str(PROJECT_DIR / "zizizaizai/topics.py")], check=True)
        subprocess.run([sys.executable, str(PROJECT_DIR / "zizizaizai/klines.py")], check=True)
        print("Topics and K-lines updated. Exiting.")
        return
    elif args.mode == "morning":
        print("\n=====================================")
        print("Morning mode: Initialization and validation only. Exiting.")
        print("=====================================")
        return
    
    # Step 4: Layer downloads can run in parallel
    print("\n=====================================")
    print("4. Fetching Individual Stock Layers concurrently (Dynamic Watchlist)...")
    print("=====================================")
    
    # Get dynamic watchlist
    try:
        from core.stock_resolver import StockResolver
        resolver = StockResolver(config_path=str(config_path))
        target_symbols = resolver.get_dynamic_watchlist()
    except Exception as e:
        print(f"Warning: Failed to get dynamic watchlist ({e}). Falling back to SH600519.")
        target_symbols = ["SH600519"]
        
    if not target_symbols:
        target_symbols = ["SH600519"]
        
    if args.mode in ["close", "evening", "all"]:
        print(f"Target symbols for layers: {target_symbols}")
        
        if args.mode == "close":
            layers = ["market", "signals", "capital"]
        else:
            layers = ["market", "signals", "capital", "fundamentals", "news", "research", "filings"]
            
        save_dir = workspace_dir / "data/cn_stock/hierarchical"
        
        def run_layer(layer):
            print(f"→ Starting layer: {layer}...")
            for sym in target_symbols:
                cmd = [
                    sys.executable,
                    str(PROJECT_DIR / "market_data/collector.py"),
                    "download_layer",
                    "--layer", layer,
                    "--symbol", sym,
                    "--save_dir", str(save_dir)
                ]
                subprocess.run(cmd, check=True)
            print(f"✓ Finished layer: {layer}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(layers)) as executor:
            futures = {executor.submit(run_layer, layer): layer for layer in layers}
            for future in concurrent.futures.as_completed(futures):
                layer = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"Layer {layer} failed: {e}")
        
    print("\n=====================================")
    print("All Data Sources Updated Successfully (Concurrent Mode)!")
    print("=====================================")

if __name__ == "__main__":
    main()
