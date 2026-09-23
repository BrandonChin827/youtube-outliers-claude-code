"""Secret loading and per-brand storage paths.

Secrets live outside the skill so sharing or updating the skill cannot expose them.
"""

import os
import re
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("YOUTUBE_OUTLIERS_CONFIG_DIR", str(Path.home() / ".config" / "youtube-outliers"))).expanduser()
ENV_PATH = CONFIG_DIR / ".env"
FALLBACK_ENV_PATHS = ()
KEY_NAME = "SCRAPECREATORS_API_KEY"
NOTION_KEY_NAME = "NOTION_API_KEY"
CONTENT_HOME_VAR = "CONTENT_HOME"
DEFAULT_CONTENT_HOME = Path.home() / "Documents" / "Content"
BRAND_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def _read_setting(name, path):
    if not path or not Path(path).exists():
        return ""
    try:
        lines = Path(path).read_text().splitlines()
    except OSError:
        return ""
    for line in lines:
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].strip()
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip("'\"")
    return ""


def _search_files(name, primary=ENV_PATH):
    for path in (primary, *FALLBACK_ENV_PATHS):
        value = _read_setting(name, path)
        if value:
            return value
    return ""


def content_home():
    """Base directory holding one folder per brand."""
    override = os.environ.get(CONTENT_HOME_VAR, "").strip() or _search_files(CONTENT_HOME_VAR)
    return Path(override).expanduser() if override else DEFAULT_CONTENT_HOME


def brand_home(brand):
    brand = str(brand).strip().lower()
    if not BRAND_RE.fullmatch(brand):
        raise ValueError("Brand must use lowercase letters, numbers, and hyphens only.")
    return content_home() / brand


def load_key(name, env_path=ENV_PATH):
    value = os.environ.get(name, "").strip()
    return value or _search_files(name, env_path)


def load_api_key(env_path=ENV_PATH):
    return load_key(KEY_NAME, env_path)


def load_notion_key(env_path=ENV_PATH):
    return load_key(NOTION_KEY_NAME, env_path)
