from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

from .paths import CONFIG_DIR, KEYS_FILE, PROJECT_ROOT


def _load_dotenv(path: Path) -> dict[str, str]:
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


_apply_env_file(PROJECT_ROOT / ".env")
_apply_env_file(CONFIG_DIR / ".env")

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


class _KeySettings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow")

    hibp: str | None = None
    emailrep: str | None = None
    hunter: str | None = None
    intelx: str | None = None
    breachdirectory: str | None = None
    shodan: str | None = None
    virustotal: str | None = None
    numverify: str | None = None
    google_cse: str | None = None
    google_cse_cx: str | None = None
    google_geolocation: str | None = None
    otx: str | None = None
    certspotter: str | None = None
    hudsonrock: str | None = None
    github: str | None = None
    rapidapi: str | None = None


@dataclass
class KeyVault:
    overrides: dict[str, str] = field(default_factory=dict)
    _settings: _KeySettings = field(default_factory=_KeySettings, init=False)
    _file_data: dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if KEYS_FILE.exists():
            try:
                self._file_data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._file_data = {}

    def get(self, name: str) -> str | None:
        if name in self.overrides and self.overrides[name]:
            return self.overrides[name]
        spec = SUPPORTED_KEYS.get(name)
        if spec:
            env_val = os.environ.get(spec[0])
            if env_val:
                return env_val
        val = getattr(self._settings, name, None)
        if val:
            return val
        return self._file_data.get(name)

    def has(self, name: str) -> bool:
        return bool(self.get(name))

    @staticmethod
    def set(name: str, value: str) -> None:
        data: dict[str, str] = {}
        if KEYS_FILE.exists():
            try:
                data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        data[name] = value
        KEYS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def unset(name: str) -> bool:
        if not KEYS_FILE.exists():
            return False
        try:
            data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        if name in data:
            del data[name]
            KEYS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
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
    concurrency: int = 30
    timeout: float = 15.0
    max_retries: int = 2
    user_agent_rotate: bool = True
    proxies: list[str] = field(default_factory=list)
    proxy_rotate: bool = True
    tor: bool = False
    verify_tls: bool = True
    allow_loud: bool = False