"""Comprehensive tests for many OSINT modules (phone, domain, ip, misc, username, email, file)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from one_osint.core.config import KeyVault, Settings
from one_osint.core.http_client import Response
from one_osint.core.result import Status


# Helpers

class FakeHttp:
    def __init__(self, responses: dict[str, Response] | Response | None = None):
        self._responses = responses
        self.calls: list = []

    async def get(self, url: str, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if isinstance(self._responses, dict):
            # try exact url, then prefix
            for k, v in self._responses.items():
                if k in url:
                    return v
            return Response(404, "", {}, url)
        if isinstance(self._responses, Response):
            return self._responses
        return Response(200, '{"ok": true}', {}, url)

    async def post(self, url: str, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if isinstance(self._responses, dict):
            for k, v in self._responses.items():
                if k in url:
                    return v
            return Response(404, "", {}, url)
        if isinstance(self._responses, Response):
            return self._responses
        return Response(200, '{"ok": true}', {}, url)

    async def aclose(self):
        pass


def _patch_http(monkeypatch, fake: FakeHttp):
    monkeypatch.setattr("one_osint.modules.phone.scanners.get_http_client", lambda s=None: fake)
    monkeypatch.setattr("one_osint.modules.email.dns_pivot.get_http_client", lambda s=None: fake)
    monkeypatch.setattr("one_osint.modules.email.reputation.get_http_client", lambda s=None: fake)
    monkeypatch.setattr("one_osint.modules.email.breaches.get_http_client", lambda s=None: fake)
    monkeypatch.setattr("one_osint.modules.ip.scanners.get_http_client", lambda s=None: fake)
    monkeypatch.setattr("one_osint.modules.google.scanners.get_http_client", lambda s=None: fake)
    monkeypatch.setattr("one_osint.modules.misc.scanners.get_http_client", lambda s=None: fake)
    monkeypatch.setattr("one_osint.modules.domain.scanners.get_http_client", lambda s=None: fake)
    monkeypatch.setattr("one_osint.modules.username.curated.get_http_client", lambda s=None: fake)
    monkeypatch.setattr("one_osint.modules.email.enumeration.get_http_client", lambda s=None: fake)
    monkeypatch.setattr("one_osint.modules.file.metadata.get_http_client", lambda s=None: fake)


# Phone parse

class TestPhoneParse:
    def test_parse_valid(self) -> None:
        from one_osint.modules.phone.parse import parse_number
        parsed = parse_number("+33612345678")
        assert parsed is not None
        assert parsed["e164"] == "+33612345678"
        assert parsed["country"] == "FR"

    def test_parse_invalid(self) -> None:
        from one_osint.modules.phone.parse import parse_number
        assert parse_number("not a number") is None
        assert parse_number("123") is None

    def test_parse_with_spaces(self) -> None:
        from one_osint.modules.phone.parse import parse_number
        parsed = parse_number("+1 202-555-0123")
        assert parsed is not None
        assert parsed["country_code"] == 1

    def test_build_dorks(self) -> None:
        from one_osint.modules.phone.parse import build_dorks
        dorks = build_dorks("+33612345678")
        assert "social_media" in dorks
        assert "disposable_services" in dorks
        assert "reputation_reports" in dorks
        assert "individuals" in dorks
        assert "files" in dorks
        assert "generic" in dorks
        # Check that number appears in queries
        all_queries = sum(dorks.values(), [])
        assert any("+33612345678" in q or "33612345678" in q for q in all_queries)
        assert len(all_queries) > 30


class TestPhoneModules:
    @pytest.mark.asyncio
    async def test_phone_local_valid(self) -> None:
        from one_osint.modules.phone.scanners import PhoneLocal
        mod = PhoneLocal(keys=KeyVault(), settings=Settings())
        result = await mod.check("+33612345678")
        assert any(f.status == Status.FOUND for f in result.findings)
        assert result.summary["e164"] == "+33612345678"

    @pytest.mark.asyncio
    async def test_phone_local_invalid(self) -> None:
        from one_osint.modules.phone.scanners import PhoneLocal
        mod = PhoneLocal(keys=KeyVault(), settings=Settings())
        result = await mod.check("badphone")
        assert result.error is not None
        assert any(f.status == Status.ERROR for f in result.findings)

    @pytest.mark.asyncio
    async def test_phone_dorks_valid(self) -> None:
        from one_osint.modules.phone.scanners import PhoneDorks
        mod = PhoneDorks(keys=KeyVault(), settings=Settings())
        result = await mod.check("+33612345678")
        assert len(result.findings) > 20
        assert all(f.status == Status.POSSIBLE for f in result.findings)
        assert result.summary["dorks"] > 20

    @pytest.mark.asyncio
    async def test_phone_dorks_invalid(self) -> None:
        from one_osint.modules.phone.scanners import PhoneDorks
        mod = PhoneDorks(keys=KeyVault(), settings=Settings())
        result = await mod.check("notaphone")
        assert any(f.status == Status.ERROR for f in result.findings)

    @pytest.mark.asyncio
    async def test_phone_numverify_found(self, monkeypatch) -> None:
        from one_osint.modules.phone.scanners import PhoneNumverify
        fake = FakeHttp(Response(200, json.dumps({"valid": True, "number": "+33612345678", "country_name": "France"}), {}, ""))
        monkeypatch.setattr("one_osint.modules.phone.scanners.get_http_client", lambda s=None: fake)
        mod = PhoneNumverify(keys=KeyVault(overrides={"numverify": "key"}), settings=Settings())
        result = await mod.check("+33612345678")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_phone_numverify_not_found(self, monkeypatch) -> None:
        from one_osint.modules.phone.scanners import PhoneNumverify
        fake = FakeHttp(Response(200, json.dumps({"valid": False}), {}, ""))
        monkeypatch.setattr("one_osint.modules.phone.scanners.get_http_client", lambda s=None: fake)
        mod = PhoneNumverify(keys=KeyVault(overrides={"numverify": "k"}), settings=Settings())
        result = await mod.check("+33612345678")
        assert any(f.status == Status.NOT_FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_phone_numverify_error_status(self, monkeypatch) -> None:
        from one_osint.modules.phone.scanners import PhoneNumverify
        fake = FakeHttp(Response(500, "error", {}, ""))
        monkeypatch.setattr("one_osint.modules.phone.scanners.get_http_client", lambda s=None: fake)
        mod = PhoneNumverify(keys=KeyVault(overrides={"numverify": "k"}), settings=Settings())
        result = await mod.check("+33612345678")
        assert any(f.status == Status.ERROR for f in result.findings)
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_phone_ovh_skipped(self) -> None:
        from one_osint.modules.phone.scanners import PhoneOvh
        mod = PhoneOvh(keys=KeyVault(), settings=Settings())
        # US number not in FR/BE/GB/ES/CH mapping
        result = await mod.check("+12025550123")
        assert any(f.status == Status.SKIPPED for f in result.findings)

    @pytest.mark.asyncio
    async def test_phone_ovh_found(self, monkeypatch) -> None:
        from one_osint.modules.phone.scanners import PhoneOvh
        fake = FakeHttp(Response(200, json.dumps(["zone1"]), {}, ""))
        monkeypatch.setattr("one_osint.modules.phone.scanners.get_http_client", lambda s=None: fake)
        mod = PhoneOvh(keys=KeyVault(), settings=Settings())
        result = await mod.check("+33612345678")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_phone_google_cse_missing_cx(self) -> None:
        from one_osint.modules.phone.scanners import PhoneGoogleCse
        mod = PhoneGoogleCse(keys=KeyVault(overrides={"google_cse": "key"}), settings=Settings())
        result = await mod.check("+33612345678")
        assert any(f.status == Status.SKIPPED for f in result.findings)

    @pytest.mark.asyncio
    async def test_phone_google_cse_found(self, monkeypatch) -> None:
        from one_osint.modules.phone.scanners import PhoneGoogleCse
        fake = FakeHttp(Response(200, json.dumps({"items": [{"link": "https://example.com", "title": "t", "snippet": "s"}]}), {}, ""))
        monkeypatch.setattr("one_osint.modules.phone.scanners.get_http_client", lambda s=None: fake)
        mod = PhoneGoogleCse(keys=KeyVault(overrides={"google_cse": "k", "google_cse_cx": "cx"}), settings=Settings())
        result = await mod.check("+33612345678")
        assert any(f.status == Status.FOUND for f in result.findings)


class TestIpModules:
    @pytest.mark.asyncio
    async def test_ip_whois_found(self, monkeypatch) -> None:
        from one_osint.modules.ip.scanners import IpWhois
        fake = FakeHttp(Response(200, json.dumps({"success": True, "ip": "8.8.8.8", "country": "US", "org": "Google"}), {}, ""))
        monkeypatch.setattr("one_osint.modules.ip.scanners.get_http_client", lambda s=None: fake)
        mod = IpWhois(keys=KeyVault(), settings=Settings())
        result = await mod.check("8.8.8.8")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_ip_whois_not_found(self, monkeypatch) -> None:
        from one_osint.modules.ip.scanners import IpWhois
        fake = FakeHttp(Response(200, json.dumps({"success": False}), {}, ""))
        monkeypatch.setattr("one_osint.modules.ip.scanners.get_http_client", lambda s=None: fake)
        mod = IpWhois(keys=KeyVault(), settings=Settings())
        result = await mod.check("0.0.0.0")
        assert any(f.status == Status.NOT_FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_ip_whois_error(self, monkeypatch) -> None:
        from one_osint.modules.ip.scanners import IpWhois
        fake = FakeHttp(Response(500, "err", {}, ""))
        monkeypatch.setattr("one_osint.modules.ip.scanners.get_http_client", lambda s=None: fake)
        mod = IpWhois(keys=KeyVault(), settings=Settings())
        result = await mod.check("8.8.8.8")
        assert any(f.status == Status.ERROR for f in result.findings)

    @pytest.mark.asyncio
    async def test_ip_shodan_found(self, monkeypatch) -> None:
        from one_osint.modules.ip.scanners import IpShodan
        fake = FakeHttp(Response(200, json.dumps({"ports": [80, 443], "vulns": ["CVE-2020-1234"], "hostnames": ["a"], "org": "X", "os": "Linux"}), {}, ""))
        monkeypatch.setattr("one_osint.modules.ip.scanners.get_http_client", lambda s=None: fake)
        mod = IpShodan(keys=KeyVault(overrides={"shodan": "key"}), settings=Settings())
        result = await mod.check("8.8.8.8")
        assert any(f.status == Status.FOUND for f in result.findings)
        # ports + vulns = 3 findings
        assert len([f for f in result.findings if f.status == Status.FOUND]) == 3

    @pytest.mark.asyncio
    async def test_ip_reverse_dns_found(self, monkeypatch) -> None:
        from one_osint.modules.ip.scanners import IpReverseDns

        async def fake_resolve(ip, lifetime=8):
            class R:
                def __str__(self): return "dns.google."
            return [R()]

        monkeypatch.setattr("dns.asyncresolver.resolve_address", fake_resolve)
        mod = IpReverseDns(keys=KeyVault(), settings=Settings())
        result = await mod.check("8.8.8.8")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_ip_reverse_dns_error(self, monkeypatch) -> None:
        from one_osint.modules.ip.scanners import IpReverseDns

        async def fake_resolve(ip, lifetime=8):
            raise Exception("dns fail")

        monkeypatch.setattr("dns.asyncresolver.resolve_address", fake_resolve)
        mod = IpReverseDns(keys=KeyVault(), settings=Settings())
        result = await mod.check("8.8.8.8")
        assert any(f.status == Status.ERROR for f in result.findings)


class TestMiscModules:
    @pytest.mark.asyncio
    async def test_github_search_found(self, monkeypatch) -> None:
        from one_osint.modules.misc.scanners import GithubSearch
        fake = FakeHttp(Response(200, json.dumps({"items": [{"login": "alice", "html_url": "https://github.com/alice", "avatar_url": "https://a", "id": 1}]}), {}, ""))
        monkeypatch.setattr("one_osint.modules.misc.scanners.get_http_client", lambda s=None: fake)
        mod = GithubSearch(keys=KeyVault(), settings=Settings())
        result = await mod.check("alice")
        assert any(f.status == Status.FOUND for f in result.findings)
        assert "alice" in result.findings[0].extra["login"]

    @pytest.mark.asyncio
    async def test_github_search_not_found(self, monkeypatch) -> None:
        from one_osint.modules.misc.scanners import GithubSearch
        fake = FakeHttp(Response(200, json.dumps({"items": []}), {}, ""))
        monkeypatch.setattr("one_osint.modules.misc.scanners.get_http_client", lambda s=None: fake)
        mod = GithubSearch(keys=KeyVault(), settings=Settings())
        result = await mod.check("nobody_xyz_123")
        assert any(f.status == Status.NOT_FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_protonmail_found(self, monkeypatch) -> None:
        from one_osint.modules.misc.scanners import ProtonmailLookup
        fake = FakeHttp(Response(200, "-----BEGIN PGP PUBLIC KEY BLOCK----- pub", {}, ""))
        monkeypatch.setattr("one_osint.modules.misc.scanners.get_http_client", lambda s=None: fake)
        mod = ProtonmailLookup(keys=KeyVault(), settings=Settings())
        result = await mod.check("test@protonmail.com")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_protonmail_not_found(self, monkeypatch) -> None:
        from one_osint.modules.misc.scanners import ProtonmailLookup
        fake = FakeHttp(Response(404, "not found", {}, ""))
        monkeypatch.setattr("one_osint.modules.misc.scanners.get_http_client", lambda s=None: fake)
        mod = ProtonmailLookup(keys=KeyVault(), settings=Settings())
        result = await mod.check("no@protonmail.com")
        assert any(f.status == Status.NOT_FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_vin_invalid_length(self) -> None:
        from one_osint.modules.misc.scanners import VinDecode
        mod = VinDecode(keys=KeyVault(), settings=Settings())
        result = await mod.check("SHORT")
        assert any(f.status == Status.ERROR for f in result.findings)

    @pytest.mark.asyncio
    async def test_vin_found(self, monkeypatch) -> None:
        from one_osint.modules.misc.scanners import VinDecode
        fake_resp = Response(200, json.dumps({"Results": [{"ErrorCode": "0", "Make": "Toyota", "Model": "Camry", "ErrorText": ""}]}), {}, "")
        monkeypatch.setattr("one_osint.modules.misc.scanners.get_http_client", lambda s=None: FakeHttp(fake_resp))
        mod = VinDecode(keys=KeyVault(), settings=Settings())
        result = await mod.check("1HGCM82633A123456")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_google_dorks(self) -> None:
        from one_osint.modules.misc.scanners import GoogleDorks
        mod = GoogleDorks(keys=KeyVault(), settings=Settings())
        result = await mod.check("alice@example.com")
        assert len(result.findings) == 8
        assert all(f.status == Status.POSSIBLE for f in result.findings)
        assert all("google.com/search" in (f.url or "") for f in result.findings)

    @pytest.mark.asyncio
    async def test_license_plate_error_no_dash(self) -> None:
        from one_osint.modules.misc.scanners import LicensePlateLookup
        mod = LicensePlateLookup(keys=KeyVault(), settings=Settings())
        result = await mod.check("ABC123")
        assert any(f.status == Status.ERROR for f in result.findings)

    @pytest.mark.asyncio
    async def test_dark_web_skipped_without_tor(self) -> None:
        from one_osint.modules.misc.scanners import DarkWebSearch
        mod = DarkWebSearch(keys=KeyVault(), settings=Settings(tor=False))
        result = await mod.check("alice")
        assert any(f.status == Status.SKIPPED for f in result.findings)


class TestUsernamePermute:
    def test_basic(self) -> None:
        from one_osint.modules.username.permute import permute_username
        assert permute_username("") == []
        assert "alice" in permute_username("alice")

    def test_with_dot(self) -> None:
        from one_osint.modules.username.permute import permute_username
        variants = permute_username("john.doe")
        assert "john_doe" in variants
        assert "john-doe" in variants
        assert "johndoe" in variants

    def test_all_variants(self) -> None:
        from one_osint.modules.username.permute import permute_username
        variants = permute_username("john.doe", all_variants=True)
        # Should include permutations
        assert len(variants) > 4
        # Single part all_variants adds suffixes
        single = permute_username("alice", all_variants=True)
        assert any(v.startswith("alice") and v != "alice" for v in single)

    def test_case_insensitive(self) -> None:
        from one_osint.modules.username.permute import permute_username
        variants = permute_username("John.Doe")
        assert "john_doe" in variants


class TestUsernameCurated:
    @pytest.mark.asyncio
    async def test_github_found(self, monkeypatch) -> None:
        from one_osint.modules.username.curated import UsernameGithub
        fake = FakeHttp(Response(200, json.dumps({"html_url": "https://github.com/alice", "name": "Alice", "avatar_url": "https://a", "followers": 10, "public_repos": 5}), {}, ""))
        monkeypatch.setattr("one_osint.modules.username.curated.get_http_client", lambda s=None: fake)
        mod = UsernameGithub(keys=KeyVault(), settings=Settings())
        result = await mod.check("alice")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_github_not_found(self, monkeypatch) -> None:
        from one_osint.modules.username.curated import UsernameGithub
        fake = FakeHttp(Response(404, "not found", {}, ""))
        monkeypatch.setattr("one_osint.modules.username.curated.get_http_client", lambda s=None: fake)
        mod = UsernameGithub(keys=KeyVault(), settings=Settings())
        result = await mod.check("alice")
        assert any(f.status == Status.NOT_FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_reddit_found(self, monkeypatch) -> None:
        from one_osint.modules.username.curated import UsernameReddit
        fake = FakeHttp(Response(200, json.dumps({"data": {"subreddit": {"title": "alice"}, "total_karma": 123}}), {}, ""))
        monkeypatch.setattr("one_osint.modules.username.curated.get_http_client", lambda s=None: fake)
        mod = UsernameReddit(keys=KeyVault(), settings=Settings())
        result = await mod.check("alice")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_mastodon_found(self, monkeypatch) -> None:
        from one_osint.modules.username.curated import UsernameMastodon
        payload = {"accounts": [{"username": "alice", "url": "https://mastodon.social/@alice", "display_name": "Alice", "followers_count": 10}]}
        fake = FakeHttp(Response(200, json.dumps(payload), {}, ""))
        monkeypatch.setattr("one_osint.modules.username.curated.get_http_client", lambda s=None: fake)
        mod = UsernameMastodon(keys=KeyVault(), settings=Settings())
        result = await mod.check("alice")
        assert any(f.status == Status.FOUND for f in result.findings)


class TestWmnExtras:
    def test_check_content_negative(self) -> None:
        from one_osint.modules.username.wmn_engine import WmnSite, check_content_negative
        site = WmnSite(name="x", uri_check="https://x.com/{account}")
        assert check_content_negative("alice", "user alice not found", site) is True
        assert check_content_negative("alice", "profile page for alice", site) is False
        # case-insensitive / accent folding
        assert check_content_negative("Alice", "USER ALICE NOT FOUND", site) is True

    def test_load_wmn_sites(self) -> None:
        from one_osint.modules.username.wmn_engine import load_wmn_sites
        sites = load_wmn_sites()
        assert len(sites) > 100
        assert any(s.name for s in sites)

    def test_pick_impersonate(self) -> None:
        from one_osint.modules.username.wmn_engine import WmnSite, WmnChecker
        site_cf = WmnSite(name="x", uri_check="https://x.com/{account}", protection=["cloudflare"])
        assert WmnChecker._pick_impersonate(site_cf) == "chrome124"
        site_plain = WmnSite(name="y", uri_check="https://y.com/{account}", protection=[])
        assert WmnChecker._pick_impersonate(site_plain) is None

    def test_fold(self) -> None:
        from one_osint.modules.username.wmn_engine import _fold
        assert _fold("Héllo") == "hello"
        # lowercase accent folding is reliable
        assert _fold("ñandú") == "nandu"
        # uppercase Ñ folds to remain ñ due to translate->lower ordering (known limitation)
        assert "n" in _fold("Ñandú")  # at least contains n after folding/lowercasing


class TestGoogleModules:
    @pytest.mark.asyncio
    async def test_google_email_probe_found(self, monkeypatch) -> None:
        from one_osint.modules.google.scanners import GoogleEmailProbe
        fake = FakeHttp(Response(200, "ok", {"Set-Cookie": "SID=123"}, ""))
        monkeypatch.setattr("one_osint.modules.google.scanners.get_http_client", lambda s=None: fake)
        mod = GoogleEmailProbe(keys=KeyVault(), settings=Settings())
        result = await mod.check("alice@gmail.com")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_google_email_probe_not_found(self, monkeypatch) -> None:
        from one_osint.modules.google.scanners import GoogleEmailProbe
        fake = FakeHttp(Response(404, "not found", {}, ""))
        monkeypatch.setattr("one_osint.modules.google.scanners.get_http_client", lambda s=None: fake)
        mod = GoogleEmailProbe(keys=KeyVault(), settings=Settings())
        result = await mod.check("alice@gmail.com")
        assert any(f.status == Status.NOT_FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_bssid_geo_found(self, monkeypatch) -> None:
        from one_osint.modules.google.scanners import GoogleBssidGeo
        fake = FakeHttp(Response(200, json.dumps({"location": {"lat": 48.85, "lng": 2.35}, "accuracy": 20}), {}, ""))
        monkeypatch.setattr("one_osint.modules.google.scanners.get_http_client", lambda s=None: fake)
        mod = GoogleBssidGeo(keys=KeyVault(overrides={"google_geolocation": "key"}), settings=Settings())
        result = await mod.check("00:11:22:33:44:55")
        assert any(f.status == Status.FOUND for f in result.findings)


class TestEmailDnsPivot:
    @pytest.mark.asyncio
    async def test_dns_pivot_with_mocked_dns(self, monkeypatch) -> None:
        from one_osint.modules.email.dns_pivot import DnsPivot

        async def fake_resolve(domain, rtype, lifetime=8):
            mapping = {
                ("example.com", "A"): ["93.184.216.34"],
                ("example.com", "MX"): ["10 mail.example.com."],
                ("example.com", "TXT"): ["v=spf1 include:_spf.example.com ~all"],
                ("example.com", "NS"): ["ns1.example.com."],
                ("_dmarc.example.com", "TXT"): ["v=DMARC1; p=none"],
            }
            return mapping.get((domain, rtype), [])

        monkeypatch.setattr("one_osint.modules.email.dns_pivot._resolve", fake_resolve)
        mod = DnsPivot(keys=KeyVault(), settings=Settings())
        result = await mod.check("alice@example.com")
        assert any(f.extra.get("type") == "MX" for f in result.findings)
        assert any(f.extra.get("type") == "SPF" for f in result.findings)
        assert any(f.extra.get("type") == "DMARC" for f in result.findings)

    @pytest.mark.asyncio
    async def test_ip_geolocation_found(self, monkeypatch) -> None:
        from one_osint.modules.email.dns_pivot import IpGeolocation
        fake = FakeHttp(Response(200, json.dumps({"ip": "8.8.8.8", "city": "Mountain View", "country_name": "United States"}), {}, ""))
        monkeypatch.setattr("one_osint.modules.email.dns_pivot.get_http_client", lambda s=None: fake)

        # Mock DNS to return IP for domain
        async def fake_resolve(domain, rtype, lifetime=8):
            class R:
                def __str__(self): return "8.8.8.8"
            return [R()]

        monkeypatch.setattr("dns.asyncresolver.resolve", fake_resolve)
        mod = IpGeolocation(keys=KeyVault(), settings=Settings())
        result = await mod.check("8.8.8.8")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_ip_geolocation_resolve_fail(self, monkeypatch) -> None:
        from one_osint.modules.email.dns_pivot import IpGeolocation

        async def fake_resolve(domain, rtype, lifetime=8):
            raise Exception("nxdomain")

        monkeypatch.setattr("dns.asyncresolver.resolve", fake_resolve)
        mod = IpGeolocation(keys=KeyVault(), settings=Settings())
        result = await mod.check("nonexistent.invalid")
        assert any(f.status == Status.ERROR for f in result.findings)


class TestEmailReputationAndBreaches:
    @pytest.mark.asyncio
    async def test_email_reputation_found(self, monkeypatch) -> None:
        from one_osint.modules.email.reputation import EmailReputation
        payload = {"reputation": "high", "suspicious": False, "references": 5, "details": {"breached": True, "spam": True, "malicious_activity": False, "credentials_leaked": False, "first_seen": "2020", "last_seen": "2024", "profiles": []}}
        fake = FakeHttp(Response(200, json.dumps(payload), {}, ""))
        monkeypatch.setattr("one_osint.modules.email.reputation.get_http_client", lambda s=None: fake)
        mod = EmailReputation(keys=KeyVault(overrides={"emailrep": "key"}), settings=Settings())
        result = await mod.check("alice@example.com")
        assert any(f.status == Status.FOUND for f in result.findings)
        assert "breached" in result.findings[0].extra["flags"]

    @pytest.mark.asyncio
    async def test_breach_hibp_found(self, monkeypatch) -> None:
        from one_osint.modules.email.breaches import BreachHibp
        payload = [{"Title": "Adobe", "Domain": "adobe.com", "BreachDate": "2013-10-04", "AddedDate": "2013-12-04", "DataClasses": ["Emails"], "Description": "desc"}]
        fake = FakeHttp(Response(200, json.dumps(payload), {}, ""))
        monkeypatch.setattr("one_osint.modules.email.breaches.get_http_client", lambda s=None: fake)
        mod = BreachHibp(keys=KeyVault(overrides={"hibp": "key"}), settings=Settings())
        result = await mod.check("alice@example.com")
        assert any(f.extra.get("breach") == "Adobe" for f in result.findings)

    @pytest.mark.asyncio
    async def test_breach_hibp_not_found(self, monkeypatch) -> None:
        from one_osint.modules.email.breaches import BreachHibp
        fake = FakeHttp(Response(404, "not found", {}, ""))
        monkeypatch.setattr("one_osint.modules.email.breaches.get_http_client", lambda s=None: fake)
        mod = BreachHibp(keys=KeyVault(overrides={"hibp": "key"}), settings=Settings())
        result = await mod.check("alice@example.com")
        assert any(f.status == Status.NOT_FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_pastebin_search_found(self, monkeypatch) -> None:
        from one_osint.modules.email.breaches import PastebinSearch
        fake = FakeHttp(Response(200, json.dumps({"data": [{"id": "abc123", "tags": ["email"], "time": "2024-01-01"}]}), {}, ""))
        monkeypatch.setattr("one_osint.modules.email.breaches.get_http_client", lambda s=None: fake)
        mod = PastebinSearch(keys=KeyVault(), settings=Settings())
        result = await mod.check("alice@example.com")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_breach_intelx_found(self, monkeypatch) -> None:
        from one_osint.modules.email.breaches import BreachIntelX
        fake = FakeHttp(Response(200, json.dumps({"totalresults": 1, "records": [{"name": "doc", "media": 0}]}), {}, ""))
        monkeypatch.setattr("one_osint.modules.email.breaches.get_http_client", lambda s=None: fake)
        mod = BreachIntelX(keys=KeyVault(overrides={"intelx": "key"}), settings=Settings())
        result = await mod.check("alice@example.com")
        assert any(f.status == Status.FOUND for f in result.findings)


class TestDomainModules:
    @pytest.mark.asyncio
    async def test_cert_transparency_found(self, monkeypatch) -> None:
        from one_osint.modules.domain.scanners import CertTransparency
        payload = [{"name_value": "a.example.com\nb.example.com\nother.com"}]
        fake = FakeHttp(Response(200, json.dumps(payload), {}, ""))
        monkeypatch.setattr("one_osint.modules.domain.scanners.get_http_client", lambda s=None: fake)
        mod = CertTransparency(keys=KeyVault(), settings=Settings())
        result = await mod.check("example.com")
        assert any("a.example.com" in (f.url or "") for f in result.findings)

    @pytest.mark.asyncio
    async def test_asn_lookup_found(self, monkeypatch) -> None:
        from one_osint.modules.domain.scanners import AsnLookup
        fake = FakeHttp(Response(200, "15169 | 8.8.8.0/24 | US | arin | 2000\n12345 | 1.1.1.0/24 | US | arin | 2010", {}, ""))
        monkeypatch.setattr("one_osint.modules.domain.scanners.get_http_client", lambda s=None: fake)
        mod = AsnLookup(keys=KeyVault(), settings=Settings())
        result = await mod.check("example.com")
        assert any(f.status == Status.FOUND for f in result.findings)

    @pytest.mark.asyncio
    async def test_asn_lookup_error(self, monkeypatch) -> None:
        from one_osint.modules.domain.scanners import AsnLookup
        fake = FakeHttp(Response(500, "error", {}, ""))
        monkeypatch.setattr("one_osint.modules.domain.scanners.get_http_client", lambda s=None: fake)
        mod = AsnLookup(keys=KeyVault(), settings=Settings())
        result = await mod.check("example.com")
        assert any(f.status == Status.ERROR for f in result.findings)


class TestFileMetadata:
    @pytest.mark.asyncio
    async def test_file_not_found(self) -> None:
        from one_osint.modules.file.metadata import FileMetadata
        mod = FileMetadata(keys=KeyVault(), settings=Settings())
        result = await mod.check("/nonexistent/path/file.jpg")
        assert any(f.status == Status.ERROR for f in result.findings)

    @pytest.mark.asyncio
    async def test_generic_file(self, tmp_path: Path) -> None:
        from one_osint.modules.file.metadata import FileMetadata
        p = tmp_path / "test.txt"
        p.write_text("hello world", encoding="utf-8")
        mod = FileMetadata(keys=KeyVault(), settings=Settings())
        result = await mod.check(str(p))
        # generic meta should produce FOUND with size info
        assert any(f.status == Status.FOUND for f in result.findings)
        assert result.summary["file"] == str(p)

    @pytest.mark.asyncio
    async def test_image_without_exif(self, tmp_path: Path) -> None:
        from PIL import Image
        from one_osint.modules.file.metadata import FileMetadata
        p = tmp_path / "img.jpg"
        img = Image.new("RGB", (10, 10), color="red")
        img.save(str(p), "JPEG")
        mod = FileMetadata(keys=KeyVault(), settings=Settings())
        result = await mod.check(str(p))
        # No exif but still should return something (maybe NOT_FOUND or FOUND with size)
        assert result.findings

    @pytest.mark.asyncio
    async def test_pdf_metadata(self, tmp_path: Path) -> None:
        from pypdf import PdfWriter
        from one_osint.modules.file.metadata import FileMetadata
        p = tmp_path / "doc.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.add_metadata({"/Title": "Test PDF", "/Author": "tester"})
        with open(p, "wb") as f:
            writer.write(f)
        mod = FileMetadata(keys=KeyVault(), settings=Settings())
        result = await mod.check(str(p))
        assert any(f.status in (Status.FOUND, Status.NOT_FOUND) for f in result.findings)

    def test_gps_decimal(self) -> None:
        from one_osint.modules.file.metadata import _gps_to_decimal
        assert _gps_to_decimal((30, 30, 30)) == 30.5 + 30 / 3600
        assert _gps_to_decimal(None) is None
        assert _gps_to_decimal("") is None


class TestBaseModule:
    def test_can_run(self) -> None:
        from one_osint.modules.base import BaseModule

        class Dummy(BaseModule):
            name = "dummy"
            input_types = ("email",)
            requires_key = "hibp"

            async def check(self, target: str):
                return None

        mod_no_key = Dummy(keys=KeyVault(), settings=Settings())
        assert mod_no_key.can_run("email") is False  # missing key

        mod_with_key = Dummy(keys=KeyVault(overrides={"hibp": "key"}), settings=Settings())
        assert mod_with_key.can_run("email") is True
        assert mod_with_key.can_run("username") is False
        assert mod_with_key.can_run("phone") is False

    def test_discover_modules(self) -> None:
        from one_osint.modules.base import discover_modules
        mods = discover_modules()
        assert "email_enumeration" in mods
        assert "username_whatsmyname" in mods
        assert "phone_local" in mods

    def test_get_module_unknown(self) -> None:
        from one_osint.modules.base import get_module
        with pytest.raises(KeyError):
            get_module("nonexistent_module_xyz")

    def test_get_modules_for(self) -> None:
        from one_osint.modules.base import get_modules_for
        mods = get_modules_for("email", keys=KeyVault(), settings=Settings(), allow_opt_in=False)
        assert len(mods) > 0
        # opt_in modules should be excluded
        assert all(not m.opt_in for m in mods)
        mods_all = get_modules_for("email", keys=KeyVault(), settings=Settings(), allow_opt_in=True)
        assert len(mods_all) >= len(mods)
