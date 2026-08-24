"""Domain pivot from email: DNS records, MX validation, SPF/DMARC, IP geo."""

from __future__ import annotations

import asyncio
import time

import dns.asyncresolver
import dns.rdatatype

from ...core.config import Settings
from ...core.detect import domain_from_email
from ...core.http_client import get_http_client
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule


async def _resolve(domain: str, rtype: str) -> list[str]:
    try:
        answers = await dns.asyncresolver.resolve(domain, rtype, lifetime=8)
        return sorted({str(r) for r in answers})
    except Exception:
        return []


class DnsPivot(BaseModule):
    name = "dns_pivot"
    description = "DNS records for the email domain (A, MX, TXT/SPF, DMARC, NS)"
    input_types = ("email", "domain")

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        domain = domain_from_email(target) if "@" in target else target
        a_records, mx, txt, ns = await asyncio.gather(
            _resolve(domain, "A"),
            _resolve(domain, "MX"),
            _resolve(domain, "TXT"),
            _resolve(domain, "NS"),
        )
        spf = [t for t in txt if t.startswith("v=spf1")]
        dkim_dmarc, _ = await asyncio.gather(
            _resolve(f"_dmarc.{domain}", "TXT"), asyncio.sleep(0)
        )
        dmarc = [t for t in dkim_dmarc if t.startswith("v=DMARC1")]

        summary = {
            "domain": domain,
            "a_records": a_records,
            "mx": mx,
            "spf": spf,
            "dmarc": dmarc,
            "ns": ns,
        }
        result.summary = summary
        for mx_host in mx:
            result.findings.append(
                Finding(
                    site="dns", status=Status.FOUND, category="dns",
                    extra={"type": "MX", "domain": domain, "value": mx_host},
                )
            )
        if spf:
            result.findings.append(Finding(
                site="dns", status=Status.FOUND, category="dns",
                extra={"type": "SPF", "domain": domain, "value": spf[0]},
            ))
        if dmarc:
            result.findings.append(Finding(
                site="dns", status=Status.FOUND, category="dns",
                extra={"type": "DMARC", "domain": domain, "value": dmarc[0]},
            ))
        if not (mx or spf or a_records):
            result.findings.append(Finding(site="dns", status=Status.NOT_FOUND, category="dns"))
        result.duration = time.perf_counter() - started
        return result


class IpGeolocation(BaseModule):
    name = "ip_geolocation"
    description = "Geolocation + ASN/org for the email domain's IP (ipapi.co)"
    input_types = ("email", "domain", "ip")

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        try:
            resp = await http.get(f"https://ipapi.co/{target}/json/")
            if resp.status_code != 200:
                result.error = f"ipapi.co returned {resp.status_code}"
                result.findings.append(Finding(site="ipapi.co", status=Status.ERROR))
            else:
                d = resp.json()
                if d.get("error"):
                    result.findings.append(Finding(site="ipapi.co", status=Status.NOT_FOUND))
                else:
                    result.summary = d
                    result.findings.append(
                        Finding(
                            site="ipapi.co",
                            status=Status.FOUND,
                            category="geo",
                            extra={
                                "ip": d.get("ip"),
                                "city": d.get("city"),
                                "region": d.get("region"),
                                "country": d.get("country_name"),
                                "timezone": d.get("timezone"),
                                "org": d.get("org"),
                                "asn": d.get("asn"),
                                "latitude": d.get("latitude"),
                                "longitude": d.get("longitude"),
                            },
                        )
                    )
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="ipapi.co", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class SmtpVerifier(BaseModule):
    name = "smtp_verify"
    description = "SMTP RCPT TO probing against the domain's MX servers"
    input_types = ("email",)
    opt_in = True

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        domain = domain_from_email(target)
        mx = await _resolve(domain, "MX")
        if not mx:
            result.summary = {"skipped": "no MX records"}
            result.findings.append(Finding(site="smtp", status=Status.SKIPPED, category="smtp"))
            result.duration = time.perf_counter() - started
            return result
        host = mx[0].split()[-1].rstrip(".")
        try:
            verdict = await asyncio.to_thread(self._probe, host, target)
        except Exception as exc:
            result.error = str(exc)
            verdict = "error"
        result.summary = {"mx_host": host, "verdict": verdict}
        status_map = {
            "exists": Status.FOUND,
            "not_found": Status.NOT_FOUND,
            "blocked": Status.SKIPPED,
        }
        result.findings.append(
            Finding(
                site="smtp",
                status=status_map.get(verdict, Status.ERROR),
                category="smtp",
                extra={"mx_host": host, "verdict": verdict},
            )
        )
        result.duration = time.perf_counter() - started
        return result

    @staticmethod
    def _probe(host: str, email: str) -> str:
        import smtplib

        try:
            with smtplib.SMTP(host, 25, timeout=8) as smtp:
                smtp.ehlo("one-osint.local")
                code, _ = smtp.mail("probe@one-osint.local")
                if code not in (250, 252):
                    return "blocked"
                code, _ = smtp.rcpt(email)
                if code in (250, 252, 551):
                    return "exists"
                if code in (550, 553):
                    return "not_found"
                return "blocked"
        except OSError:
            return "blocked"
