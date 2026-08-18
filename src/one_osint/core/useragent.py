"""User-Agent pool and browser impersonation."""

from __future__ import annotations

import random

from ..core.paths import DATA_DIR

_USER_AGENTS: list[str] | None = None


def load_user_agents() -> list[str]:
    global _USER_AGENTS
    if _USER_AGENTS is None:
        path = DATA_DIR / "useragents.txt"
        if path.exists():
            _USER_AGENTS = [
                line.strip()
                for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
                if line.strip()
            ]
        else:
            _USER_AGENTS = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ]
    return _USER_AGENTS


def random_user_agent() -> str:
    return random.choice(load_user_agents())
