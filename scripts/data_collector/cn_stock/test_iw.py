import yaml
import sys
from pathlib import Path
CUR_DIR = Path(__file__).resolve().parent
sys.path.append(str(CUR_DIR))
from adapters.research import IwencaiAdapter

config = {}
with open("secret.yaml", "r") as f:
    config = yaml.safe_load(f)

adapter = IwencaiAdapter(config)
print(f"API Key loaded: {adapter.api_key[:10]}...")
df = adapter.fetch_iwencai("今日涨停")
print(f"Dataframe size: {len(df)}")
if len(df) > 0:
    print(df.head(2))
