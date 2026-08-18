"""Structured result types shared across all modules.

Every module returns a list of :class:`Finding` objects plus optional
enrichment data. Findings are unified so the orchestrator, exporters and
web UI all consume one schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    ERROR = "error"
    SKIPPED = "skipped"
    RATE_LIMITED = "rate_limited"
    POSSIBLE = "possible"


class ModuleStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(slots=True)
class Finding:
    """One discrete result row: an account, a record, an entry."""

    site: str
    url: str | None = None
    status: Status = Status.FOUND
    category: str = "misc"
    extra: dict[str, Any] = field(default_factory=dict)
    media: list[str] = field(default_factory=list)
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "url": self.url,
            "status": self.status.value if isinstance(self.status, Status) else str(self.status),
            "category": self.category,
            "extra": self.extra,
            "media": self.media,
            "reason": self.reason,
        }


@dataclass(slots=True)
class ModuleResult:
    """Result bundle returned by one module run."""

    name: str
    findings: list[Finding] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    skipped: bool = False
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "error": self.error,
            "skipped": self.skipped,
            "duration": round(self.duration, 3),
        }
