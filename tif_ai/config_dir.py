"""OS-specific config directory handling (Phase 4, §5.3)."""

import os
import sys
import json
import shutil
import logging

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "config.json"


def get_config_dir() -> str:
    """Return the OS-specific TIF-AI config directory (§5.3)."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA")
        if not base:
            base = os.path.expanduser("~")
        return os.path.join(base, "TIF-AI")
    elif sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/TIF-AI")
    else:
        return os.path.expanduser("~/.config/tif-ai")


def ensure_config_dir() -> str:
    """Create the config directory if missing; return its path."""
    path = get_config_dir()
    os.makedirs(path, exist_ok=True)
    return path


def read_config() -> dict:
    """Read config.json from the config dir; return {} if absent."""
    path = os.path.join(get_config_dir(), CONFIG_FILENAME)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to read config: {e}")
        return {}


def write_config(config: dict) -> str:
    """Write config.json to the config dir; return the path."""
    ensure_config_dir()
    path = os.path.join(get_config_dir(), CONFIG_FILENAME)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        # Config may hold secrets (API keys) — restrict permissions.
        try:
            os.chmod(path, 0o600)
        except (NotImplementedError, OSError):
            pass
        return path
    except Exception as e:
        logger.error(f"Failed to write config: {e}")
        raise


def export_config(dest_path: str) -> str:
    """Copy config.json to dest_path for portability."""
    src = os.path.join(get_config_dir(), CONFIG_FILENAME)
    if not os.path.exists(src):
        raise FileNotFoundError("No config found to export; run `tif-ai install` first.")
    shutil.copy2(src, dest_path)
    return dest_path


def import_config(src_path: str) -> str:
    """Import a config.json from src_path into the config dir."""
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"Source config not found: {src_path}")
    ensure_config_dir()
    dest = os.path.join(get_config_dir(), CONFIG_FILENAME)
    shutil.copy2(src_path, dest)
    try:
        os.chmod(dest, 0o600)
    except (NotImplementedError, OSError):
        pass
    return dest
