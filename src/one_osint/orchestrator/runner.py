"""Run an investigation as a one-shot async entry (used by CLI and API)."""

from __future__ import annotations

from typing import Any

from ..core.config import KeyVault, Settings
from ..core.detect import detect_input_type
from .engine import Investigation


async def run_investigation(
    target: str,
    *,
    keys: KeyVault | None = None,
    settings: Settings | None = None,
    modules: list[str] | None = None,
    allow_opt_in: bool = False,
    event_sink=None,
    storage=None,
) -> dict[str, Any]:
    inv = Investigation(
        target=target,
        input_type=detect_input_type(target),
        settings=settings or Settings(),
        keys=keys or KeyVault(),
        modules=modules or [],
        allow_opt_in=allow_opt_in,
        event_sink=event_sink,
        storage=storage,
    )
    return await inv.run()
