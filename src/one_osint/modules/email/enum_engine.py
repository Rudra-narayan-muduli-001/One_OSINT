"""Email registration-enumeration engine.

Data-driven framework: each site is a declarative spec (endpoint, method,
detection rules, optional recovery-data extraction). Detection follows the
proven pattern - a FOUND verdict requires a positive marker AND no
negative marker. Quiet flows only by default (``loud`` sites must be
opted in via settings).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ...core.http_client import HttpClient


#: markers - kind in {"status", "string", "json", "regex"}
@dataclass(slots=True)
class Rule:
    kind: str
    value: Any
    path: str | None = None  # dot path for json rules

    def matches(self, status: int, content: str, payload: Any) -> bool:
        if self.kind == "status":
            return status == int(self.value)
        if self.kind == "string":
            return self.value in content
        if self.kind == "regex":
            return re.search(self.value, content) is not None
        if self.kind == "json":
            if payload is None:
                return False
            node = payload
            if self.path:
                for part in self.path.split("."):
                    if isinstance(node, dict):
                        node = node.get(part)
                    elif isinstance(node, list) and part.isdigit():
                        idx = int(part)
                        node = node[idx] if idx < len(node) else None
                    else:
                        return False
            want = self.value
            if isinstance(want, bool):
                return bool(node) is want
            return node == want
        return False


#: recovery extraction helpers - return extra dict or None
RecoveryFn = Callable[[int, str, Any], dict[str, Any] | None]

_RE_EMAIL = re.compile(r"([A-Za-z0-9._%+\-*]+\*?@[A-Za-z0-9.\-*]+\.[A-Za-z*]{2,})")
_RE_PHONE = re.compile(r"(\+?[0-9*]{4,}[0-9*]{4,})")


def _recovery_from_body(body: str) -> dict[str, Any] | None:
    out: dict[str, Any] = {}
    m = _RE_EMAIL.search(body)
    if m:
        out["recovery_email"] = m.group(1)
    m = _RE_PHONE.search(body)
    if m is not None and (("recovery_email" not in out) or m.group(1).isdigit()):
        out["recovery_phone"] = m.group(1)
    return out or None


@dataclass(slots=True)
class PreCheck:
    """Acquire cookies before the main request (CSRF flows)."""

    url: str
    cookie_names: tuple[str, ...] = ()


@dataclass(slots=True)
class EnumSite:
    name: str
    category: str
    method: str = "probe"  # probe | register | login | recovery
    url: str = ""
    http_method: str = "GET"
    params: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] | str | None = None
    json_body: dict[str, Any] | None = None
    headers: dict[str, str] = field(default_factory=dict)
    found: list[Rule] = field(default_factory=list)
    not_found: list[Rule] = field(default_factory=list)
    recover: RecoveryFn | None = None
    pre_check: PreCheck | None = None
    input_operation: str | None = None  # hash-sha256 | hash-md5
    loud: bool = False
    impersonate: str | None = None

    def apply_input(self, email: str) -> str:
        if self.input_operation == "hash-sha256":
            return hashlib.sha256(email.encode()).hexdigest()
        if self.input_operation == "hash-md5":
            return hashlib.md5(email.encode()).hexdigest()
        return email


@dataclass(slots=True)
class EmailHit:
    site: str
    category: str
    method: str
    exists: bool
    url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    status: str = "found"  # found | not_found | rate_limited | error | skipped


class EnumEngine:
    """Runs a set of EnumSite definitions against one email."""

    def __init__(self, http: HttpClient, max_concurrent: int = 25) -> None:
        self.http = http
        self.sem = asyncio.Semaphore(max_concurrent)

    async def check_email(
        self,
        email: str,
        sites: list[EnumSite],
        *,
        allow_loud: bool = False,
    ) -> list[EmailHit]:
        hits: list[EmailHit] = []
        await asyncio.gather(
            *[
                self._check_one(email, site, hits, allow_loud) for site in sites
            ]
        )
        hits.sort(key=lambda h: h.site.lower())
        return hits

    async def _check_one(
        self, email: str, site: EnumSite, out: list[EmailHit], allow_loud: bool
    ) -> None:
        if site.loud and not allow_loud:
            out.append(
                EmailHit(
                    site=site.name,
                    category=site.category,
                    method=site.method,
                    exists=False,
                    status="skipped",
                )
            )
            return
        value = site.apply_input(email)
        url = site.url.replace("{input}", value).replace("{email}", email)
        cookies: dict[str, str] = {}
        try:
            async with self.sem:
                if site.pre_check:
                    resp0 = await self.http.get(site.pre_check.url)
                    for name in site.pre_check.cookie_names:
                        if name in resp0.headers.get("Set-Cookie", ""):
                            raw = resp0.headers["Set-Cookie"]
                            m = re.search(rf"(?:^|, ){re.escape(name)}=([^;,\s]+)", raw)
                            if m:
                                cookies[name] = m.group(1)
                headers = dict(site.headers)
                for k, v in cookies.items():
                    headers["Cookie"] = headers.get("Cookie", "") + f"{k}={v}; "
                cookie_val = headers.get("Cookie", "").rstrip("; ")
                if cookie_val:
                    headers["Cookie"] = cookie_val
                else:
                    headers.pop("Cookie", None)
                headers = {
                    k: v.replace("{csrftoken_value}", next(iter(cookies.values()), ""))
                    for k, v in headers.items()
                }

                kwargs: dict[str, Any] = {"headers": headers or None}
                if site.params:
                    kwargs["params"] = {
                        k: str(v).replace("{input}", value).replace("{email}", email)
                        for k, v in site.params.items()
                    }
                if site.data is not None:
                    data = site.data
                    if isinstance(data, dict):
                        data = {
                            k: str(v).replace("{input}", value).replace("{email}", email)
                            for k, v in data.items()
                        }
                    else:
                        data = data.replace("{input}", value).replace("{email}", email)
                    if "csrftoken_value" in str(data):
                        token = next(iter(cookies.values()), "")
                        if isinstance(data, dict):
                            data = {k: str(v).replace("{csrftoken_value}", token) for k, v in data.items()}
                        else:
                            data = data.replace("{csrftoken_value}", token)
                    kwargs["data"] = data
                if site.json_body is not None:
                    kwargs["json"] = _deep_replace(site.json_body, "{input}", value)
                    kwargs["json"] = _deep_replace(kwargs["json"], "{email}", email)
                if site.impersonate:
                    kwargs["impersonate"] = site.impersonate

                resp = await getattr(self.http, site.http_method.lower())(url, **kwargs)
        except Exception as exc:
            out.append(
                EmailHit(
                    site=site.name,
                    category=site.category,
                    method=site.method,
                    exists=False,
                    status="error",
                    extra={"error": str(exc)},
                )
            )
            return

        try:
            payload = resp.json()
        except Exception:
            payload = None

        found = any(r.matches(resp.status_code, resp.text, payload) for r in site.found)
        missing = any(r.matches(resp.status_code, resp.text, payload) for r in site.not_found)
        extra: dict[str, Any] = {}
        if site.recover:
            recovered = site.recover(resp.status_code, resp.text, payload)
            if recovered:
                extra.update(recovered)

        if found and not missing:
            out.append(
                EmailHit(
                    site=site.name,
                    category=site.category,
                    method=site.method,
                    exists=True,
                    url=url,
                    extra=extra,
                    status="found",
                )
            )
        else:
            out.append(
                EmailHit(
                    site=site.name,
                    category=site.category,
                    method=site.method,
                    exists=False,
                    status="not_found",
                )
            )


def _deep_replace(node: Any, token: str, value: str) -> Any:
    if isinstance(node, dict):
        return {k: _deep_replace(v, token, value) for k, v in node.items()}
    if isinstance(node, list):
        return [_deep_replace(v, token, value) for v in node]
    if isinstance(node, str):
        return node.replace(token, value)
    return node
