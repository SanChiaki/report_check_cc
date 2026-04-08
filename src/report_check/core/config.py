import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def _resolve_env_vars(obj: Any) -> Any:
    """Recursively resolve ${ENV_VAR} in config values."""
    if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        var_name = obj[2:-1]
        value = os.environ.get(var_name, "")
        if not value:
            logger.warning(f"Environment variable {var_name} is not set or empty")
        return value
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def load_config(path: str) -> dict:
    """Load YAML config file with environment variable resolution."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _resolve_env_vars(raw)
