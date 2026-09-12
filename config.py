"""Config management — reads provisioning key and settings from config file."""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".openrouter-tracker"
CONFIG_FILE = CONFIG_DIR / "config.json"


def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    """Load app config: poll_interval, low_credit_threshold, provisioning_key."""
    ensure_config_dir()
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    defaults = {
        "poll_interval_seconds": 300,
        "low_credit_threshold": 10.0,
        "provisioning_key": os.environ.get("OPENROUTER_PROVISIONING_KEY", ""),
    }
    save_config(defaults)
    return defaults


def save_config(cfg):
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
