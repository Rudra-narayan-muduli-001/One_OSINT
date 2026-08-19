"""Paths and runtime locations for one-osint."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    _CONFIG_ROOT = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "one-osint"
else:
    _CONFIG_ROOT = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "one-osint"


def _project_root() -> Path:
    # src/one_osint/core -> project root
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = _project_root()

#: Repo data directory (bundled datasets, wordlists, user agents)
DATA_DIR = Path(os.environ.get("ONE_OSINT_DATA", PROJECT_ROOT / "data"))

#: User-writable config/keys/results location
CONFIG_DIR = Path(os.environ.get("ONE_OSINT_CONFIG", _CONFIG_ROOT))

KEYS_FILE = CONFIG_DIR / "keys.yaml"
DB_FILE = CONFIG_DIR / "one-osint.sqlite3"
RESULTS_DIR = CONFIG_DIR / "results"
LOG_DIR = CONFIG_DIR / "logs"
CACHE_DIR = CONFIG_DIR / "cache"

for _d in (CONFIG_DIR, RESULTS_DIR, LOG_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)
