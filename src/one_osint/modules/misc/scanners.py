"""Miscellaneous OSINT modules: GitHub, ProtonMail, VIN, dorks, plates."""

from __future__ import annotations

import time
from urllib.parse import quote

from ...core.config import Settings
from ...core.http_client import get_http_client
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule


class GithubSearch(BaseModule):
    name = "github_search"
    description = "GitHub user/repo search for an email or username"
    input_types = ("email", "username")

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        headers = {}
        if self.keys and self.keys.has("github"):
            headers["Authorization"] = f"token {self.keys.get('github')}"
        try:
            resp = await http.get(
                "https://api.github.com/search/users",
                params={"q": target, "per_page": 5},
                headers=headers,
            )
            if resp.status_code != 200:
                result.error = f"github returned {resp.status_code}"
                result.findings.append(Finding(site="github", status=Status.ERROR))
            else:
                items = resp.json().get("items", [])
                result.summary = {"users": len(items)}
                if not items:
                    result.findings.append(Finding(site="github", status=Status.NOT_FOUND))
                for u in items:
                    result.findings.append(
                        Finding(
                            site="github", url=u.get("html_url"), status=Status.FOUND,
                            category="dev",
                            extra={
                                "login": u.get("login"),
                                "id": u.get("id"),
                                "avatar": u.get("avatar_url"),
                            },
                            media=[u["avatar_url"]] if u.get("avatar_url") else [],
                        )
                    )
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="github", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class ProtonmailLookup(BaseModule):
    name = "protonmail_lookup"
    description = "ProtonMail PGP key lookup - confirms Proton account existence"
    input_types = ("email",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        try:
            resp = await http.get(f"https://api.protonmail.ch/pks/lookup?op=get&search={quote(target, safe='')}")
            if resp.status_code == 200 and "pub" in resp.text:
                result.summary = {"proton_account": True, "pgp_key": True}
                result.findings.append(
                    Finding(
                        site="protonmail", status=Status.FOUND, category="webmail",
                        extra={"pgp_key_available": True},
                    )
                )
            else:
                result.summary = {"proton_account": False}
                result.findings.append(Finding(site="protonmail", status=Status.NOT_FOUND))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="protonmail", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class VinDecode(BaseModule):
    name = "vin_decode"
    description = "NHTSA vPIC VIN decoder - vehicle specs"
    input_types = ("username",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        if len(target) != 17:
            result.error = f"invalid VIN length: {len(target)}"
            result.findings.append(Finding(site="vin", status=Status.ERROR, category="vehicle"))
            result.duration = time.perf_counter() - started
            return result
        http = get_http_client(self.settings or Settings())
        try:
            resp = await http.get(
                f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesExtended/{target}?format=json",
                timeout=20,
            )
            if resp.status_code != 200:
                result.findings.append(Finding(site="vin", status=Status.ERROR))
            else:
                row = (resp.json().get("Results") or [{}])[0]
                if row.get("ErrorCode") == "0" and row.get("Make"):
                    clean = {k: v for k, v in row.items() if v and k not in ("ErrorText", "ErrorCode")}
                    result.summary = clean
                    result.findings.append(
                        Finding(site="vin", status=Status.FOUND, category="vehicle",
                                extra=clean)
                    )
                else:
                    result.findings.append(Finding(site="vin", status=Status.NOT_FOUND))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="vin", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class GoogleDorks(BaseModule):
    name = "google_dorks"
    description = "Google dork query generation for an email"
    input_types = ("email", "username")

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        queries = [
            f"intext:'{target}'",
            f'"{target}" filetype:pdf',
            f'"{target}" filetype:csv',
            f'"{target}" site:pastebin.com',
            f'"{target}" site:github.com',
            f'"{target}" site:linkedin.com',
            f'"{target}" site:facebook.com',
            f'"{target}" -site:linkedin.com -site:facebook.com',
        ]
        result.summary = {"dorks": len(queries)}
        for q in queries:
            result.findings.append(
                Finding(
                    site="google", status=Status.POSSIBLE, category="dorks",
                    url=f"https://www.google.com/search?q={quote(q)}",
                    reason="ready-to-run search link (not verified)",
                    extra={"query": q},
                )
            )
        result.duration = time.perf_counter() - started
        return result


class LicensePlateLookup(BaseModule):
    name = "license_plate"
    description = "US license plate lookup via findbyplate.com"
    input_types = ("username",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        if "-" not in target:
            result.error = "usage: <plate>-<US state abbreviation>, e.g. ABC123-CA"
            result.findings.append(Finding(site="plate", status=Status.ERROR, category="vehicle"))
            result.duration = time.perf_counter() - started
            return result
        plate, state = target.rsplit("-", 1)
        http = get_http_client(self.settings or Settings())
        try:
            resp = await http.get(
                f"https://findbyplate.com/US/{state.upper()}/{plate}/",
                impersonate="chrome124",
            )
            if resp.status_code != 200:
                result.findings.append(Finding(site="findbyplate", status=Status.ERROR))
                result.error = f"findbyplate returned {resp.status_code}"
            else:
                import re

                m = re.search(r"([\d]{4})\s+([A-Z][a-z]+)", resp.text)
                text = re.sub(r"<[^>]+>", " ", resp.text)
                text = re.sub(r"\s+", " ", text)
                result.summary = {"page_scraped": True}
                result.findings.append(
                    Finding(
                        site="findbyplate", status=Status.FOUND, category="vehicle",
                        url=f"https://findbyplate.com/US/{state.upper()}/{plate}/",
                        extra={"snippet": text[:500], "year_hint": m.group(1) if m else None},
                    )
                )
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="findbyplate", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class DarkWebSearch(BaseModule):
    name = "dark_web_search"
    description = "Ahmia .onion search (requires Tor SOCKS proxy on 127.0.0.1:9050)"
    input_types = ("email", "username")
    opt_in = True

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        settings = self.settings or Settings()
        if not settings.tor:
            result.summary = {"skipped": "tor proxy not enabled (--tor)"}
            result.findings.append(Finding(site="ahmia", status=Status.SKIPPED, category="darkweb"))
            result.duration = time.perf_counter() - started
            return result
        http = get_http_client(settings)
        try:
            resp = await http.get(f"https://ahmia.fi/search/?q={quote(target, safe='')}", timeout=30)
            if resp.status_code == 200:
                import re

                links = re.findall(r'<a href="(http[^"]+\.onion[^"]*)"', resp.text)
                result.summary = {"onion_results": len(links)}
                if not links:
                    result.findings.append(Finding(site="ahmia", status=Status.NOT_FOUND))
                for link in links[:20]:
                    result.findings.append(
                        Finding(site="ahmia", url=link, status=Status.FOUND, category="darkweb")
                    )
            else:
                result.findings.append(Finding(site="ahmia", status=Status.ERROR))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="ahmia", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result
