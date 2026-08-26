"""IP intelligence: WHOIS, Shodan host/ports, DNS reverse, DNSInf bundle."""

from __future__ import annotations

import time

from ...core.config import Settings
from ...core.http_client import get_http_client
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule


class IpWhois(BaseModule):
    name = "ip_whois"
    description = "WHOIS registration data for the IP (arin/ipwhois)"
    input_types = ("ip", "domain")

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        try:
            resp = await http.get(f"https://ipwhois.app/json/{target}", timeout=20)
            if resp.status_code != 200:
                result.error = f"ipwhois.app returned {resp.status_code}"
                result.findings.append(Finding(site="ipwhois", status=Status.ERROR))
            else:
                d = resp.json()
                if d.get("success") is False:
                    result.findings.append(Finding(site="ipwhois", status=Status.NOT_FOUND))
                else:
                    result.summary = d
                    result.findings.append(
                        Finding(
                            site="ipwhois", status=Status.FOUND, category="whois",
                            extra={
                                "ip": d.get("ip"),
                                "type": d.get("type"),
                                "continent": d.get("continent"),
                                "country": d.get("country"),
                                "region": d.get("region"),
                                "city": d.get("city"),
                                "org": d.get("org"),
                                "asn": d.get("asn"),
                                "isp": d.get("isp"),
                                "timezone": d.get("timezone"),
                            },
                        )
                    )
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="ipwhois", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class IpShodan(BaseModule):
    name = "ip_shodan"
    description = "Shodan host lookup - ports, banners, CVEs"
    input_types = ("ip",)
    requires_key = "shodan"

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        key = self.keys.get("shodan") if self.keys else None
        try:
            resp = await http.get(
                f"https://api.shodan.io/shodan/host/{target}",
                params={"key": key},
                timeout=20,
            )
            if resp.status_code != 200:
                result.error = f"shodan returned {resp.status_code}"
                result.findings.append(Finding(site="shodan", status=Status.ERROR))
            else:
                d = resp.json()
                result.summary = {
                    "ports": d.get("ports", []),
                    "vulns": d.get("vulns", []),
                    "hostnames": d.get("hostnames", []),
                    "org": d.get("org"),
                    "os": d.get("os"),
                }
                for port in d.get("ports", []):
                    result.findings.append(
                        Finding(site="shodan", status=Status.FOUND, category="ports",
                                extra={"port": port})
                    )
                for vuln in d.get("vulns", []):
                    result.findings.append(
                        Finding(site="shodan", status=Status.FOUND, category="vulns",
                                extra={"cve": vuln})
                    )
                if not result.findings:
                    result.findings.append(Finding(site="shodan", status=Status.NOT_FOUND))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="shodan", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class IpReverseDns(BaseModule):
    name = "ip_reverse_dns"
    description = "Reverse DNS (PTR) lookup for an IP"
    input_types = ("ip",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        import dns.asyncresolver

        try:
            answers = await dns.asyncresolver.resolve_address(target, lifetime=8)
            names = [str(r).rstrip(".") for r in answers]
            result.summary = {"ptr": names}
            for name in names:
                result.findings.append(
                    Finding(site="dns", url=f"https://{name}", status=Status.FOUND,
                            category="dns", extra={"type": "PTR", "ip": target, "value": name})
                )
            if not names:
                result.findings.append(Finding(site="dns", status=Status.NOT_FOUND, category="dns"))
        except Exception as exc:
            from dns.exception import DNSException

            nxdomain = isinstance(exc, DNSException) and "NXDOMAIN" in str(getattr(exc, "codes", ()) or "") or "NXDOMAIN" in str(exc)
            if not nxdomain:
                result.error = str(exc)
            result.findings.append(
                Finding(site="dns", status=Status.NOT_FOUND if nxdomain else Status.ERROR, category="dns")
            )
        result.duration = time.perf_counter() - started
        return result
