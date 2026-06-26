"""Shared authentication for ZIZIZAIZAI APIs.

Token resolution order:
1. ZIZIZAIZAI_TOKEN environment variable
2. Login via email/password from secret.yaml
"""
import os
import yaml
import requests
from pathlib import Path

_GLOBAL_TOKEN = None


def get_token() -> str | None:
    global _GLOBAL_TOKEN
    if _GLOBAL_TOKEN:
        return _GLOBAL_TOKEN

    token = os.environ.get("ZIZIZAIZAI_TOKEN")
    if not token:
        config_path = Path(__file__).resolve().parent.parent.parent.parent / "secret.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                email = config.get("zizi_email")
                password = config.get("zizi_password")
                if email and password:
                    try:
                        res = requests.post(
                            "https://api.zizizaizai.com/v2/login/email/login",
                            json={"email": email, "password": password},
                            headers={
                                "User-Agent": "Mozilla/5.0",
                                "Content-Type": "application/json",
                            },
                            timeout=15,
                        )
                        if res.status_code == 200:
                            data = res.json()
                            token = data.get("data", {}).get("access_token") or data.get("token")
                    except Exception:
                        pass

    _GLOBAL_TOKEN = token
    return token
