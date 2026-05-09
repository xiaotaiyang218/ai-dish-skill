from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent
LOCAL_CONFIG_PATH = SKILL_DIR.parent / '.local-secrets.json'
_LOCAL_CONFIG_CACHE: dict[str, Any] | None = None


def load_local_config() -> dict[str, Any]:
    global _LOCAL_CONFIG_CACHE
    if _LOCAL_CONFIG_CACHE is not None:
        return _LOCAL_CONFIG_CACHE
    if not LOCAL_CONFIG_PATH.exists():
        _LOCAL_CONFIG_CACHE = {}
        return _LOCAL_CONFIG_CACHE
    try:
        raw = json.loads(LOCAL_CONFIG_PATH.read_text(encoding='utf-8'))
        _LOCAL_CONFIG_CACHE = raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        _LOCAL_CONFIG_CACHE = {}
    return _LOCAL_CONFIG_CACHE


def get_secret(name: str, default: str = '') -> str:
    env_value = str(os.getenv(name) or '').strip()
    if env_value:
        return env_value
    config_value = load_local_config().get(name, default)
    return str(config_value or '').strip()


def local_secret_hint(*names: str) -> str:
    joined = ' and '.join(names)
    return f'set {joined} or add them to {LOCAL_CONFIG_PATH.name}'
