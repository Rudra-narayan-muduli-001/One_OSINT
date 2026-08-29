"""Tests for the core: input detection, storage, useragent."""

from __future__ import annotations

from pathlib import Path

from one_osint.core.detect import (
    InputType,
    detect_input_type,
    domain_from_email,
    normalize_email,
    normalize_username,
)
from one_osint.core.storage import Storage
from one_osint.core.useragent import random_user_agent


class TestDetect:
    def test_email(self) -> None:
        assert detect_input_type("foo.bar@example.com") is InputType.EMAIL
        assert detect_input_type("FOO+tag@sub.example.co.uk") is InputType.EMAIL

    def test_username(self) -> None:
        assert detect_input_type("alice_42") is InputType.USERNAME
        assert detect_input_type("torvalds") is InputType.USERNAME

    def test_phone(self) -> None:
        assert detect_input_type("+33612345678") is InputType.PHONE
        assert detect_input_type("+1 202 555 0123") is InputType.PHONE

    def test_domain(self) -> None:
        assert detect_input_type("example.com") is InputType.DOMAIN
        assert detect_input_type("sub.example.co.uk") is InputType.DOMAIN

    def test_ip(self) -> None:
        assert detect_input_type("8.8.8.8") is InputType.IP
        assert detect_input_type("2001:db8::1") is InputType.IP

    def test_unknown(self) -> None:
        assert detect_input_type("") is InputType.UNKNOWN
        assert detect_input_type("hello world!!!") is InputType.UNKNOWN

    def test_normalize(self) -> None:
        assert normalize_email("  Foo@Bar.com ") == "foo@bar.com"
        assert normalize_username("  alice ") == "alice"
        assert domain_from_email("x@Sub.Example.COM") == "sub.example.com"


class TestStorage:
    def test_roundtrip(self, tmp_path: Path) -> None:
        s = Storage(tmp_path / "test.sqlite3")
        inv_id = s.create_investigation("alice@example.com", "email")
        assert inv_id
        row = s.get_investigation(inv_id)
        assert row and row["status"] == "running"

        s.save_module_run(inv_id, "email_enumeration", "done", 0.5, {"x": 1})
        runs = s.get_module_runs(inv_id)
        assert len(runs) == 1
        assert runs[0]["module"] == "email_enumeration"
        assert runs[0]["result"] == {"x": 1}

        s.update_investigation(inv_id, "done", {"target": "alice@example.com"})
        row = s.get_investigation(inv_id)
        assert row and row["status"] == "done"
        assert "report_json" in row and row["report_json"]

        listed = s.list_investigations()
        assert listed and listed[0]["id"] == inv_id
        assert s.delete_investigation(inv_id) is True
        assert s.get_investigation(inv_id) is None


class TestUseragent:
    def test_random_ua(self) -> None:
        ua = random_user_agent()
        assert ua.startswith("Mozilla/5.0")
        assert "(" in ua
