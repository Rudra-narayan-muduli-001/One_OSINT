"""Email reputation (EmailRep.io) - needs EMAILREP_API_KEY."""

from __future__ import annotations

import time
from urllib.parse import quote

from ...core.config import Settings
from ...core.http_client import get_http_client
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule


class EmailReputation(BaseModule):
    name = "email_reputation"
    description = "EmailRep.io reputation, risk and breach signals"
    input_types = ("email",)
    requires_key = "emailrep"

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        key = self.keys.get("emailrep") if self.keys else None
        try:
            resp = await http.get(
                f"https://emailrep.io/{quote(target, safe='')}",
                headers={"Key": key, "Accept": "application/json"},
            )
            if resp.status_code != 200:
                result.error = f"emailrep.io returned {resp.status_code}"
                result.findings.append(Finding(site="emailrep.io", status=Status.ERROR))
            else:
                d = resp.json()
                result.summary = d
                flags = []
                if d.get("details", {}).get("breached"):
                    flags.append("breached")
                if d.get("details", {}).get("malicious_activity"):
                    flags.append("malicious_activity")
                if d.get("details", {}).get("spam"):
                    flags.append("spam")
                if d.get("details", {}).get("credentials_leaked"):
                    flags.append("credentials_leaked")
                result.findings.append(
                    Finding(
                        site="emailrep.io",
                        status=Status.FOUND if flags else Status.NOT_FOUND,
                        category="intel",
                        extra={
                            "reputation": d.get("reputation"),
                            "suspicious": d.get("suspicious"),
                            "references": d.get("references"),
                            "flags": flags,
                            "first_seen": d.get("details", {}).get("first_seen"),
                            "last_seen": d.get("details", {}).get("last_seen"),
                            "profiles": d.get("details", {}).get("profiles"),
                        },
                    )
                )
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="emailrep.io", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result
