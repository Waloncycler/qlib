# Multi-Source Chinese Stock Data Collector for Qlib

This tool provides a unified, pluggable, and highly extensible pipeline to ingest Chinese stock market data from multiple sources:
1. **mootdx**: TDX high-speed direct client connection.
2. **akshare**: Community-maintained data APIs.
3. **ZIZIZAIZAI**: Custom timing and uplimit sentiment API.
4. **EastMoney (东方财富)**: Snapshot push lists.
5. **ZZSHARE**: Custom sentiment & daily K-line client SDK.
6. **Tencent/Sina**: HTTP polling APIs.

## Installation & Setup

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: If you use `zzshare`, ensure the custom `zzshare` package is installed in your python environment.*

2. **Configure Secrets**:
   Create a file named `secret.yaml` in this directory (`backend/secret.yaml`) to specify API credentials:
   ```yaml
   zizi_email: "waloncycler@163.com"
   zizi_password: "YOUR_ZIZIZAIZAI_PASSWORD"
   zzshare_token: "08afc8f2a1ef2ee3cba15c85bad7f3ced2f120005f3d4bed9efc2d65d9fc5d7d"
   ```
   Alternatively, you can expose these as environment variables:
   ```bash
   export ZIZI_EMAIL="waloncycler@163.com"
   export ZIZI_PASSWORD="YOUR_ZIZIZAIZAI_PASSWORD"
   export ZZSHARE_TOKEN="08afc8f2a1ef2ee3cba15c85bad7f3ced2f120005f3d4bed9efc2d65d9fc5d7d"
   ```

## Usage Examples

### 1. Download Data
Download A-share daily historical data using a specific source (e.g. `akshare` or `mootdx`):
```bash
python backend/market_data/collector.py download_data \
    --source akshare \
    --source_dir ~/.qlib/cn_stock_data/source \
    --start 2026-01-01 \
    --end 2026-05-20 \
    --limit_nums 10
```

### 2. Normalize Data
Standardize headers, fields, and calculate close-to-close changes:
```bash
python backend/market_data/collector.py normalize_data \
    --source_dir ~/.qlib/cn_stock_data/source \
    --normalize_dir ~/.qlib/cn_stock_data/normalize
```

### 3. Dump to Qlib Binary Format
Dump the normalized CSV files into Qlib's binary database:
```bash
python scripts/dump_bin.py dump_all \
    --csv_path ~/.qlib/cn_stock_data/normalize \
    --qlib_dir ~/.qlib/qlib_data/cn_data
```

### 4. Smart Backfill with iWencai
If there are missing sentiment or valuation data points in `market_sentiment.csv` (often the case for 2021 or older dates), use the smart backfill script. It has quota protection (max 190 queries/run) and prioritizes recent dates first:
```bash
python backend/backfill/backfill_iwencai_smart.py
```
