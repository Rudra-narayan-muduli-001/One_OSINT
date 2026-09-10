from __future__ import annotations

import importlib
import inspect
import pkgutil
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


_MODULES: dict[str, type[BaseModule]] | None = None


def discover_modules() -> dict[str, type[BaseModule]]:
    global _MODULES
    if _MODULES is not None:
        return _MODULES
    _MODULES = {}
    pkg = importlib.import_module(__package__)
    for modinfo in pkgutil.walk_packages(pkg.__path__, __package__ + "."):
        try:
            mod = importlib.import_module(modinfo.name)
        except Exception:
            continue
        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if (
                cls is not BaseModule
                and issubclass(cls, BaseModule)
                and cls.name
                and cls.__module__ == modinfo.name
            ):
                _MODULES[cls.name] = cls
    return _MODULES


def get_module(name: str, keys=None, settings=None) -> BaseModule:
    cls = discover_modules().get(name)
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
    for _name, cls in sorted(discover_modules().items()):
        mod = cls(keys=keys, settings=settings)
        if mod.can_run(input_type) and (allow_opt_in or not mod.opt_in):
            out.append(mod)
    return out
