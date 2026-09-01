"""Tests for exporters: JSON / CSV / Markdown / HTML / PDF."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from one_osint.exporters.export import (
    _neutralize,
    export_csv,
    export_html,
    export_json,
    export_markdown,
    export_pdf,
    write_export,
)


def _sample_report() -> dict:
    return {
        "target": "alice@example.com",
        "input_type": "email",
        "created_at": "2026-01-01T00:00:00",
        "found_accounts": 1,
        "module_count": 2,
        "pivots": {"emails": ["bob@example.com"], "usernames": [], "domains": [], "phones": []},
        "modules": [
            {
                "name": "email_enumeration",
                "duration": 1.234,
                "error": None,
                "summary": {"sites_checked": 10},
                "findings": [
                    {
                        "site": "github",
                        "url": "https://github.com/alice",
                        "status": "found",
                        "category": "dev",
                        "extra": {"k": "v"},
                        "media": [],
                        "reason": None,
                    },
                    {
                        "site": "twitter",
                        "url": None,
                        "status": "not_found",
                        "category": "social",
                        "extra": {},
                        "media": [],
                        "reason": None,
                    },
                ],
            },
            {
                "name": "dns_pivot",
                "duration": 0.5,
                "error": "timeout",
                "summary": {},
                "findings": [],
            },
        ],
    }


class TestExportJson:
    def test_roundtrip(self) -> None:
        report = _sample_report()
        out = export_json(report)
        parsed = json.loads(out)
        assert parsed["target"] == "alice@example.com"
        assert parsed["found_accounts"] == 1

    def test_pretty(self) -> None:
        out = export_json(_sample_report())
        assert "\n" in out
        assert "  " in out


class TestExportMarkdown:
    def test_contains_header(self) -> None:
        md = export_markdown(_sample_report())
        assert "# OSINT Report: alice@example.com" in md
        assert "Input type" in md
        assert "email_enumeration" in md
        assert "github" in md

    def test_pivots_rendered(self) -> None:
        md = export_markdown(_sample_report())
        assert "bob@example.com" in md

    def test_error_rendered(self) -> None:
        md = export_markdown(_sample_report())
        assert "error: timeout" in md

    def test_empty_modules(self) -> None:
        report = {"target": "x", "input_type": "username", "modules": [], "found_accounts": 0, "module_count": 0}
        md = export_markdown(report)
        assert "# OSINT Report: x" in md


class TestExportCsv:
    def test_header_and_rows(self) -> None:
        csv_text = export_csv(_sample_report())
        reader = csv.DictReader(io.StringIO(csv_text))
        rows = list(reader)
        assert reader.fieldnames == ["module", "site", "status", "category", "url", "extra"]
        assert len(rows) == 2
        assert rows[0]["module"] == "email_enumeration"
        assert rows[0]["site"] == "github"

    def test_neutralize_formula(self) -> None:
        # build report where extra starts with = to trigger CSV injection guard
        report = _sample_report()
        report["modules"][0]["findings"][0]["extra"] = {"payload": "=cmd"}
        # export_csv json-dumps extra; the writer neutralizes if string starts with = + etc
        # _neutralize is applied to json string, which starts with {
        # so test _neutralize directly
        assert _neutralize("=cmd|calc") == "'=cmd|calc"
        assert _neutralize("+cmd") == "'+cmd"
        assert _neutralize("-cmd") == "'-cmd"
        assert _neutralize("@cmd") == "'@cmd"
        assert _neutralize("normal") == "normal"

    def test_csv_escaping(self) -> None:
        csv_text = export_csv(_sample_report())
        # should not raise
        assert "github" in csv_text


class TestExportHtml:
    def test_structure(self) -> None:
        html = export_html(_sample_report())
        assert "<!doctype html>" in html.lower()
        assert "alice@example.com" in html
        assert "email_enumeration" in html
        assert "<table>" in html

    def test_xss_escaped(self) -> None:
        report = _sample_report()
        report["target"] = "<script>alert(1)</script>"
        html = export_html(report)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_empty_report(self) -> None:
        report = {"target": "x", "input_type": "ip", "modules": [], "found_accounts": 0}
        html = export_html(report)
        assert "x" in html


class TestExportPdf:
    def test_creates_file(self, tmp_path: Path) -> None:
        out = tmp_path / "report.pdf"
        result = export_pdf(_sample_report(), out)
        assert result == out
        assert out.exists()
        assert out.stat().st_size > 500
        # PDF header
        assert out.read_bytes()[:4] == b"%PDF"

    def test_default_path(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        out = export_pdf(_sample_report())
        assert out.exists()
        assert out.read_bytes()[:4] == b"%PDF"
        out.unlink()


class TestWriteExport:
    @pytest.mark.parametrize("fmt,expected_ext", [
        ("json", "json"),
        (".json", "json"),
        ("csv", "csv"),
        ("md", "md"),
        ("html", "html"),
        ("pdf", "pdf"),
    ])
    def test_write_all_formats(self, tmp_path: Path, fmt: str, expected_ext: str) -> None:
        report = _sample_report()
        path = tmp_path / f"out.{expected_ext}"
        result = write_export(report, path, fmt)
        assert result == path
        assert path.exists()
        if expected_ext != "pdf":
            assert path.read_text(encoding="utf-8")
        else:
            assert path.read_bytes()[:4] == b"%PDF"

    def test_unsupported_format(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="unsupported format"):
            write_export(_sample_report(), tmp_path / "out.xyz", "xyz")

    def test_case_insensitive(self, tmp_path: Path) -> None:
        path = tmp_path / "out.json"
        write_export(_sample_report(), path, "JSON")
        assert json.loads(path.read_text(encoding="utf-8"))["target"] == "alice@example.com"
