"""Domain intelligence: certificate transparency, brute force, takeover, ASN."""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

import dns.asyncresolver
import dns.rdatatype

from ...core.config import Settings
from ...core.http_client import get_http_client
from ...core.paths import CACHE_DIR, DATA_DIR
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule

_SUBDOMAIN_RE = re.compile(r"^(?:\*\.)?([a-z0-9](?:[a-z0-9\-]*[a-z0-9])?\.)+[a-z]{2,}$", re.I)


def _dedup(values: list[str]) -> list[str]:
    return sorted({v.lower().rstrip(".") for v in values})


class CertTransparency(BaseModule):
    name = "domain_crt"
    description = "Certificate transparency subdomains (crt.sh, certspotter)"
    input_types = ("domain",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        hosts: set[str] = set()
        try:
            resp = await http.get(
                f"https://crt.sh/?q=%25.{target}&output=json", timeout=30
            )
            if resp.status_code == 200:
                try:
                    rows = resp.json()
                except Exception:
                    rows = []
                for row in rows:
                    for name in (row.get("name_value") or "").splitlines():
                        name = name.strip().lower()
                        if name.endswith("." + target) and _SUBDOMAIN_RE.match(name):
                            hosts.add(name)
        except Exception as exc:
            result.error = str(exc)
        if self.keys and self.keys.has("certspotter"):
            try:
                resp = await http.get(
                    f"https://api.certspotter.com/v1/issuances?domain={target}&include_subdomains=true&expand=dns_names",
                    headers={"Authorization": f"Bearer {self.keys.get('certspotter')}"},
                )
                if resp.status_code == 200:
                    for row in resp.json():
                        for name in row.get("dns_names", []):
                            name = name.strip().lower().lstrip("*.")
                            if name.endswith("." + target):
                                hosts.add(name)
            except Exception:
                pass
        result.summary = {"subdomains": len(hosts)}
        if not hosts:
            result.findings.append(Finding(site="crt.sh", status=Status.NOT_FOUND, category="domain"))
        for host in sorted(hosts):
            result.findings.append(
                Finding(site="crt.sh", url=f"https://{host}", status=Status.FOUND, category="domain")
            )
        result.duration = time.perf_counter() - started
        return result


class DnsBrute(BaseModule):
    name = "domain_dns_brute"
    description = "Subdomain brute force from wordlist with DNS resolution"
    input_types = ("domain",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        wordlist = Path(DATA_DIR / "dns-names.txt")
        words = [
            w.strip().lower()
            for w in wordlist.read_text(encoding="utf-8", errors="ignore").splitlines()
            if w.strip()
        ]
        settings = self.settings or Settings()
        sem = asyncio.Semaphore(max(10, settings.concurrency // 2))
        found: list[str] = []

        async def probe(word: str) -> None:
            async with sem:
                name = f"{word}.{target}"
                try:
                    answers = await dns.asyncresolver.resolve(name, "A", lifetime=6)
                    ips = sorted({str(r) for r in answers})
                    if ips:
                        found.append(f"{name} ({','.join(ips)})")
                except Exception:
                    pass

        await asyncio.gather(*[probe(w) for w in words])
        result.summary = {"wordlist": len(words), "resolved": len(found)}
        if not found:
            result.findings.append(Finding(site="dns_brute", status=Status.NOT_FOUND, category="domain"))
        for entry in found:
            host = entry.split(" ")[0]
            result.findings.append(
                Finding(site="dns_brute", url=f"https://{host}", status=Status.FOUND, category="domain")
            )
        result.duration = time.perf_counter() - started
        return result


class SubdomainTakeover(BaseModule):
    name = "domain_takeover"
    description = "Subdomain takeover fingerprint check (can-i-take-over-xyz)"
    input_types = ("domain",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        fingerprints = _load_fingerprints()
        if not fingerprints:
            try:
                resp = await http.get(
                    "https://raw.githubusercontent.com/EdOverflow/can-i-take-over-xyz/master/fingerprints.json",
                    timeout=15,
                )
                if resp.status_code == 200:
                    fingerprints = resp.json()
                    _cache_fingerprints(fingerprints)
            except Exception:
                fingerprints = []
        if not fingerprints:
            result.error = "fingerprints unavailable"
            result.findings.append(Finding(site="takeover", status=Status.ERROR, category="domain"))
            result.duration = time.perf_counter() - started
            return result

        cname_vuln: set[str] = set()
        for fp in fingerprints:
            if not fp.get("vulnerable", False):
                continue
            cname = fp.get("cname")
            candidates = cname if isinstance(cname, list) else [cname]
            for c in candidates:
                if isinstance(c, str) and c and c != "cname":
                    cname_vuln.add(c.strip().rstrip(".").lower())
        hits = []
        for cname in cname_vuln:
            host = f"{_slug(cname)}.{target}"
            try:
                answers = await dns.asyncresolver.resolve(host, "CNAME", lifetime=5)
                if any(str(r).rstrip(".").lower().endswith(cname) for r in answers):
                    hits.append((host, cname))
            except Exception:
                pass
        result.summary = {"fingerprints": len(fingerprints), "takeovers": len(hits)}
        if not hits:
            result.findings.append(Finding(site="takeover", status=Status.NOT_FOUND, category="domain"))
        for host, cname in hits:
            result.findings.append(
                Finding(site="takeover", url=f"https://{host}", status=Status.FOUND, category="domain",
                        extra={"cname": cname})
            )
        result.duration = time.perf_counter() - started
        return result


_FP_CACHE = CACHE_DIR / "takeover_fingerprints.json"


def _load_fingerprints() -> list[dict]:
    if _FP_CACHE.exists():
        try:
            return json.loads(_FP_CACHE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _cache_fingerprints(data: list[dict]) -> None:
    _FP_CACHE.write_text(json.dumps(data), encoding="utf-8")


def _slug(cname: str) -> str:
    part = cname.split(".")[0].lower()
    return "x" if not part or not part.isalnum() else part


class AsnLookup(BaseModule):
    name = "domain_asn"
    description = "ASN discovery for the domain's IPs (hackertarget)"
    input_types = ("domain",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        try:
            resp = await http.get(f"https://api.hackertarget.com/aslookup/?q={target}", timeout=20)
            if resp.status_code == 200:
                lines = [line for line in resp.text.splitlines() if line.strip()]
                if lines and "error" not in lines[0].lower():
                    result.summary = {"asn_records": len(lines)}
                    for line in lines:
                        parts = line.split("|")
                        if len(parts) >= 2:
                            result.findings.append(
                                Finding(
                                    site="hackertarget", status=Status.FOUND, category="asn",
                                    extra={"asn": parts[0].strip(), "range": parts[1].strip()},
                                )
                            )
                else:
                    result.findings.append(Finding(site="hackertarget", status=Status.NOT_FOUND))
            else:
                result.findings.append(Finding(site="hackertarget", status=Status.ERROR))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="hackertarget", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class SubdomainPassive(BaseModule):
    name = "domain_passive"
    description = "Passive subdomain sources (rapiddns, hackertarget, otx, anubis)"
    input_types = ("domain",)

    async def check(self, target: str) -> ModuleResult:
        target = target.strip().lower()
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        hosts: set[str] = set()

        async def from_rapiddns() -> None:
            try:
                resp = await http.get(f"https://rapiddns.io/subdomain/{target}?full=1", timeout=20)
                if resp.status_code == 200:
                    for m in re.finditer(r"([a-z0-9](?:[a-z0-9\-]*[a-z0-9])?\.)+" + re.escape(target), resp.text.lower()):
                        hosts.add(m.group(0))
            except Exception:
                pass

        async def from_hackertarget() -> None:
            try:
                resp = await http.get(f"https://api.hackertarget.com/hostsearch/?q={target}", timeout=20)
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        host = line.split(",")[0].strip().lower()
                        if host.endswith("." + target):
                            hosts.add(host)
            except Exception:
                pass

        async def from_otx() -> None:
            headers = {}
            if self.keys and self.keys.has("otx"):
                headers = {"X-OTX-API-KEY": self.keys.get("otx")}
            try:
                resp = await http.get(
                    f"https://otx.alienvault.com/api/v1/indicators/domain/{target}/passive_dns",
                    headers=headers, timeout=20,
                )
                if resp.status_code == 200:
                    for rec in resp.json().get("passive_dns", []):
                        host = (rec.get("hostname") or "").strip().lower()
                        if host.endswith("." + target):
                            hosts.add(host)
            except Exception:
                pass

        async def from_anubis() -> None:
            try:
                resp = await http.get(f"https://jldc.me/anubis/subdomains/{target}", timeout=20)
                if resp.status_code == 200:
                    for host in resp.json():
                        if isinstance(host, str) and host.lower().endswith("." + target):
                            hosts.add(host.lower())
            except Exception:
                pass

        await asyncio.gather(from_rapiddns(), from_hackertarget(), from_otx(), from_anubis())
        result.summary = {"subdomains": len(hosts)}
        if not hosts:
            result.findings.append(Finding(site="passive", status=Status.NOT_FOUND, category="domain"))
        for host in sorted(hosts):
            result.findings.append(
                Finding(site="passive", url=f"https://{host}", status=Status.FOUND, category="domain")
            )
        result.duration = time.perf_counter() - started
        return result
