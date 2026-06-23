import sys
from pathlib import Path
import yaml

CUR_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CUR_DIR.parent
WORKSPACE_DIR = PROJECT_DIR.parent
DATA_DIR = WORKSPACE_DIR / "data/cn_stock/hierarchical"

# Import our stock resolver and adapters
sys.path.append(str(PROJECT_DIR))
sys.path.append(str(PROJECT_DIR.parent / "scripts"))

from core.stock_resolver import StockResolver
from market_data.adapters.research import IwencaiAdapter

# Shared instances
resolver = StockResolver()

config = {}
secret_path = PROJECT_DIR / "secret.yaml"
if secret_path.exists():
    with open(secret_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

iwencai_adapter = IwencaiAdapter(config)
