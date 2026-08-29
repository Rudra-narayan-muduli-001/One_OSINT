"""Tests for the WhatsMyName username engine (dual-marker logic)."""

from __future__ import annotations

import asyncio

from one_osint.modules.username.wmn_engine import (
    WmnChecker,
    WmnSite,
    _match,
)


class TestMatch:
    def test_code_match(self) -> None:
        assert _match(200, 200, "x", None) is True
        assert _match(200, 404, "x", None) is False

    def test_string_match(self) -> None:
        assert _match(200, None, "hello world", "world") is True
        assert _match(200, None, "hello world", "planet") is False

    def test_code_and_string(self) -> None:
        assert _match(200, 200, "hello", "hell") is True
        assert _match(200, 200, "hello", "nope") is False
        assert _match(404, 200, "hello", "hell") is False


class _Resp:
    def __init__(self, status: int, text: str):
        self.status_code = status
        self.text = text


class _MiniChecker(WmnChecker):
    """Checker with a fixed tiny site list (skips loading the dataset)."""

    def __init__(self, http, sites: list[WmnSite]):
        self.http = http
        self.sem = asyncio.Semaphore(4)
        self.sites = sites


class TestWmnChecker:
    def _http(self, status_by_url: dict[str, tuple[int, str]]):
        class Fake:
            def __init__(self):
                self.status_by_url = status_by_url

            async def get(self, url: str, **kwargs):
                status, text = self.status_by_url.get(url, (404, ""))
                return _Resp(status, text)

            async def post(self, url: str, **kwargs):
                status, text = self.status_by_url.get(url, (404, ""))
                return _Resp(status, text)

            async def aclose(self):
                pass

        return Fake()

    def _mk_site(self, name: str, uri: str, **kw) -> WmnSite:
        return WmnSite(name=name, uri_check=uri, **kw)

    def _run(self, http, sites: list[WmnSite], username: str = "alice"):
        return asyncio.run(_MiniChecker(http, sites).check_username(username))

    def test_found_when_both_markers(self) -> None:
        site = self._mk_site("GitHub", "https://github.com/{account}",
                             e_code=200, e_string="github")
        http = self._http({"https://github.com/alice": (200, "this is github alice")})
        hits = self._run(http, [site])
        assert [h.site for h in hits] == ["GitHub"]

    def test_negative_marker_wins(self) -> None:
        site = self._mk_site("SiteX", "https://x.com/{account}",
                             e_code=200, e_string="found",
                             m_string="account not found")
        http = self._http({"https://x.com/alice": (200, "found but account not found")})
        hits = self._run(http, [site])
        assert hits == []

    def test_negative_status_wins(self) -> None:
        site = self._mk_site("SiteX2", "https://x2.com/{account}",
                             e_code=200, e_string="found",
                             m_code=404)
        http = self._http({"https://x2.com/alice": (404, "not found")})
        hits = self._run(http, [site])
        assert hits == []

    def test_code_mismatch(self) -> None:
        site = self._mk_site("SiteY", "https://y.com/{account}", e_code=200)
        http = self._http({"https://y.com/alice": (404, "")})
        hits = self._run(http, [site])
        assert hits == []

    def test_invalid_site_skipped(self) -> None:
        site = self._mk_site("SiteZ", "https://z.com/{account}", valid=False)
        hits = self._run(None, [site])
        assert hits == []

    def test_sanitize(self) -> None:
        site = self._mk_site("SiteS", "https://s.com/{account}", strip_bad_char="@")
        assert site.sanitize("@ali@ce") == "alice"
