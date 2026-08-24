"""Email registration-enumeration module."""

from __future__ import annotations

import time

from ...core.config import Settings
from ...core.http_client import get_http_client
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule
from .enum_engine import EnumEngine
from .enum_sites import build_email_sites


class EmailEnumeration(BaseModule):
    name = "email_enumeration"
    description = "40+ site email registration check (quiet flows)"
    input_types = ("email",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        settings = self.settings or Settings()
        engine = EnumEngine(get_http_client(settings), max_concurrent=settings.concurrency)
        sites = build_email_sites()
        hits = await engine.check_email(
            target, sites, allow_loud=settings.allow_loud
        )
        found_count = 0
        for hit in hits:
            if hit.status == "found":
                found_count += 1
                result.findings.append(
                    Finding(
                        site=hit.site,
                        url=hit.url,
                        status=Status.FOUND,
                        category=hit.category,
                        extra=hit.extra or {},
                    )
                )
            elif hit.status == "not_found":
                result.findings.append(
                    Finding(
                        site=hit.site,
                        status=Status.NOT_FOUND,
                        category=hit.category,
                    )
                )
            elif hit.status == "error":
                result.findings.append(
                    Finding(site=hit.site, status=Status.ERROR, category=hit.category)
                )
            elif hit.status == "skipped":
                result.findings.append(
                    Finding(site=hit.site, status=Status.SKIPPED, category=hit.category)
                )
        result.summary = {"sites_checked": len(sites), "registered": found_count}
        result.duration = time.perf_counter() - started
        return result
