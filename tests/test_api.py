"""Tests for the orchestrator and the REST API layer."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from one_osint.api.server import app
from one_osint.core.config import KeyVault, Settings
from one_osint.core.detect import InputType
from one_osint.core.result import Finding, ModuleResult
from one_osint.core.storage import Storage
from one_osint.modules.base import BaseModule
from one_osint.orchestrator.engine import Investigation


class FakeModule(BaseModule):
    name = "fake_check"
    description = "fake"
    input_types = {"username"}

    async def check(self, target: str) -> ModuleResult:
        res = ModuleResult(name=self.name)
        res.findings.append(Finding("fake_finding", f"https://fake/{target}", extra={"target": target}))
        return res


def test_investigation_with_fake_module(monkeypatch) -> None:
    def fake_discover():
        return {"fake_check": FakeModule}

    monkeypatch.setattr("one_osint.orchestrator.engine.discover_modules", fake_discover)

    events: list[dict] = []

    async def sink(ev: dict) -> None:
        events.append(ev)

    inv = Investigation(
        target="alice",
        input_type=InputType.USERNAME,
        settings=Settings(),
        keys=KeyVault(),
        modules=["fake_check"],
        event_sink=sink,
    )
    report = asyncio.run(inv.run())

    assert report["target"] == "alice"
    assert report["found_accounts"] == 1
    kinds = {e["type"] for e in events}
    assert {"investigation_start", "module_start", "module_done", "investigation_done"} <= kinds
    md = [e for e in events if e["type"] == "module_done"][0]
    assert md["module"] == "fake_check"
    assert md["findings"] == 1


def test_investigation_persists(tmp_path: Path, monkeypatch) -> None:
    def fake_discover():
        return {"fake_check": FakeModule}

    monkeypatch.setattr("one_osint.orchestrator.engine.discover_modules", fake_discover)

    storage = Storage(tmp_path / "inv.sqlite3")
    inv = Investigation(
        target="bob",
        input_type=InputType.USERNAME,
        settings=Settings(),
        keys=KeyVault(),
        modules=["fake_check"],
        storage=storage,
    )
    asyncio.run(inv.run())
    rows = storage.list_investigations()
    assert len(rows) == 1
    assert rows[0]["status"] == "done"
    runs = storage.get_module_runs(rows[0]["id"])
    assert runs[0]["module"] == "fake_check"
    assert "fake_finding" in storage.get_investigation(rows[0]["id"])["report_json"]


@pytest.fixture()
def client(monkeypatch, tmp_path: Path) -> TestClient:
    def fake_discover():
        return {"fake_check": FakeModule}

    monkeypatch.setattr("one_osint.api.server.discover_modules", fake_discover)
    monkeypatch.setattr(
        "one_osint.api.server.run_investigation",
        _fake_run_investigation,
    )
    monkeypatch.setattr("one_osint.api.server.Storage", lambda: Storage(tmp_path / "api.sqlite3"))
    return TestClient(app)


async def _fake_run_investigation(*args, **kwargs):
    target = args[0] if args else kwargs.get("target", "?")
    res = ModuleResult(name="fake_check")
    res.findings.append(Finding("fake_finding", "https://fake/alice", extra={"k": "v"}))
    return {
        "target": target,
        "input_type": "username",
        "modules": [res.to_dict()],
        "found_accounts": 1,
        "module_count": 1,
        "pivots": {"emails": [], "usernames": [], "domains": [], "phones": []},
    }


def test_api_health_and_modules(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "version": "0.1.0"}
    mods = client.get("/api/modules").json()
    assert any(m["name"] == "fake_check" for m in mods)


def test_api_investigation_flow(client: TestClient, tmp_path: Path) -> None:
    # sync path: health/modules/keys only (background task needs a live loop)
    r = client.post(
        "/api/investigate",
        json={"target": "alice", "modules": ["fake_check"], "allow_loud": True},
    )
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_api_investigation_async_flow(monkeypatch, tmp_path: Path) -> None:
    """Full flow with ASGITransport so the background worker actually runs."""
    import httpx

    def fake_discover():
        return {"fake_check": FakeModule}

    monkeypatch.setattr("one_osint.api.server.discover_modules", fake_discover)
    monkeypatch.setattr("one_osint.api.server.run_investigation", _fake_run_investigation)
    monkeypatch.setattr(
        "one_osint.api.server.Storage", lambda: Storage(tmp_path / "api2.sqlite3")
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/investigate",
            json={"target": "alice", "modules": ["fake_check"]},
        )
        assert r.status_code == 202
        inv_id = r.json()["investigation_id"]

        report = None
        for _ in range(100):
            await asyncio.sleep(0.1)
            rep = (await ac.get(f"/api/report/{inv_id}")).json()
            if "found_accounts" in rep:
                report = rep
                break
        assert report is not None
        assert report["found_accounts"] == 1

        export = await ac.get(f"/api/report/{inv_id}/export?format=md")
        assert export.status_code == 200
        assert "fake_finding" in export.text

        listed = (await ac.get("/api/investigations")).json()
        assert any(i["id"] == inv_id for i in listed)
        deleted = (await ac.delete(f"/api/investigation/{inv_id}")).json()
        assert deleted["deleted"] is True


def test_api_rejects_unknown_target(client: TestClient) -> None:
    r = client.post("/api/investigate", json={"target": "!!!", "modules": None})
    assert r.status_code == 400


def test_webui_served(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "one-osint" in r.text
    import re

    assets = re.findall(r"/static/assets/[^\"']+", r.text)
    assert assets, "built web UI must reference hashed assets under /static/assets/"
    for path in assets:
        assert client.get(path).status_code == 200
