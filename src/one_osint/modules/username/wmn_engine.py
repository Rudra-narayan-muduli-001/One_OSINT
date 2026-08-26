"""WhatsMyName dataset loader and presence-check engine.

Implements the proven dual-marker detection logic: an account is FOUND only
when the exists-markers match (``e_code``/``e_string``) AND the missing
markers do not (``m_code``/``m_string``). Supports GET and POST entries,
username sanitisation (``strip_bad_char``) and custom headers.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...core.http_client import HttpClient
from ...core.paths import DATA_DIR

WMN_FILE = DATA_DIR / "wmn-data.json"
METADATA_FILE = DATA_DIR / "wmn-metadata.json"

_ACCENT_FOLD = str.maketrans(
    "áàâäãåéèêëíìîïóòôöõúùûüñç",
    "aaaaaaeeeeiiiiooooouuuunc",
)


@dataclass(slots=True)
class WmnSite:
    name: str
    uri_check: str
    uri_pretty: str | None = None
    post_body: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    strip_bad_char: str = ""
    e_code: int | None = None
    e_string: str | None = None
    m_code: int | None = None
    m_string: str | None = None
    cat: str = "misc"
    known: list[str] = field(default_factory=list)
    protection: list[str] = field(default_factory=list)
    valid: bool = True

    def sanitize(self, username: str) -> str:
        if self.strip_bad_char:
            for ch in self.strip_bad_char:
                username = username.replace(ch, "")
        return username.strip()


def load_wmn_sites(path: Path | None = None) -> list[WmnSite]:
    src = path or WMN_FILE
    if not src.exists():
        raise FileNotFoundError(f"wmn-data.json not found at {src}")
    data = json.loads(src.read_text(encoding="utf-8"))
    sites: list[WmnSite] = []
    for raw in data.get("sites", []):
        e_code = raw.get("e_code")
        m_code = raw.get("m_code")
        sites.append(
            WmnSite(
                name=raw.get("name", ""),
                uri_check=raw.get("uri_check", ""),
                uri_pretty=raw.get("uri_pretty"),
                post_body=raw.get("post_body"),
                headers=raw.get("headers") or {},
                strip_bad_char=raw.get("strip_bad_char") or "",
                e_code=int(e_code) if e_code is not None else None,
                e_string=raw.get("e_string"),
                m_code=int(m_code) if m_code is not None else None,
                m_string=raw.get("m_string"),
                cat=raw.get("cat", "misc"),
                known=raw.get("known") or [],
                protection=raw.get("protection") or [],
                valid=raw.get("valid", True),
            )
        )
    return sites


@dataclass(slots=True)
class UsernameHit:
    site: str
    url: str
    category: str
    e_code: int | None
    m_code: int | None
    reason: str


_META: dict[str, dict[str, Any]] | None = None


def load_metadata() -> dict[str, dict[str, Any]]:
    """Load wmn-metadata.json (per-site metadata extraction rules)."""
    global _META
    if _META is None:
        if METADATA_FILE.exists():
            _META = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
        else:
            _META = {}
    return _META


def _match(status: int, code: int | None, content: str, string: str | None) -> bool:
    if code is not None and status != code:
        return False
    if string is not None:
        return string in content
    return code is not None


def _fold(value: str) -> str:
    return value.translate(_ACCENT_FOLD).lower()


def check_content_negative(username: str, content: str, site: WmnSite) -> bool:
    """Extra negative heuristic: profile page mentioning 'not found' etc."""
    folded = _fold(content)
    pats = [
        f"user {_fold(username)} not found",
        f"no user named {_fold(username)}",
        f"user '{_fold(username)}' does not exist",
    ]
    return any(p in folded for p in pats)


class WmnChecker:
    """Async presence checker over the full WhatsMyName dataset."""

    def __init__(self, http: HttpClient, max_concurrent: int = 30) -> None:
        self.http = http
        self.sem = asyncio.Semaphore(max_concurrent)
        self.sites = load_wmn_sites()

    async def check_username(
        self, username: str, *, no_nsfw: bool = False
    ) -> list[UsernameHit]:
        import asyncio

        hits: list[UsernameHit] = []
        await asyncio.gather(
            *[self._check_one(username, site, hits, no_nsfw) for site in self.sites]
        )
        hits.sort(key=lambda h: h.site.lower())
        return hits

    async def _check_one(
        self,
        username: str,
        site: WmnSite,
        out: list[UsernameHit],
        no_nsfw: bool,
    ) -> None:
        if not site.valid or "nsfw" in site.cat.lower() and no_nsfw:
            return
        if not site.uri_check or "{account}" not in site.uri_check:
            return
        target = site.sanitize(username)
        url = site.uri_check.replace("{account}", target)
        try:
            async with self.sem:
                if site.post_body:
                    if site.name in _POST_JSON_SITES:
                        body = json.dumps(
                            {
                                k: v.replace("{account}", target)
                                for k, v in _POST_JSON_SITES[site.name].items()
                            }
                        )
                        resp = await self.http.post(
                            url,
                            data=body,
                            headers={**site.headers, "Content-Type": "application/json"},
                            impersonate=self._pick_impersonate(site),
                        )
                    else:
                        resp = await self.http.post(
                            url,
                            data=site.post_body.replace("{account}", target),
                            headers=site.headers,
                            impersonate=self._pick_impersonate(site),
                        )
                else:
                    resp = await self.http.get(
                        url,
                        headers=site.headers,
                        impersonate=self._pick_impersonate(site),
                    )
        except Exception:
            return

        found = _match(resp.status_code, site.e_code, resp.text, site.e_string)
        missing = _match(resp.status_code, site.m_code, resp.text, site.m_string)
        if found and not missing and resp.status_code != site.m_code:
            pretty = site.uri_pretty or url
            pretty = pretty.replace("{account}", target)
            out.append(
                UsernameHit(
                    site=site.name,
                    url=pretty,
                    category=site.cat,
                    e_code=site.e_code,
                    m_code=site.m_code,
                    reason="e_code/e_string match, m_string absent",
                )
            )

    @staticmethod
    def _pick_impersonate(site: WmnSite) -> str | None:
        prot = " ".join(site.protection).lower()
        if "cloudflare" in prot or "captcha" in prot or "bot" in prot:
            return "chrome124"
        return None


#: POST-based sites from the dataset need json bodies instead of form data
_POST_JSON_SITES: dict[str, dict[str, str]] = {
    "AniList": {"query": 'query { User(name: "{account}") { id name } }'},
    "Anime-Planet": {"username": "{account}"},
}
