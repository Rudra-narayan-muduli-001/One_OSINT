"""Phone number modules: local parse, numverify, OVH, dorks, Google CSE."""

from __future__ import annotations

import time
from urllib.parse import quote

from ...core.config import Settings
from ...core.http_client import get_http_client
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule
from .parse import build_dorks, parse_number


class PhoneLocal(BaseModule):
    name = "phone_local"
    description = "Offline parsing: formats, country, carrier, line type"
    input_types = ("phone",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        parsed = parse_number(target)
        if parsed is None:
            result.error = f"invalid phone number: {target}"
            result.findings.append(Finding(site="local", status=Status.ERROR, category="phone"))
        else:
            result.summary = parsed
            result.findings.append(
                Finding(
                    site="local", status=Status.FOUND, category="phone",
                    url=f"tel:{parsed['e164']}", extra=parsed,
                )
            )
        result.duration = time.perf_counter() - started
        return result


class PhoneNumverify(BaseModule):
    name = "phone_numverify"
    description = "Numverify/apilayer - validation, location, carrier, line type"
    input_types = ("phone",)
    requires_key = "numverify"

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        key = self.keys.get("numverify") if self.keys else None
        try:
            resp = await http.get(
                "https://api.apilayer.com/number_verification/validate",
                params={"number": target},
                headers={"apikey": key},
            )
            if resp.status_code != 200:
                result.error = f"numverify returned {resp.status_code}"
                result.findings.append(Finding(site="numverify", status=Status.ERROR))
            else:
                d = resp.json()
                result.summary = d
                if d.get("valid"):
                    result.findings.append(
                        Finding(
                            site="numverify", status=Status.FOUND, category="phone",
                            extra={
                                "valid": d.get("valid"),
                                "number": d.get("number"),
                                "country": d.get("country_name"),
                                "country_code": d.get("country_code"),
                                "location": d.get("location"),
                                "carrier": d.get("carrier"),
                                "line_type": d.get("line_type"),
                            },
                        )
                    )
                else:
                    result.findings.append(Finding(site="numverify", status=Status.NOT_FOUND))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="numverify", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class PhoneOvh(BaseModule):
    name = "phone_ovh"
    description = "OVH Telecom - is the number an OVH VoIP line (FR/BE/UK/ES/CH)"
    input_types = ("phone",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        country = None
        parsed = parse_number(target)
        if parsed:
            country = {"FR": "33", "BE": "32", "GB": "44", "ES": "34", "CH": "41"}.get(
                parsed.get("country", "")
            )
        if not country:
            result.summary = {"skipped": "unsupported country"}
            result.findings.append(Finding(site="ovh", status=Status.SKIPPED, category="phone"))
            result.duration = time.perf_counter() - started
            return result
        try:
            resp = await http.get(
                "https://api.ovh.com/1.0/telephony/number/detailedZones",
                params={"country": country, "number": target.replace("+", "")},
            )
            if resp.status_code == 200:
                zones = resp.json()
                if zones:
                    result.summary = {"ovh_voip": True, "zones": zones}
                    result.findings.append(
                        Finding(
                            site="ovh", status=Status.FOUND, category="phone",
                            extra={"ovh_voip": True, "zones": zones},
                        )
                    )
                else:
                    result.summary = {"ovh_voip": False}
                    result.findings.append(Finding(site="ovh", status=Status.NOT_FOUND))
            else:
                result.findings.append(Finding(site="ovh", status=Status.ERROR))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="ovh", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class PhoneDorks(BaseModule):
    name = "phone_dorks"
    description = "30+ Google dork queries (social, disposable, reputation, files)"
    input_types = ("phone",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        parsed = parse_number(target)
        if not parsed:
            result.error = f"invalid phone number: {target}"
            result.findings.append(Finding(site="dorks", status=Status.ERROR))
            result.duration = time.perf_counter() - started
            return result
        e164 = parsed["e164"]
        dorks = build_dorks(e164)
        total = sum(len(v) for v in dorks.values())
        result.summary = {"dorks": total, "groups": {k: len(v) for k, v in dorks.items()}}
        for group, queries in dorks.items():
            for q in queries:
                result.findings.append(
                    Finding(
                        site="google",
                        status=Status.POSSIBLE,
                        category=group,
                        url=f"https://www.google.com/search?q={quote(q)}",
                        reason="ready-to-run search link (not verified)",
                        extra={"query": q},
                    )
                )
        result.duration = time.perf_counter() - started
        return result


class PhoneGoogleCse(BaseModule):
    name = "phone_google_cse"
    description = "Google Programmable Search - web results mentioning the number"
    input_types = ("phone",)
    requires_key = "google_cse"

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        key = self.keys.get("google_cse") if self.keys else None
        cx = self.keys.get("google_cse_cx") if self.keys else None
        if not cx:
            result.error = "google_cse_cx missing"
            result.findings.append(Finding(site="google", status=Status.SKIPPED))
            result.duration = time.perf_counter() - started
            return result
        try:
            resp = await http.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"key": key, "cx": cx, "q": f'"{target}"', "num": 10},
            )
            if resp.status_code != 200:
                result.error = f"google cse returned {resp.status_code}"
                result.findings.append(Finding(site="google", status=Status.ERROR))
            else:
                items = resp.json().get("items", [])
                result.summary = {"results": len(items)}
                if not items:
                    result.findings.append(Finding(site="google", status=Status.NOT_FOUND))
                for item in items:
                    result.findings.append(
                        Finding(
                            site="google",
                            url=item.get("link"),
                            status=Status.FOUND,
                            category="search",
                            extra={
                                "title": item.get("title"),
                                "snippet": (item.get("snippet") or "")[:300],
                            },
                        )
                    )
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="google", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result
