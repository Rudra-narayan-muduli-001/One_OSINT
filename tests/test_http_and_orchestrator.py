"""Tests for http client, orchestrator engine, runner, storage extended."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from one_osint.core.config import KeyVault, Settings
from one_osint.core.detect import InputType
from one_osint.core.http_client import Response, get, post, request
from one_osint.core.result import Finding, ModuleResult, Status
from one_osint.core.storage import Storage
from one_osint.modules.base import BaseModule
from one_osint.orchestrator.engine import Investigation, _collect_field
from one_osint.orchestrator.runner import run_investigation


class TestResponse:
    def test_ok_property(self) -> None:
        assert Response(200, "ok", {}, "").ok is True
        assert Response(301, "", {}, "").ok is True
        assert Response(404, "", {}, "").ok is False
        assert Response(500, "", {}, "").ok is False

    def test_json(self) -> None:
        r = Response(200, '{"a": 1}', {}, "")
        assert r.json() == {"a": 1}

    def test_json_invalid(self) -> None:
        r = Response(200, "not json", {}, "")
        with pytest.raises(json.JSONDecodeError):
            r.json()

    def test_contains_string(self) -> None:
        r = Response(200, "hello world", {}, "")
        assert r.contains("world") is True
        assert r.contains("missing") is False

    def test_contains_list(self) -> None:
        r = Response(200, "hello world", {}, "")
        assert r.contains(["world", "other"]) is True
        assert r.contains(["nope", "missing"]) is False


class TestHttpClient:
    @pytest.mark.asyncio
    async def test_get_post_wiring(self, monkeypatch) -> None:
        async def fake_request(method, url, **kwargs):
            return Response(200, f"{method}:{url}", {}, url)

        monkeypatch.setattr("one_osint.core.http_client.request", fake_request)
        r = await get("https://example.com")
        assert r.text == "GET:https://example.com"
        r2 = await post("https://example.com", json={"a": 1})
        assert r2.text.startswith("POST")

    @pytest.mark.asyncio
    async def test_user_agent_rotation(self, monkeypatch) -> None:
        monkeypatch.setattr("one_osint.core.http_client.random_user_agent", lambda: "TestUA/1.0")

        async def fake_request(method, url, **kwargs):
            headers = kwargs.get("headers", {})
            return Response(200, "ok", {"User-Agent": headers.get("User-Agent", "")}, url)

        monkeypatch.setattr("one_osint.core.http_client.request", fake_request)
        resp = await get("https://example.com", settings=Settings(user_agent_rotate=True))
        assert resp.headers.get("User-Agent") == "TestUA/1.0"

    @pytest.mark.asyncio
    async def test_proxy_selection(self, monkeypatch) -> None:
        async def fake_request(method, url, **kwargs):
            proxy = kwargs.get("proxy")
            return Response(200, proxy or "none", {}, url)

        monkeypatch.setattr("one_osint.core.http_client.request", fake_request)
        
        # Test tor proxy
        r = await get("https://example.com", settings=Settings(tor=True))
        assert "socks5h://127.0.0.1:9050" in r.text
        
        # Test static proxy
        r = await get("https://example.com", settings=Settings(proxies=["http://p1", "http://p2"], proxy_rotate=False))
        assert "http://p1" in r.text

    @pytest.mark.asyncio
    async def test_request_with_httpx_error(self, monkeypatch) -> None:
        import httpx

        async def fake_request(method, url, **kwargs):
            raise httpx.HTTPError("network down")

        monkeypatch.setattr("one_osint.core.http_client.request", fake_request)
        with pytest.raises(RuntimeError, match="HTTP GET"):
            await get("https://example.com")


class TestStorageExtended:
    def test_create_and_get(self, tmp_path: Path) -> None:
        s = Storage(tmp_path / "test.db")
        inv_id = s.create_investigation("alice@example.com", "email")
        row = s.get_investigation(inv_id)
        assert row is not None
        assert row["target"] == "alice@example.com"
        assert row["input_type"] == "email"
        assert row["status"] == "running"

    def test_list_limit(self, tmp_path: Path) -> None:
        s = Storage(tmp_path / "test.db")
        for i in range(5):
            s.create_investigation(f"user{i}", "username")
        listed = s.list_investigations(limit=2)
        assert len(listed) == 2

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        s = Storage(tmp_path / "test.db")
        assert s.delete_investigation("nonexistent") is False

    def test_module_runs_and_update(self, tmp_path: Path) -> None:
        s = Storage(tmp_path / "test.db")
        inv_id = s.create_investigation("bob", "username")
        s.save_module_run(inv_id, "mod_a", "done", 0.1, {"x": 1})
        runs = s.get_module_runs(inv_id)
        assert runs[0]["module"] == "mod_a"
        assert runs[0]["result"] == {"x": 1}

        s.update_investigation(inv_id, "done", {"final": True})
        row = s.get_investigation(inv_id)
        assert row["status"] == "done"
        assert "final" in row["report"]

        s.update_investigation(inv_id, "error")
        row = s.get_investigation(inv_id)
        assert row["status"] == "error"

    def test_get_missing_investigation(self, tmp_path: Path) -> None:
        s = Storage(tmp_path / "missing.db")
        assert s.get_investigation("doesnotexist") is None
        assert s.get_module_runs("doesnotexist") == []


class FakeModule(BaseModule):
    name = "fake_mod"
    description = "fake for testing"
    input_types = ("email", "username")

    async def check(self, target: str) -> ModuleResult:
        res = ModuleResult(name=self.name)
        res.findings.append(Finding(site="fake", url=f"https://example.com/{target}"))
        res.summary = {"target": target}
        return res


class ErrorModule(BaseModule):
    name = "error_mod"
    description = "always errors"
    input_types = ("email",)

    async def check(self, target: str) -> ModuleResult:
        raise ValueError("boom")


class SkippedModule(BaseModule):
    name = "skipped_mod"
    description = "skipped"
    input_types = ("email",)
    opt_in = True

    async def check(self, target: str) -> ModuleResult:
        res = ModuleResult(name=self.name, skipped=True)
        return res


class TestCollectField:
    def test_collect(self) -> None:
        r = ModuleResult(name="x")
        r.findings.append(Finding(site="s", extra={"emails": "a@b.com"}))
        r.findings.append(Finding(site="s2", extra={"emails": "A@B.COM"}))  # should dedup lowercased
        r.findings.append(Finding(site="s3", extra={"domains": "example.com"}))
        out = _collect_field([r], "emails")
        assert out == ["a@b.com"]
        out2 = _collect_field([r], "domains")
        assert out2 == ["example.com"]

    def test_collect_ignores_non_string(self) -> None:
        r = ModuleResult(name="x")
        r.findings.append(Finding(site="s", extra={"emails": ["a@b.com"]}))  # list not string
        assert _collect_field([r], "emails") == []


class TestInvestigation:
    def _make_inv(self, tmp_path: Path | None = None, modules=None, monkeypatch=None):
        from unittest.mock import MagicMock

        def fake_discover():
            return {"fake_mod": FakeModule, "error_mod": ErrorModule, "skipped_mod": SkippedModule}

        if monkeypatch:
            monkeypatch.setattr("one_osint.orchestrator.engine.discover_modules", fake_discover)
            monkeypatch.setattr("one_osint.orchestrator.engine.get_modules_for", lambda *a, **kw: [FakeModule()])
        storage = Storage(tmp_path / "inv.db") if tmp_path else None
        return Investigation(
            target="alice@example.com",
            input_type=InputType.EMAIL,
            settings=Settings(concurrency=5, timeout=5),
            keys=KeyVault(),
            modules=modules or ["fake_mod"],
            storage=storage,
        )

    def test_build_report(self, tmp_path: Path, monkeypatch) -> None:
        inv = self._make_inv(tmp_path, monkeypatch=monkeypatch)
        res = ModuleResult(name="fake_mod")
        res.findings.append(Finding(site="github", status=Status.FOUND))
        res.findings.append(Finding(site="twitter", status=Status.NOT_FOUND))
        inv.results = [res]
        inv.pivots = {"emails": [], "usernames": [], "domains": [], "phones": []}
        report = inv.build_report()
        assert report["target"] == "alice@example.com"
        assert report["found_accounts"] == 1
        assert report["module_count"] == 1
        assert report["modules"][0]["name"] == "fake_mod"

    def test_run_with_fake_module(self, tmp_path: Path, monkeypatch) -> None:
        inv = self._make_inv(tmp_path, monkeypatch=monkeypatch)
        events = []

        async def sink(ev: dict) -> None:
            events.append(ev)

        inv.event_sink = sink
        report = asyncio.run(inv.run())
        assert report["target"] == "alice@example.com"
        assert report["found_accounts"] == 1
        assert any(e["type"] == "investigation_start" for e in events)
        assert any(e["type"] == "module_done" for e in events)
        assert any(e["type"] == "investigation_done" for e in events)

    def test_run_handles_module_error(self, tmp_path: Path, monkeypatch) -> None:
        def fake_discover():
            return {"error_mod": ErrorModule}

        monkeypatch.setattr("one_osint.orchestrator.engine.discover_modules", fake_discover)
        inv = Investigation(
            target="alice@example.com",
            input_type=InputType.EMAIL,
            settings=Settings(),
            keys=KeyVault(),
            modules=["error_mod"],
        )
        report = asyncio.run(inv.run())
        assert report["module_count"] == 1
        assert report["modules"][0]["error"] == "boom"

    def test_build_pipeline_with_filter(self, monkeypatch) -> None:
        def fake_discover():
            return {"fake_mod": FakeModule, "error_mod": ErrorModule}

        monkeypatch.setattr("one_osint.orchestrator.engine.discover_modules", fake_discover)
        inv = Investigation(
            target="x", input_type=InputType.EMAIL, settings=Settings(), keys=KeyVault(), modules=["fake_mod"]
        )
        pipeline = inv._build_pipeline()
        assert len(pipeline) == 1
        assert pipeline[0].name == "fake_mod"

    def test_pivots_collected(self, tmp_path: Path, monkeypatch) -> None:
        class PivotMod(BaseModule):
            name = "pivot_mod"
            input_types = ("email",)

            async def check(self, target: str) -> ModuleResult:
                r = ModuleResult(name=self.name)
                r.findings.append(Finding(site="dns", extra={"emails": "pivot@example.com", "domains": "example.com"}))
                return r

        def fake_discover():
            return {"pivot_mod": PivotMod}

        monkeypatch.setattr("one_osint.orchestrator.engine.discover_modules", fake_discover)
        inv = Investigation(
            target="alice@example.com",
            input_type=InputType.EMAIL,
            settings=Settings(),
            keys=KeyVault(),
            modules=["pivot_mod"],
        )
        report = asyncio.run(inv.run())
        assert "pivot@example.com" in report["pivots"]["emails"]
        assert "example.com" in report["pivots"]["domains"]


class TestRunner:
    @pytest.mark.asyncio
    async def test_run_investigation_wrapper(self, monkeypatch, tmp_path: Path) -> None:
        def fake_discover():
            return {"fake_mod": FakeModule}

        monkeypatch.setattr("one_osint.orchestrator.engine.discover_modules", fake_discover)
        report = await run_investigation("alice", settings=Settings(), keys=KeyVault(), modules=["fake_mod"])
        assert report["target"] == "alice"
        assert report["found_accounts"] == 1

    @pytest.mark.asyncio
    async def test_run_investigation_detects_ip(self, monkeypatch) -> None:
        def fake_discover():
            return {"fake_mod": FakeModule}

        monkeypatch.setattr("one_osint.orchestrator.engine.discover_modules", fake_discover)
        report = await run_investigation("8.8.8.8", settings=Settings(), keys=KeyVault(), modules=["fake_mod"])
        assert report["input_type"] == "ip"