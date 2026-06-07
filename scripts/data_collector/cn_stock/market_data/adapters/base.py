# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import abc
import logging
import re
from typing import List, Optional
import pandas as pd
import requests

logger = logging.getLogger("CN_Stock_Adapters_Base")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def clean_symbol(symbol: str) -> str:
    """Extract the 6-digit stock code from any format (e.g. sh600000, 600000.SH, sz000001)."""
    match = re.search(r"\d{6}", symbol)
    if match:
        return match.group(0)
    return symbol


def get_market_prefix(symbol: str) -> str:
    """Determine market prefix (sh/sz/bj) based on code rules."""
    code = clean_symbol(symbol)
    if code.startswith(("6", "9", "5", "688")):
        return "sh"
    elif code.startswith(("0", "3", "2", "184", "159", "002", "300")):
        return "sz"
    elif code.startswith(("8", "4")):
        return "bj"
    return "sh"  # Default fallback


def to_qlib_symbol(symbol: str) -> str:
    """Convert stock code to Qlib standard (e.g. SH600000, SZ000001)."""
    code = clean_symbol(symbol)
    prefix = get_market_prefix(code).upper()
    return f"{prefix}{code}"


def to_ts_code(symbol: str) -> str:
    """Convert to Tushare/ZZSHARE format (e.g. 600000.SH, 000001.SZ)."""
    code = clean_symbol(symbol)
    prefix = get_market_prefix(code).upper()
    return f"{code}.{prefix}"


def to_tencent_symbol(symbol: str) -> str:
    """Convert to Tencent format (e.g. sh600000, sz000001)."""
    code = clean_symbol(symbol)
    prefix = get_market_prefix(code).lower()
    return f"{prefix}{code}"


def resilient_request(
    method: str,
    url: str,
    max_retries: int = 3,
    backoff_base: float = 1.5,
    timeout: int = 8,
    verify: bool = False,
    **kwargs,
) -> requests.Response:
    """Unified HTTP request with exponential backoff retry.

    Automatically retries on ConnectionError, Timeout, SSLError,
    and RemoteDisconnected errors.

    Args:
        method: HTTP method ('get' or 'post').
        max_retries: Maximum number of retry attempts.
        backoff_base: Base for exponential backoff (seconds).
        timeout: Request timeout in seconds.
        **kwargs: Passed directly to requests.request().

    Returns:
        requests.Response object.

    Raises:
        requests.RequestException: If all retries are exhausted.
    """
    import time
    from requests.exceptions import ConnectionError, Timeout, ChunkedEncodingError

    kwargs.setdefault("timeout", timeout)
    if "headers" not in kwargs:
        kwargs["headers"] = {"User-Agent": UA}
    kwargs.setdefault("verify", verify)

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.request(method, url, **kwargs)
            return resp
        except (ConnectionError, Timeout, ChunkedEncodingError, OSError) as e:
            last_exc = e
            if attempt < max_retries:
                wait = backoff_base ** attempt
                logger.warning(
                    f"Request to {url} failed (attempt {attempt}/{max_retries}): {e}. "
                    f"Retrying in {wait:.1f}s..."
                )
                time.sleep(wait)
            else:
                logger.error(
                    f"Request to {url} failed after {max_retries} attempts: {e}"
                )
        except Exception as e:
            # Non-retryable errors (e.g. invalid JSON, programming errors)
            raise

    raise last_exc


def eastmoney_datacenter(
    report_name: str,
    columns: str = "ALL",
    filter_str: str = "",
    page_size: int = 50,
    sort_columns: str = "",
    sort_types: str = "-1",
) -> list:
    """EastMoney datacenter unified query endpoint (used across Dragon-Tiger, lockups, margins, block trades, shareholders, dividends)."""
    params = {
        "reportName": report_name,
        "columns": columns,
        "filter": filter_str,
        "pageNumber": "1",
        "pageSize": str(page_size),
        "sortColumns": sort_columns,
        "sortTypes": sort_types,
        "source": "WEB",
        "client": "WEB",
    }
    try:
        r = resilient_request("get", DATACENTER_URL, params=params, headers={"User-Agent": UA})
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            return d["result"]["data"]
    except Exception as e:
        logger.error(f"EastMoney datacenter query failed ({report_name}): {e}")
    return []


class BaseSourceAdapter(abc.ABC):
    """Abstract Base Class for pluggable data source adapters."""

    def __init__(self, config: dict):
        self.config = config

    @abc.abstractmethod
    def get_instrument_list(self) -> List[str]:
        """Get the list of stock symbols available in this source."""
        raise NotImplementedError

    @abc.abstractmethod
    def fetch_symbol_data(
        self,
        symbol: str,
        interval: str,
        start_datetime: pd.Timestamp,
        end_datetime: pd.Timestamp,
    ) -> pd.DataFrame:
        """Fetch symbol data."""
        raise NotImplementedError


def get_mootdx_client(market: str = "std") -> Optional[object]:
    """Helper to initialize and return a Mootdx Quotes client with robust failover.
    Bypasses mootdx config unpack bugs by supplying server explicitly.
    """
    try:
        from mootdx import config
        from mootdx.quotes import Quotes
        config.setup()
        
        # Try retrieving standard server list
        servers = config.get('SERVER', {}).get('HQ' if market == "std" else 'EX', [])
        if not servers:
            servers = [["深圳双线主站1", "110.41.147.114", 7709]]
            
        for s in servers:
            if len(s) >= 3:
                name, ip, port = s[0], s[1], s[2]
                try:
                    # Pass server explicitly as a tuple (ip, port) to avoid unpacking error in mootdx config.json
                    client = Quotes.factory(market=market, server=(ip, int(port)))
                    return client
                except Exception as e:
                    logger.debug(f"Mootdx server {name} ({ip}:{port}) connection failed: {e}")
        
        # Last resort fallback
        return Quotes.factory(market=market)
    except Exception as e:
        logger.error(f"Failed to initialize Mootdx client: {e}")
    return None

