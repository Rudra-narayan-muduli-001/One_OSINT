"""Regression tests for the API access-control and module-gating fixes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from one_osint.api.server import app
from one_osint.core.config import KeyVault, Settings
from one_osint.core.detect import InputType
from one_osint.core.result import Finding, ModuleResult
from one_osint.modules.base import BaseModule
from one_osint.orchestrator.engine import Investigation

BASE = "http://localhost"


class LoudModule(BaseModule):
    name = "loud_probe"
    description = "opt-in module that contacts the target directly"
    input_types = ("email",)
    opt_in = True

    async def check(self, target: str) -> ModuleResult:
        return ModuleResult(name=self.name)


class FileOnlyModule(BaseModule):
    name = "file_only"
    description = "accepts only the file input type"
    input_types = ("file",)

    async def check(self, target: str) -> ModuleResult:
        res = ModuleResult(name=self.name)
        res.findings.append(Finding("read", None, extra={"target": target}))
        return res


class EmailModule(BaseModule):
    name = "email_ok"
    description = "plain email module"
    input_types = ("email",)

    async def check(self, target: str) -> ModuleResult:
        return ModuleResult(name=self.name)


def _discover():
    return {"loud_probe": LoudModule, "file_only": FileOnlyModule, "email_ok": EmailModule}


def _pipeline(target: str, input_type: InputType, modules: list[str], opt_in: bool = False):
    import one_osint.orchestrator.engine as engine

    original = engine.discover_modules
    engine.discover_modules = _discover
    try:
        inv = Investigation(
            target=target,
            input_type=input_type,
            settings=Settings(),
            keys=KeyVault(),
            modules=modules,
            allow_opt_in=opt_in,
        )
        return [m.name for m in inv._build_pipeline()]
    finally:
        engine.discover_modules = original


def test_wildcard_cors_is_gone() -> None:
    """A hostile origin must not be granted read access (was allow_origins=['*'])."""
    with TestClient(app, base_url=BASE) as client:
        r = client.get("/api/investigations", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") is None


def test_vite_dev_origin_still_allowed() -> None:
    """The legitimate cross-origin client (Vite dev server) keeps working."""
    with TestClient(app, base_url=BASE) as client:
        r = client.get("/api/modules", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_forged_host_is_rejected() -> None:
    """Host validation blocks DNS rebinding, which CORS alone cannot."""
    with TestClient(app, base_url=BASE) as client:
        r = client.get("/api/investigations", headers={"Host": "evil.example"})
    assert r.status_code == 400


def test_explicit_modules_cannot_bypass_opt_in() -> None:
    assert _pipeline("a@example.com", InputType.EMAIL, ["loud_probe"]) == []
    assert _pipeline("a@example.com", InputType.EMAIL, ["loud_probe"], opt_in=True) == [
        "loud_probe"
    ]


def test_explicit_modules_cannot_bypass_input_type() -> None:
    """The file module stays unreachable when the target is not a file."""
    assert _pipeline("a@example.com", InputType.EMAIL, ["file_only"]) == []
    assert _pipeline("a@example.com", InputType.EMAIL, ["email_ok"]) == ["email_ok"]


@pytest.mark.parametrize("path", ["/api/investigations", "/api/keys"])
def test_no_credentialed_cors(path: str) -> None:
    """Credentials must never be combinable with a reflected origin."""
    with TestClient(app, base_url=BASE) as client:
        r = client.get(path, headers={"Origin": "https://evil.example"})
    assert r.headers.get("access-control-allow-credentials") is None