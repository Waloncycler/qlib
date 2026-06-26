import time
from pathlib import Path
import sys

PROJECT_DIR = Path("/Users/walox/qlib/backend")
sys.path.append(str(PROJECT_DIR))
sys.path.append(str(PROJECT_DIR.parent / "scripts"))

from core.data_resolver import DataResolver

resolver = DataResolver()

t0 = time.time()
print("Fetching market...")
resolver.resolve_single_stock("SH600519", "market")
t1 = time.time()
print(f"Market took {t1 - t0:.2f}s")

t0 = time.time()
print("Fetching signals...")
resolver.resolve_single_stock("SH600519", "signals")
t1 = time.time()
print(f"Signals took {t1 - t0:.2f}s")

t0 = time.time()
print("Fetching capital...")
resolver.resolve_single_stock("SH600519", "capital")
t1 = time.time()
print(f"Capital took {t1 - t0:.2f}s")

t0 = time.time()
print("Fetching fundamentals...")
resolver.resolve_single_stock("SH600519", "fundamentals")
t1 = time.time()
print(f"Fundamentals took {t1 - t0:.2f}s")

t0 = time.time()
print("Fetching news...")
resolver.resolve_single_stock("SH600519", "news")
t1 = time.time()
print(f"News took {t1 - t0:.2f}s")
