"""Real-time intraday quotes from Tencent Finance."""
import requests
from loguru import logger


def get_live_quotes_service(symbols: list[str]):
    """Fetches real-time intraday quotes for a list of Qlib symbols from Tencent Finance."""
    if not symbols:
        return {"status": "success", "data": {}}

    # Qlib: SH600519 -> Tencent: sh600519
    tencent_symbols = [s.lower() for s in symbols]
    url = f"http://qt.gtimg.cn/q={','.join(tencent_symbols)}"

    try:
        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
        text = resp.text

        results = {}
        for line in text.strip().split('\n'):
            if not line or '=' not in line:
                continue
            parts = line.split('=')
            if len(parts) != 2:
                continue

            var_name = parts[0]
            data_str = parts[1].strip('";')
            fields = data_str.split('~')

            if len(fields) > 32:
                code = var_name.split('_')[-1].upper()
                name = fields[1]
                try:
                    current_price = float(fields[3])
                    yesterday_close = float(fields[4])
                    open_price = float(fields[5])
                    pct_change = float(fields[32])
                except ValueError:
                    continue

                results[code] = {
                    "price": current_price,
                    "yesterday_close": yesterday_close,
                    "open_price": open_price,
                    "pct_change": pct_change,
                    "name": name
                }

        return {"status": "success", "data": results}
    except Exception as e:
        logger.error(f"Error fetching live quotes: {e}")
        return {"status": "error", "message": str(e)}
