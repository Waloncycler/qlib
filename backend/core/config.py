import sys
import threading
from pathlib import Path
import yaml

global_v8_lock = threading.Lock()

CUR_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CUR_DIR.parent
WORKSPACE_DIR = PROJECT_DIR.parent
DATA_DIR = WORKSPACE_DIR / "data/cn_stock/hierarchical"

# Import our stock resolver and adapters
sys.path.append(str(PROJECT_DIR))
sys.path.append(str(PROJECT_DIR.parent / "scripts"))


def _load_yaml(path: Path) -> dict:
    """Load a YAML file, returning empty dict if missing or invalid."""
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


# --- Centralized configuration loading ---
config = _load_yaml(PROJECT_DIR / "secret.yaml")
watchlist = _load_yaml(PROJECT_DIR / "watchlist.yaml")

# Shared instances (import after config is ready to avoid circular dependency)
from core.data_resolver import DataResolver
from modules.market.adapters.research import IwencaiAdapter

resolver = DataResolver(config=config, watchlist=watchlist)
iwencai_adapter = IwencaiAdapter(config)
