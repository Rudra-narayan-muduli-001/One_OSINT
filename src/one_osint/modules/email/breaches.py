"""Breach databases: HIBP, BreachDirectory, IntelX, psbdmp, Hudson Rock."""

from __future__ import annotations

import time

from ...core.config import Settings
from ...core.http_client import get_http_client
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule


class BreachHibp(BaseModule):
    name = "breach_hibp"
    description = "HaveIBeenPwned v3 breached-account + pastes"
    input_types = ("email",)
    requires_key = "hibp"

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        key = self.keys.get("hibp") if self.keys else None
        try:
            resp = await http.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{target}",
                headers={"hibp-api-key": key, "user-agent": "one-osint"},
            )
            if resp.status_code == 404:
                result.summary = {"breaches": []}
                result.findings.append(Finding(site="hibp", status=Status.NOT_FOUND, category="breach"))
            elif resp.status_code != 200:
                result.error = f"hibp returned {resp.status_code}"
                result.findings.append(Finding(site="hibp", status=Status.ERROR, category="breach"))
            else:
                breaches = resp.json()
                result.summary = {"breaches": len(breaches)}
                for b in breaches:
                    result.findings.append(
                        Finding(
                            site="hibp",
                            status=Status.FOUND,
                            category="breach",
                            extra={
                                "breach": b.get("Title"),
                                "domain": b.get("Domain"),
                                "breach_date": b.get("BreachDate"),
                                "added_date": b.get("AddedDate"),
                                "data_classes": b.get("DataClasses"),
                                "description": (b.get("Description") or "")[:300],
                            },
                        )
                    )
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="hibp", status=Status.ERROR, category="breach"))
        result.duration = time.perf_counter() - started
        return result


class BreachDirectory(BaseModule):
    name = "breach_directory"
    description = "BreachDirectory via RapidAPI - sources + leaked passwords"
    input_types = ("email",)
    requires_key = "breachdirectory"

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        key = self.keys.get("breachdirectory") if self.keys else None
        try:
            resp = await http.get(
                f"https://breachdirectory.p.rapidapi.com/?func=auto&term={target}",
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "breachdirectory.p.rapidapi.com"},
            )
            if resp.status_code != 200:
                result.error = f"breachdirectory returned {resp.status_code}"
                result.findings.append(Finding(site="breachdirectory", status=Status.ERROR))
            else:
                d = resp.json()
                result.summary = {"found": d.get("found")}
                entries = d.get("result", [])
                for entry in entries[:20]:
                    result.findings.append(
                        Finding(
                            site="breachdirectory",
                            status=Status.FOUND,
                            category="breach",
                            extra={
                                "sources": entry.get("sources"),
                                "sha1": entry.get("sha1"),
                                "hash": entry.get("hash"),
                                "password": entry.get("password"),
                            },
                        )
                    )
                if not entries:
                    result.findings.append(Finding(site="breachdirectory", status=Status.NOT_FOUND))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="breachdirectory", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class BreachIntelX(BaseModule):
    name = "breach_intelx"
    description = "Intelligence X - breach/paste URLs for the email"
    input_types = ("email",)
    requires_key = "intelx"

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        key = self.keys.get("intelx") if self.keys else None
        try:
            resp = await http.post(
                "https://2.intelx.io/intelligent/search",
                json={"term": target, "maxresults": 20, "media": 0, "sort": 2, "terminate": []},
                headers={"x-key": key},
            )
            if resp.status_code != 200:
                result.error = f"intelx returned {resp.status_code}"
                result.findings.append(Finding(site="intelx", status=Status.ERROR))
            else:
                d = resp.json()
                count = d.get("totalresults", 0)
                result.summary = {"results": count}
                if count == 0:
                    result.findings.append(Finding(site="intelx", status=Status.NOT_FOUND))
                else:
                    for rec in (d.get("records") or [])[:20]:
                        result.findings.append(
                            Finding(
                                site="intelx",
                                status=Status.FOUND,
                                category="breach",
                                extra={
                                    "name": rec.get("name"),
                                    "media": rec.get("media"),
                                    "date": rec.get("date"),
                                    "type": rec.get("type"),
                                },
                            )
                        )
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="intelx", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class PastebinSearch(BaseModule):
    name = "pastebin_search"
    description = "psbdmp.ws - pastebin dumps containing the email"
    input_types = ("email",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        try:
            resp = await http.get(f"https://psbdmp.ws/api/v3/search/{target}")
            if resp.status_code != 200:
                result.error = f"psbdmp returned {resp.status_code}"
                result.findings.append(Finding(site="psbdmp", status=Status.ERROR))
            else:
                d = resp.json()
                data = d.get("data") or []
                result.summary = {"dumps": len(data)}
                if not data:
                    result.findings.append(Finding(site="psbdmp", status=Status.NOT_FOUND))
                for item in data[:20]:
                    result.findings.append(
                        Finding(
                            site="psbdmp",
                            url=f"https://psbdmp.ws/dump/{item.get('id')}",
                            status=Status.FOUND,
                            category="paste",
                            extra={"id": item.get("id"), "tags": item.get("tags"), "date": item.get("time")},
                        )
                    )
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="psbdmp", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class HudsonRockStealer(BaseModule):
    name = "hudsonrock_stealer"
    description = "Hudson Rock - infostealer malware log compromise lookup"
    input_types = ("email",)
    opt_in = True
    requires_key = "hudsonrock"

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        key = self.keys.get("hudsonrock") if self.keys else None
        headers = {"api-key": key} if key else {}
        try:
            resp = await http.get(
                f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-email?email={target}",
                headers=headers,
            )
            if resp.status_code != 200:
                result.error = f"hudsonrock returned {resp.status_code}"
                result.findings.append(Finding(site="hudsonrock", status=Status.ERROR))
            else:
                d = resp.json()
                if d.get("pwned"):
                    for hit in (d.get("stealers") or [])[:10]:
                        result.findings.append(
                            Finding(
                                site="hudsonrock",
                                status=Status.FOUND,
                                category="stealer",
                                extra={
                                    "malware": hit.get("malware_path"),
                                    "compromise_date": hit.get("compromised_data_date"),
                                    "computer": hit.get("computer_name"),
                                    "os": hit.get("operating_system"),
                                    "antiviruses": hit.get("antivirus"),
                                    "logins": hit.get("number_of_logins"),
                                },
                            )
                        )
                    result.summary = {"stealer_infections": len(d.get("stealers") or [])}
                else:
                    result.summary = {"stealer_infections": 0}
                    result.findings.append(Finding(site="hudsonrock", status=Status.NOT_FOUND))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="hudsonrock", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result
