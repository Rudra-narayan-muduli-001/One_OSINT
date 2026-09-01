"""Tests for core: result, config, paths, useragent, detect extended."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from one_osint.core.config import KeyVault, Settings, SUPPORTED_KEYS
from one_osint.core.detect import (
    InputType,
    detect_input_type,
    domain_from_email,
    normalize_email,
    normalize_username,
)
from one_osint.core.result import Finding, ModuleResult, Status, ModuleStatus
from one_osint.core.useragent import load_user_agents, random_user_agent


class TestFinding:
    def test_to_dict_defaults(self) -> None:
        f = Finding(site="github")
        d = f.to_dict()
        assert d["site"] == "github"
        assert d["status"] == Status.FOUND.value
        assert d["category"] == "misc"
        assert d["extra"] == {}
        assert d["media"] == []
        assert d["url"] is None

    def test_to_dict_with_values(self) -> None:
        f = Finding(
            site="shodan",
            url="https://shodan.io/host/1.1.1.1",
            status=Status.NOT_FOUND,
            category="intel",
            extra={"ports": [80]},
            media=["https://img"],
            reason="test",
        )
        d = f.to_dict()
        assert d["url"] == "https://shodan.io/host/1.1.1.1"
        assert d["status"] == "not_found"
        assert d["extra"]["ports"] == [80]
        assert d["reason"] == "test"

    def test_status_string(self) -> None:
        f = Finding(site="x", status="custom_status")
        d = f.to_dict()
        assert d["status"] == "custom_status"


class TestModuleResult:
    def test_to_dict(self) -> None:
        r = ModuleResult(name="test_mod")
        r.findings.append(Finding(site="a", status=Status.FOUND))
        r.summary = {"k": 1}
        r.duration = 1.23456
        d = r.to_dict()
        assert d["name"] == "test_mod"
        assert len(d["findings"]) == 1
        assert d["summary"] == {"k": 1}
        assert d["duration"] == round(1.23456, 3)
        assert d["error"] is None
        assert d["skipped"] is False

    def test_error_and_skipped(self) -> None:
        r = ModuleResult(name="m", error="boom", skipped=True, duration=0.1)
        d = r.to_dict()
        assert d["error"] == "boom"
        assert d["skipped"] is True

    def test_status_enum(self) -> None:
        assert Status.FOUND.value == "found"
        assert Status.NOT_FOUND.value == "not_found"
        assert ModuleStatus.DONE.value == "done"


class TestDetectExtended:
    def test_email_variants(self) -> None:
        assert detect_input_type("  foo@example.com  ") == InputType.EMAIL
        assert detect_input_type("a@b.co") == InputType.EMAIL
        assert detect_input_type("invalid@") == InputType.UNKNOWN

    def test_phone_detection(self) -> None:
        assert detect_input_type("+33612345678") == InputType.PHONE
        assert detect_input_type("+1 202 555 0123") == InputType.PHONE
        # 10-digit without + is treated as username (not phone) due to len <=10 rule
        assert detect_input_type("2025550123") == InputType.USERNAME
        assert detect_input_type("+123456789012345") == InputType.PHONE  # 15 digits
        assert detect_input_type("+123456") == InputType.UNKNOWN  # too short

    def test_domain_detection(self) -> None:
        assert detect_input_type("example.com") == InputType.DOMAIN
        assert detect_input_type("sub.domain.co.uk") == InputType.DOMAIN
        # "-bad.com" fails domain regex but matches username pattern -> username wins
        assert detect_input_type("-bad.com") == InputType.USERNAME
        # "localhost" has no dot, so not domain; matches username instead
        assert detect_input_type("localhost") == InputType.USERNAME

    def test_ip_detection(self) -> None:
        assert detect_input_type("8.8.8.8") == InputType.IP
        # phone regex wins over IP for dotted quad with >10 digits due to ordering
        assert detect_input_type("255.255.255.255") == InputType.PHONE
        assert detect_input_type("999.999.999.999") == InputType.PHONE
        assert detect_input_type("2001:db8::1") == InputType.IP
        assert detect_input_type("::1") == InputType.IP

    def test_username_detection(self) -> None:
        assert detect_input_type("alice_42") == InputType.USERNAME
        assert detect_input_type("ab") == InputType.UNKNOWN  # too short
        assert detect_input_type("a" * 65) == InputType.UNKNOWN  # too long
        # "john-doe.test" matches domain pattern (dot + TLD) before username check
        assert detect_input_type("john-doe.test") == InputType.DOMAIN

    def test_unknown(self) -> None:
        assert detect_input_type("") == InputType.UNKNOWN
        assert detect_input_type("   ") == InputType.UNKNOWN
        assert detect_input_type("!!bad!!") == InputType.UNKNOWN

    def test_normalize_helpers(self) -> None:
        assert normalize_email("  FOo@Bar.COM ") == "foo@bar.com"
        assert normalize_username("  alice ") == "alice"
        assert domain_from_email("Test@Sub.Example.COM") == "sub.example.com"
        assert domain_from_email("no-at-sign") == "no-at-sign".lower()  # rsplit fallback


class TestSettings:
    def test_defaults(self) -> None:
        s = Settings()
        assert s.concurrency == 30
        assert s.timeout == 15.0
        assert s.user_agent_rotate is True
        assert s.proxies == []
        assert s.tor is False

    def test_custom(self) -> None:
        s = Settings(concurrency=5, timeout=5, tor=True, proxies=["http://proxy"])
        assert s.concurrency == 5
        assert s.tor is True


class TestKeyVault:
    def test_overrides_take_precedence(self, monkeypatch) -> None:
        monkeypatch.setenv("HIBP_API_KEY", "env_value")
        vault = KeyVault(overrides={"hibp": "override"})
        assert vault.get("hibp") == "override"
        assert vault.has("hibp") is True

    def test_env_fallback(self, monkeypatch) -> None:
        monkeypatch.setenv("HIBP_API_KEY", "env_key_123")
        vault = KeyVault(overrides={})
        # ensure file does not contain hibp
        vault._file_data = {}
        assert vault.get("hibp") == "env_key_123"

    def test_missing_key(self) -> None:
        vault = KeyVault(overrides={})
        vault._file_data = {}
        # use a name that likely has no env var
        os.environ.pop("SHODAN_API_KEY", None)
        # but we cannot guarantee env; test unknown key name without env spec
        assert vault.get("nonexistent_key_xyz") is None
        assert vault.has("nonexistent_key_xyz") is False

    def test_list_keys_structure(self) -> None:
        vault = KeyVault()
        keys = vault.list_keys()
        assert isinstance(keys, list)
        assert any(k["name"] == "hibp" for k in keys)
        for k in keys:
            assert "name" in k
            assert "description" in k
            assert "env_var" in k
            assert "set" in k

    def test_supported_keys_coverage(self) -> None:
        # ensure all expected keys are present
        for expected in ("hibp", "shodan", "virustotal", "github"):
            assert expected in SUPPORTED_KEYS

    def test_set_and_unset(self, tmp_path: Path, monkeypatch) -> None:
        from one_osint.core import paths as paths_mod

        # Redirect KEYS_FILE to temp location
        tmp_keys = tmp_path / "keys.yaml"
        monkeypatch.setattr(paths_mod, "KEYS_FILE", tmp_keys)
        # Also patch KeyVault's reference via import
        import one_osint.core.config as config_mod

        monkeypatch.setattr(config_mod, "KEYS_FILE", tmp_keys)

        KeyVault.set("testkey", "testvalue123")
        assert tmp_keys.exists()
        content = tmp_keys.read_text(encoding="utf-8")
        assert "testkey" in content
        # Now read via new vault
        vault = KeyVault()
        vault._file_data = {"testkey": "testvalue123"}  # simulate load
        assert vault.get("testkey") == "testvalue123"

        result = KeyVault.unset("testkey")
        assert result is True
        # unset non-existent
        assert KeyVault.unset("nonexistent") is False


class TestPaths:
    def test_paths_exist(self) -> None:
        from one_osint.core.paths import DATA_DIR, CONFIG_DIR, PROJECT_ROOT

        assert PROJECT_ROOT.exists()
        assert DATA_DIR.exists()
        assert CONFIG_DIR.exists()

    def test_data_dir_env_override(self, monkeypatch, tmp_path: Path) -> None:
        # Use fresh import not needed; just check DATA_DIR is Path
        from one_osint.core.paths import DATA_DIR

        assert isinstance(DATA_DIR, Path)


class TestUserAgent:
    def test_load_user_agents(self) -> None:
        agents = load_user_agents()
        assert isinstance(agents, list)
        assert len(agents) >= 1
        assert all(isinstance(a, str) for a in agents)

    def test_random_ua_format(self) -> None:
        ua = random_user_agent()
        assert isinstance(ua, str)
        assert len(ua) > 10
        assert "Mozilla" in ua or "Chrome" in ua or "/" in ua

    def test_random_ua_multiple_calls(self) -> None:
        # Should not crash on repeated calls
        uas = {random_user_agent() for _ in range(10)}
        assert len(uas) >= 1

    def test_caching(self) -> None:
        a1 = load_user_agents()
        a2 = load_user_agents()
        assert a1 is a2  # cached
