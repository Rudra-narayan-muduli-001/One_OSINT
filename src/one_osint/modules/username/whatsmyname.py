"""Username presence module - 700+ sites via the WhatsMyName dataset."""

from __future__ import annotations

import time

from ...core.config import Settings
from ...core.http_client import get_http_client
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule
from .wmn_engine import WmnChecker


class UsernameWmn(BaseModule):
    name = "username_whatsmyname"
    description = "700+ site username presence check (WhatsMyName dataset)"
    input_types = ("username",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        settings = self.settings or Settings()
        checker = WmnChecker(
            get_http_client(settings), max_concurrent=settings.concurrency
        )
        hits = await checker.check_username(target)
        for hit in hits:
            result.findings.append(
                Finding(
                    site=hit.site,
                    url=hit.url,
                    status=Status.FOUND,
                    category=hit.category,
                    reason=hit.reason,
                )
            )
        result.summary = {"sites_checked": len(checker.sites), "accounts_found": len(hits)}
        result.duration = time.perf_counter() - started
        return result
