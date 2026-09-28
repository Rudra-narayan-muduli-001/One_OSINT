from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..core.result import ModuleResult

if TYPE_CHECKING:
    from ..core.config import KeyVault, Settings


class BaseModule(ABC):
    name: str = ""
    description: str = ""
    input_types: tuple[str, ...] = ("email", "username", "phone", "domain", "ip", "file")
    opt_in: bool = False
    requires_key: str | None = None

    def __init__(self, keys: KeyVault | None = None, settings: Settings | None = None) -> None:
        self.keys = keys
        self.settings = settings

    def can_run(self, input_type: str) -> bool:
        if input_type not in self.input_types:
            return False
        if self.requires_key and self.keys and not self.keys.has(self.requires_key):
            return False
        return True

    @abstractmethod
    async def check(self, target: str) -> ModuleResult:
        raise NotImplementedError


def _get_registry():
    from . import discover_modules
    return discover_modules()


def get_module(name: str, keys=None, settings=None) -> BaseModule:
    cls = _get_registry().get(name)
    if cls is None:
        raise KeyError(f"unknown module: {name}")
    return cls(keys=keys, settings=settings)


def get_modules_for(
    input_type: str,
    keys=None,
    settings=None,
    allow_opt_in: bool = False,
) -> list[BaseModule]:
    out: list[BaseModule] = []
    for _name, cls in sorted(_get_registry().items()):
        mod = cls(keys=keys, settings=settings)
        if mod.can_run(input_type) and (allow_opt_in or not mod.opt_in):
            out.append(mod)
    return out