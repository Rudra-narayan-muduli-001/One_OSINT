"""High-value curated username checkers (GitHub, Reddit, X, Mastodon, etc.).

These complement the WMN dataset with metadata extraction (name, bio,
followers, avatar) - data the dataset does not provide.
"""

from __future__ import annotations

import time

from ...core.config import Settings
from ...core.http_client import get_http_client
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule


async def _github_check(http, username: str) -> Finding:
    resp = await http.get(f"https://api.github.com/users/{username}", impersonate=None)
    if resp.status_code == 404:
        return Finding(site="github", status=Status.NOT_FOUND, category="dev")
    if resp.status_code != 200:
        return Finding(site="github", status=Status.ERROR, category="dev")
    d = resp.json()
    return Finding(
        site="github",
        url=d.get("html_url"),
        status=Status.FOUND,
        category="dev",
        extra={
            "name": d.get("name"),
            "bio": d.get("bio"),
            "followers": d.get("followers"),
            "following": d.get("following"),
            "repos": d.get("public_repos"),
            "location": d.get("location"),
            "company": d.get("company"),
            "blog": d.get("blog"),
            "created_at": d.get("created_at"),
            "avatar": d.get("avatar_url"),
        },
        media=[d["avatar_url"]] if d.get("avatar_url") else [],
    )


class UsernameGithub(BaseModule):
    name = "username_github"
    description = "GitHub profile + metadata via public API"
    input_types = ("username",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        try:
            finding = await _github_check(http, target)
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="github", status=Status.ERROR))
        else:
            result.findings.append(finding)
        result.duration = time.perf_counter() - started
        return result


class UsernameReddit(BaseModule):
    name = "username_reddit"
    description = "Reddit profile + karma via public JSON API"
    input_types = ("username",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        try:
            resp = await http.get(f"https://www.reddit.com/user/{target}/about.json")
            if resp.status_code == 404:
                result.findings.append(Finding(site="reddit", status=Status.NOT_FOUND))
            elif resp.status_code == 200:
                d = resp.json().get("data", {})
                result.findings.append(
                    Finding(
                        site="reddit",
                        url=f"https://www.reddit.com/user/{target}",
                        status=Status.FOUND,
                        category="social",
                        extra={
                            "name": d.get("subreddit", {}).get("title"),
                            "karma": d.get("total_karma"),
                            "link_karma": d.get("link_karma"),
                            "comment_karma": d.get("comment_karma"),
                            "created_utc": d.get("created_utc"),
                            "verified": d.get("verified"),
                        },
                    )
                )
            else:
                result.findings.append(Finding(site="reddit", status=Status.ERROR))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="reddit", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class UsernameMastodon(BaseModule):
    name = "username_mastodon"
    description = "Mastodon account discovery on mastodon.social"
    input_types = ("username",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        try:
            resp = await http.get(
                "https://mastodon.social/api/v2/search",
                params={"q": target, "resolve": "true", "limit": 5},
            )
            if resp.status_code == 200:
                accounts = resp.json().get("accounts", [])
                for acc in accounts:
                    if acc.get("username", "").lower() == target.lower():
                        result.findings.append(
                            Finding(
                                site="mastodon",
                                url=acc.get("url"),
                                status=Status.FOUND,
                                category="social",
                                extra={
                                    "display_name": acc.get("display_name"),
                                    "note": (acc.get("note") or "").strip()[:200],
                                    "followers": acc.get("followers_count"),
                                    "following": acc.get("following_count"),
                                    "posts": acc.get("statuses_count"),
                                    "created_at": acc.get("created_at"),
                                },
                                media=[acc["avatar"] or ""] if acc.get("avatar") else [],
                            )
                        )
                if not result.findings:
                    result.findings.append(Finding(site="mastodon", status=Status.NOT_FOUND))
            else:
                result.findings.append(Finding(site="mastodon", status=Status.ERROR))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="mastodon", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result
