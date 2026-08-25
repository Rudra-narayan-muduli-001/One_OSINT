"""API key vault + settings.

Keys are stored in ``keys.yaml`` under the user config dir, or set as
environment variables, or placed in a ``.env`` file (project root or user
config dir). Resolution precedence: CLI flag > env var > ``.env`` > keys file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .paths import CONFIG_DIR, KEYS_FILE, PROJECT_ROOT


def _load_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env parser: KEY=VALUE lines, # comments, optional quotes."""
    loaded: dict[str, str] = {}
    if not path.is_file():
        return loaded
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value:
            loaded[key] = value
    return loaded


def _apply_env_file(path: Path) -> None:
    for key, value in _load_dotenv(path).items():
        os.environ.setdefault(key, value)


#: loaded once at import; real environment variables always win over .env
_apply_env_file(PROJECT_ROOT / ".env")
_apply_env_file(CONFIG_DIR / ".env")

#: Every API key the modules may need. Format: canonical -> (env var, description)
SUPPORTED_KEYS: dict[str, tuple[str, str]] = {
    "hibp": ("HIBP_API_KEY", "HaveIBeenPwned v3"),
    "emailrep": ("EMAILREP_API_KEY", "EmailRep.io"),
    "hunter": ("HUNTER_IO_API_KEY", "Hunter.io"),
    "intelx": ("INTELX_API_KEY", "Intelligence X"),
    "breachdirectory": ("BREACHDIRECTORY_API_KEY", "BreachDirectory (RapidAPI)"),
    "shodan": ("SHODAN_API_KEY", "Shodan"),
    "virustotal": ("VIRUSTOTAL_API_KEY", "VirusTotal"),
    "numverify": ("NUMVERIFY_API_KEY", "Numverify / apilayer"),
    "google_cse": ("GOOGLE_CSE_API_KEY", "Google Programmable Search"),
    "google_cse_cx": ("GOOGLE_CSE_CX", "Google CSE engine ID"),
    "google_geolocation": ("GOOGLE_GEOLOCATION_API_KEY", "Google Geolocation API"),
    "otx": ("OTX_API_KEY", "AlienVault OTX"),
    "certspotter": ("CERTSPOTTER_API_KEY", "CertSpotter"),
    "hudsonrock": ("HUDSONROCK_API_KEY", "Hudson Rock Cavalier"),
    "github": ("GITHUB_TOKEN", "GitHub token"),
    "rapidapi": ("RAPIDAPI_KEY", "RapidAPI host key"),
}


@dataclass
class KeyVault:
    """Loads and resolves API keys from file, env and explicit values."""

    overrides: dict[str, str] = field(default_factory=dict)
    _file_data: dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if KEYS_FILE.exists():
            try:
                raw = yaml.safe_load(KEYS_FILE.read_text(encoding="utf-8")) or {}
                self._file_data = {str(k): str(v) for k, v in raw.items() if v}
            except yaml.YAMLError:
                self._file_data = {}

    def get(self, name: str) -> str | None:
        """Resolve a key: override > env > keys file."""
        if name in self.overrides and self.overrides[name]:
            return self.overrides[name]
        spec = SUPPORTED_KEYS.get(name)
        if spec:
            env_val = os.environ.get(spec[0])
            if env_val:
                return env_val
        return self._file_data.get(name)

    def has(self, name: str) -> bool:
        return bool(self.get(name))

    @staticmethod
    def set(name: str, value: str) -> None:
        data: dict[str, str] = {}
        if KEYS_FILE.exists():
            data = yaml.safe_load(KEYS_FILE.read_text(encoding="utf-8")) or {}
        data[name] = value
        KEYS_FILE.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    @staticmethod
    def unset(name: str) -> bool:
        if not KEYS_FILE.exists():
            return False
        data = yaml.safe_load(KEYS_FILE.read_text(encoding="utf-8")) or {}
        if name in data:
            del data[name]
            KEYS_FILE.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            return True
        return False

    def list_keys(self) -> list[dict[str, object]]:
        out = []
        for name, (env, desc) in SUPPORTED_KEYS.items():
            out.append(
                {
                    "name": name,
                    "description": desc,
                    "env_var": env,
                    "set": bool(self.get(name)),
                }
            )
        return out


@dataclass
class Settings:
    """Runtime settings (proxies, concurrency, stealth)."""

    concurrency: int = 30
    timeout: float = 15.0
    max_retries: int = 2
    user_agent_rotate: bool = True
    proxies: list[str] = field(default_factory=list)
    proxy_rotate: bool = True
    tor: bool = False
    verify_tls: bool = True
    allow_loud: bool = False
