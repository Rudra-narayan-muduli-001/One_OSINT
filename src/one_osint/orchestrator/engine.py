"""Investigation orchestrator.

Runs a phased pipeline over the auto-discovered modules with asyncio
concurrency, per-module timeouts, optional streaming of events, and
persistence to SQLite.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ..core.config import KeyVault, Settings
from ..core.detect import InputType
from ..core.result import ModuleResult
from ..core.storage import Storage
from ..modules.base import BaseModule, discover_modules, get_modules_for

EventSink = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(slots=True)
class Investigation:
    target: str
    input_type: InputType
    settings: Settings
    keys: KeyVault
    modules: list[str] = field(default_factory=list)
    allow_opt_in: bool = False
    event_sink: EventSink | None = None
    storage: Storage | None = None

    #: per-phase output filled during run
    results: list[ModuleResult] = field(default_factory=list)
    pivots: dict[str, list[str]] = field(default_factory=dict)

    async def _emit(self, event: dict[str, Any]) -> None:
        if self.event_sink:
            try:
                await self.event_sink(event)
            except Exception:
                pass

    async def run(self) -> dict[str, Any]:
        inv_id = None
        if self.storage:
            inv_id = self.storage.create_investigation(self.target, self.input_type.value)

        modules = self._build_pipeline()
        await self._emit({"type": "investigation_start", "target": self.target,
                          "input_type": self.input_type.value, "modules": [m.name for m in modules]})

        sem = asyncio.Semaphore(self.settings.concurrency)

        async def run_one(module: BaseModule) -> ModuleResult:
            async with sem:
                await self._emit({"type": "module_start", "module": module.name})
                t0 = time.perf_counter()
                try:
                    res = await asyncio.wait_for(
                        module.check(self.target), timeout=max(60, self.settings.timeout * 4)
                    )
                except TimeoutError:
                    res = ModuleResult(name=module.name, error="timeout")
                except Exception as exc:
                    res = ModuleResult(name=module.name, error=str(exc))
                res.duration = time.perf_counter() - t0
                await self._emit({
                    "type": "module_done",
                    "module": module.name,
                    "error": res.error,
                    "findings": len(res.findings),
                    "summary": res.summary,
                    "duration": round(res.duration, 3),
                })
                if self.storage and inv_id:
                    self.storage.save_module_run(
                        inv_id, module.name,
                        "error" if res.error else ("done" if not res.skipped else "skipped"),
                        res.duration, res.to_dict(),
                    )
                return res

        # Phase 1: primary modules (all matching input type)
        primary = [m for m in modules if self.input_type.value in m.input_types]
        secondary = [m for m in modules if m not in primary]

        results = await asyncio.gather(*[run_one(m) for m in primary])
        self.results = list(results)

        # Phase 2: pivots - derive new targets from findings
        await self._run_pivots(modules, run_one)

        # Phase 3: secondary modules (e.g. domain checks on the email's domain)
        if secondary:
            extra = await asyncio.gather(*[run_one(m) for m in secondary])
            self.results.extend(extra)

        report = self.build_report()
        if self.storage and inv_id:
            self.storage.update_investigation(inv_id, "done", report)
        await self._emit({"type": "investigation_done", "target": self.target,
                          "investigation_id": inv_id})
        return report

    def _build_pipeline(self) -> list[BaseModule]:
        if self.modules:
            wanted = set(self.modules)
            out = []
            for name, cls in sorted(discover_modules().items()):
                if name in wanted:
                    mod = cls(keys=self.keys, settings=self.settings)
                    out.append(mod)
            return out
        return get_modules_for(
            self.input_type.value,
            keys=self.keys,
            settings=self.settings,
            allow_opt_in=self.allow_opt_in,
        )

    async def _run_pivots(self, modules: list[BaseModule], run_one) -> None:
        """Collect derived pivot targets (emails/usernames/domains) for the report."""
        self.pivots["emails"] = _collect_field(self.results, "emails")
        self.pivots["usernames"] = _collect_field(self.results, "usernames")
        self.pivots["domains"] = _collect_field(self.results, "domains")
        self.pivots["phones"] = _collect_field(self.results, "phones")

    def build_report(self) -> dict[str, Any]:
        modules_out = []
        for res in self.results:
            modules_out.append(res.to_dict())
        return {
            "target": self.target,
            "input_type": self.input_type.value,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pivots": self.pivots,
            "modules": modules_out,
            "found_accounts": sum(
                1 for res in self.results for f in res.findings
                if f.status.value == "found"
            ),
            "module_count": len(self.results),
        }


def _collect_field(results: list[ModuleResult], field_name: str) -> list[str]:
    values: set[str] = set()
    for res in results:
        for f in res.findings:
            if f.extra and isinstance(f.extra, dict):
                v = f.extra.get(field_name)
                if isinstance(v, str) and v:
                    values.add(v.lower())
    return sorted(values)
