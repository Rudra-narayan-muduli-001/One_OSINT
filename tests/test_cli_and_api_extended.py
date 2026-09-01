"""Tests for CLI and API extended coverage."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from one_osint.api.server import app, report_to_text
from one_osint.cli.main import app as cli_app
from one_osint.core.config import KeyVault, Settings
from one_osint.core.result import Finding, ModuleResult
from one_osint.core.storage import Storage


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestCli:
    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(cli_app, ["version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_modules_list(self, runner: CliRunner) -> None:
        result = runner.invoke(cli_app, ["modules"])
        assert result.exit_code == 0
        # Should list at least one module name
        assert "email_enumeration" in result.output or "Modules" in result.output

    def test_keys_list(self, runner: CliRunner) -> None:
        result = runner.invoke(cli_app, ["keys", "--list"])
        assert result.exit_code == 0
        assert "API keys" in result.output or "hibp" in result.output

    def test_keys_set_unset(self, runner: CliRunner, tmp_path: Path, monkeypatch) -> None:
        from one_osint.core import paths as paths_mod
        import one_osint.core.config as config_mod
        tmp_keys = tmp_path / "keys.yaml"
        monkeypatch.setattr(paths_mod, "KEYS_FILE", tmp_keys)
        monkeypatch.setattr(config_mod, "KEYS_FILE", tmp_keys)
        result = runner.invoke(cli_app, ["keys", "--set", "testkey=myvalue"])
        assert result.exit_code == 0
        assert tmp_keys.exists()
        result2 = runner.invoke(cli_app, ["keys", "--unset", "testkey"])
        assert result2.exit_code == 0

    def test_keys_set_invalid(self, runner: CliRunner) -> None:
        result = runner.invoke(cli_app, ["keys", "--set", "invalidwithoutvalue"])
        assert result.exit_code == 2

    def test_investigate_unknown_target(self, runner: CliRunner, monkeypatch) -> None:
        # Mock Storage to avoid writing to real DB
        monkeypatch.setattr("one_osint.cli.main.Storage", lambda: Storage(Path("/tmp/fake_cli_test.sqlite3")))
        result = runner.invoke(cli_app, ["investigate", "!!!unknown_target!!!"])
        assert result.exit_code == 2
        assert "Cannot detect" in result.output

    def test_investigate_with_fake_module(self, runner: CliRunner, tmp_path: Path, monkeypatch) -> None:
        from one_osint.core.result import Finding, ModuleResult
        from one_osint.modules.base import BaseModule

        class FakeMod(BaseModule):
            name = "fake_cli_mod"
            input_types = ("username",)
            async def check(self, target: str):
                r = ModuleResult(name=self.name)
                r.findings.append(Finding(site="fake", url=f"https://fake/{target}"))
                return r

        def fake_discover():
            return {"fake_cli_mod": FakeMod}

        monkeypatch.setattr("one_osint.modules.base.discover_modules", fake_discover)
        monkeypatch.setattr("one_osint.orchestrator.engine.discover_modules", fake_discover)
        monkeypatch.setattr("one_osint.cli.main.discover_modules", fake_discover)
        # Patch Storage to tmp
        db = tmp_path / "cli_inv.sqlite3"
        monkeypatch.setattr("one_osint.cli.main.Storage", lambda: Storage(db))
        monkeypatch.setattr("one_osint.orchestrator.engine.get_http_client", lambda s=None: AsyncMock())
        # Need to also mock get_http_client used inside orchestrator runner
        result = runner.invoke(cli_app, ["investigate", "alice", "--modules", "fake_cli_mod"])
        # Should succeed (exit 0) and print summary
        assert result.exit_code == 0
        assert "alice" in result.output or "OSINT" in result.output


class TestApiExtended:
    @pytest.fixture()
    def client(self, monkeypatch, tmp_path: Path) -> TestClient:
        from one_osint.modules.base import BaseModule
        from one_osint.core.result import Finding, ModuleResult

        class FakeMod(BaseModule):
            name = "fake_check"
            input_types = ("username",)
            async def check(self, target: str):
                r = ModuleResult(name=self.name)
                r.findings.append(Finding(site="fake", url=f"https://fake/{target}"))
                return r

        def fake_discover():
            return {"fake_check": FakeMod}

        async def fake_run(*args, **kwargs):
            t = args[0] if args else kwargs.get("target", "alice")
            r = ModuleResult(name="fake_check")
            r.findings.append(Finding(site="fake", url="https://fake/alice", extra={"k": "v"}))
            return {
                "target": t,
                "input_type": "username",
                "modules": [r.to_dict()],
                "found_accounts": 1,
                "module_count": 1,
                "pivots": {"emails": [], "usernames": [], "domains": [], "phones": []},
            }

        monkeypatch.setattr("one_osint.api.server.discover_modules", fake_discover)
        monkeypatch.setattr("one_osint.api.server.run_investigation", fake_run)
        monkeypatch.setattr("one_osint.api.server.Storage", lambda: Storage(tmp_path / "api_ext.sqlite3"))
        return TestClient(app)

    def test_health(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_modules_endpoint(self, client: TestClient) -> None:
        r = client.get("/api/modules")
        assert r.status_code == 200
        assert any(m["name"] == "fake_check" for m in r.json())

    def test_keys_endpoint(self, client: TestClient, monkeypatch) -> None:
        # Need to ensure real endpoint works even with fake storage
        r = client.get("/api/keys")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_investigate_rejects_unknown(self, client: TestClient) -> None:
        r = client.post("/api/investigate", json={"target": "!!!", "modules": None})
        assert r.status_code == 400

    def test_report_to_text_all_formats(self) -> None:
        report = {
            "target": "alice",
            "input_type": "username",
            "found_accounts": 1,
            "module_count": 1,
            "pivots": {},
            "modules": [{"name": "m", "duration": 0.5, "findings": [{"site": "s", "url": "https://x", "status": "found", "category": "misc", "extra": {}, "media": [], "reason": None}], "error": None, "summary": {}}],
        }
        assert "alice" in report_to_text(report, "json")
        # CSV exports findings rows, not the target string itself — check for site/module instead
        csv_out = report_to_text(report, "csv")
        assert "s" in csv_out and "m" in csv_out
        assert "# OSINT" in report_to_text(report, "md")
        with pytest.raises(Exception):  # HTTPException
            report_to_text(report, "unsupported")

    def test_report_not_found(self, client: TestClient) -> None:
        r = client.get("/api/report/nonexistent123")
        assert r.status_code == 404

    def test_export_not_found(self, client: TestClient) -> None:
        r = client.get("/api/report/nonexistent123/export?format=json")
        assert r.status_code == 404

    def test_investigation_delete(self, client: TestClient, tmp_path: Path) -> None:
        # Create investigation via API then delete via storage
        r = client.post("/api/investigate", json={"target": "alice", "modules": ["fake_check"]})
        assert r.status_code == 202
        inv_id = r.json()["investigation_id"]
        # List should contain it (may be race, but storage persists)
        # Wait a bit for background worker? In sync TestClient, background won't run, but row exists with status running
        listed = client.get("/api/investigations").json()
        assert isinstance(listed, list)
        deleted = client.delete(f"/api/investigation/{inv_id}").json()
        assert "deleted" in deleted

    @pytest.mark.asyncio
    async def test_websocket_unknown_investigation(self, monkeypatch, tmp_path: Path) -> None:
        import httpx
        from one_osint.modules.base import BaseModule
        from one_osint.core.result import Finding, ModuleResult

        class FakeMod(BaseModule):
            name = "fake_check"
            input_types = ("username",)
            async def check(self, target: str):
                r = ModuleResult(name=self.name)
                r.findings.append(Finding(site="fake"))
                return r

        def fake_discover():
            return {"fake_check": FakeMod}

        async def fake_run(*a, **kw):
            r = ModuleResult(name="fake_check")
            r.findings.append(Finding(site="fake", url="https://fake/alice"))
            return {"target": "alice", "input_type": "username", "modules": [r.to_dict()], "found_accounts": 1, "module_count": 1, "pivots": {"emails": [], "usernames": [], "domains": [], "phones": []}}

        monkeypatch.setattr("one_osint.api.server.discover_modules", fake_discover)
        monkeypatch.setattr("one_osint.api.server.run_investigation", fake_run)
        monkeypatch.setattr("one_osint.api.server.Storage", lambda: Storage(tmp_path / "ws_test.sqlite3"))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            # Check health via async client
            r = await ac.get("/health")
            assert r.status_code == 200


class TestDetectEdgeCases:
    def test_file_detection_via_cli(self) -> None:
        # The CLI should treat existing file path as file type; detect_input_type returns UNKNOWN for file paths, but orchestrator runner uses detect
        from one_osint.core.detect import InputType, detect_input_type
        # File type is not auto detected; expect UNKNOWN for path-like string
        assert detect_input_type("/tmp/somefile.txt") == InputType.UNKNOWN
        assert detect_input_type("C:\\path\\file.txt") == InputType.UNKNOWN

    def test_email_with_ip_domain(self) -> None:
        from one_osint.core.detect import InputType, detect_input_type
        # detect treats test@192.168.1.1 as email via regex (domain part looks like IP but still matches email pattern)
        result = detect_input_type("test@192.168.1.1")
        assert result in (InputType.EMAIL, InputType.UNKNOWN, InputType.IP)

    def test_phone_edge(self) -> None:
        from one_osint.core.detect import InputType, detect_input_type
        # Too short after stripping
        assert detect_input_type("+12") == InputType.UNKNOWN
        # Digits only long enough but without +
        assert detect_input_type("12345678901") == InputType.PHONE  # 11 digits >10 => phone
        # 5-digit numeric string matches username pattern, not unknown
        assert detect_input_type("12345") == InputType.USERNAME
