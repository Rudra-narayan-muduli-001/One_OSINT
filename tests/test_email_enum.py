"""Tests for the email enumeration engine (rule matching + engine logic)."""

from __future__ import annotations

from one_osint.modules.email.enum_engine import (
    EnumEngine,
    EnumSite,
    Rule,
)


class TestRule:
    def test_status_rule(self) -> None:
        assert Rule("status", 200).matches(200, "", None)
        assert not Rule("status", 200).matches(404, "", None)

    def test_string_rule(self) -> None:
        assert Rule("string", "not registered").matches(200, "email not registered", None)
        assert not Rule("string", "available").matches(200, "email already registered", None)

    def test_regex_rule(self) -> None:
        assert Rule("regex", r"error.?code[:=]\s*30").matches(200, "error code: 30", None)

    def test_json_rule_bool(self) -> None:
        assert Rule("json", True, "result").matches(200, "", {"result": True})
        assert not Rule("json", True, "result").matches(200, "", {"result": False})
        assert not Rule("json", True, "result").matches(200, "", {"other": 1})

    def test_json_rule_path(self) -> None:
        assert Rule("json", "used", "meta.error").matches(200, "", {"meta": {"error": "used"}})
        assert Rule("json", 404, "meta.status").matches(200, "", {"meta": {"status": 404}})
        assert not Rule("json", 404, "meta.status").matches(200, "", {"meta": {"status": 200}})
        assert not Rule("json", 1, "list.5").matches(200, "", {"list": [1]})

    def test_json_rule_bad_payload(self) -> None:
        assert not Rule("json", True, "result").matches(200, "not json", None)


class _FakeHttp:
    def __init__(self, status: int = 200, text: str = "", json: dict | None = None) -> None:
        self.status = status
        self.text = text
        self._json = json
        self.calls: list[tuple] = []

    async def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self._resp()

    async def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self._resp()

    def _resp(self):
        from one_osint.core.http_client import Response

        class P:
            def __init__(self, status, text, _json):
                self.status_code = status
                self.text = text
                self._json = _json

            def json(self):
                if self._json is None:
                    raise ValueError("no json")
                return self._json

        p = P(self.status, self.text, self._json)
        return Response(status_code=p.status_code, text=p.text, headers={}, url="")

    async def aclose(self) -> None:
        return None


class TestEnumEngine:
    def test_found_when_marker_matches(self) -> None:
        http = _FakeHttp(status=200, text="email already registered")
        site = EnumSite("SiteA", "social", url="https://x.com/check",
                        found=[Rule("string", "already registered")])
        hits = __import__("asyncio").run(EnumEngine(http).check_email("a@b.com", [site]))
        assert len(hits) == 1
        assert hits[0].status == "found"
        assert hits[0].exists is True

    def test_not_found_when_negative_marker(self) -> None:
        http = _FakeHttp(status=200, text="email not found; available")
        site = EnumSite("SiteB", "social", url="https://x.com/check",
                        found=[Rule("string", "available")],
                        not_found=[Rule("string", "not found")])
        hits = __import__("asyncio").run(EnumEngine(http).check_email("a@b.com", [site]))
        assert hits[0].status == "not_found"
        assert hits[0].exists is False

    def test_loud_skipped_without_flag(self) -> None:
        http = _FakeHttp(status=200, text="already registered")
        site = EnumSite("SiteC", "social", url="https://x.com/check", loud=True,
                        found=[Rule("string", "already registered")])
        hits = __import__("asyncio").run(EnumEngine(http).check_email("a@b.com", [site]))
        assert hits[0].status == "skipped"

    def test_loud_allowed_with_flag(self) -> None:
        http = _FakeHttp(status=200, text="already registered")
        site = EnumSite("SiteD", "social", url="https://x.com/check", loud=True,
                        found=[Rule("string", "already registered")])
        hits = __import__("asyncio").run(
            EnumEngine(http).check_email("a@b.com", [site], allow_loud=True)
        )
        assert hits[0].status == "found"

    def test_error_captured(self) -> None:
        class Boom:
            async def get(self, *a, **k):
                raise RuntimeError("net down")

            async def aclose(self):
                pass

        site = EnumSite("SiteE", "social", url="https://x.com/check",
                        found=[Rule("string", "yes")])
        hits = __import__("asyncio").run(EnumEngine(Boom()).check_email("a@b.com", [site]))
        assert hits[0].status == "error"
        assert "net down" in hits[0].extra["error"]

    def test_input_substitution_and_json_body(self) -> None:
        seen: dict = {}

        class Capture:
            async def post(self, url: str, **kwargs):
                seen["url"] = url
                seen["json"] = kwargs.get("json")
                from one_osint.core.http_client import Response
                return Response(status_code=200, text='{"ok": 1}', headers={}, url="")

            async def aclose(self):
                pass

        site = EnumSite("SiteF", "social", url="https://x.com/api/{input}",
                        http_method="POST",
                        json_body={"email": "{email}", "ref": "{input}"},
                        found=[Rule("json", 1, "ok")],
                        input_operation="hash-sha256")
        import hashlib
        email = "a@b.com"
        expect_hash = hashlib.sha256(email.encode()).hexdigest()
        hits = __import__("asyncio").run(EnumEngine(Capture()).check_email(email, [site]))
        assert hits[0].status == "found"
        assert seen["url"].endswith(expect_hash)
        assert seen["json"]["email"] == email
        assert seen["json"]["ref"] == expect_hash

    def test_recovery_fn(self) -> None:
        http = _FakeHttp(status=200, text="recovery email: sec***@gmail.com")
        site = EnumSite("SiteG", "social", url="https://x.com/check",
                        found=[Rule("string", "recovery email")],
                        recover=lambda s, t, p: {"recovery_email": "sec***@gmail.com"})
        hits = __import__("asyncio").run(EnumEngine(http).check_email("a@b.com", [site]))
        assert hits[0].extra == {"recovery_email": "sec***@gmail.com"}
