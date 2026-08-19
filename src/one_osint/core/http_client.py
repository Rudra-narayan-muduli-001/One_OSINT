"""Stealth HTTP client.

- curl_cffi Chrome impersonation for bot-walled endpoints
- httpx (HTTP/2) for the rest
- per-request random User-Agent (or fixed), proxy rotation, retries,
  session-scoped cookie handling
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .useragent import random_user_agent

try:  # optional heavy dependency - fall back to httpx if unavailable
    from curl_cffi import requests as curl_requests

    _HAS_CURL = True
except ImportError:  # pragma: no cover
    _HAS_CURL = False


@dataclass(slots=True)
class Response:
    status_code: int
    text: str
    headers: dict[str, str]
    url: str

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def json(self) -> Any:
        import json

        return json.loads(self.text)

    def contains(self, markers: list[str] | str) -> bool:
        if isinstance(markers, str):
            return markers in self.text
        return any(m in self.text for m in markers)


class HttpClient:
    """Async HTTP client with stealth + proxy + retry. Thread-safe per task."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self._clients: dict[bool, httpx.AsyncClient] = {}
        self._session = asyncio.Lock()

    async def _get_client(self, http2: bool = True) -> httpx.AsyncClient:
        async with self._session:
            if http2 not in self._clients:
                self._clients[http2] = httpx.AsyncClient(
                    http2=http2,
                    verify=self.settings.verify_tls,
                    timeout=httpx.Timeout(self.settings.timeout),
                    follow_redirects=True,
                    headers={"Accept-Language": "en-US,en;q=0.9"},
                )
            return self._clients[http2]

    def _pick_proxy(self) -> str | None:
        if self.settings.tor:
            return "socks5h://127.0.0.1:9050"
        if self.settings.proxies:
            if self.settings.proxy_rotate:
                return random.choice(self.settings.proxies)
            return self.settings.proxies[0]
        return None

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | str | None = None,
        json: dict[str, Any] | None = None,
        impersonate: str | None = None,
        timeout: float | None = None,
        http2: bool = True,
    ) -> Response:
        hdrs = dict(headers or {})
        if self.settings.user_agent_rotate and "User-Agent" not in hdrs:
            hdrs["User-Agent"] = random_user_agent()
        proxy = self._pick_proxy()

        if impersonate and _HAS_CURL:
            # curl_cffi sync - run in a thread executor to keep the event loop free
            return await asyncio.to_thread(
                self._curl_request,
                method,
                url,
                headers=hdrs,
                params=params,
                data=data,
                json=json,
                impersonate=impersonate,
                timeout=timeout,
                proxy=proxy,
            )

        client = await self._get_client(http2=http2)
        client.headers.update({k: v for k, v in hdrs.items() if k.lower() != "user-agent"})
        try:
            if "User-Agent" in hdrs:
                client.headers["User-Agent"] = hdrs["User-Agent"]
            kwargs: dict[str, Any] = {"params": params, "headers": hdrs}
            if data is not None:
                kwargs["data"] = data
            if json is not None:
                kwargs["json"] = json
            if proxy:
                kwargs["proxy"] = proxy if isinstance(proxy, str) else None
            if timeout is not None:
                kwargs["timeout"] = timeout
            resp = await client.request(method, url, **kwargs)
            resp.encoding = resp.encoding or "utf-8"
            return Response(
                status_code=resp.status_code,
                text=resp.text,
                headers=dict(resp.headers),
                url=str(resp.url),
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"HTTP {method} {url}: {exc}") from exc

    def _curl_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | str | None = None,
        json: dict[str, Any] | None = None,
        impersonate: str,
        timeout: float | None,
        proxy: str | None,
    ) -> Response:

        kwargs: dict[str, Any] = {
            "headers": headers,
            "params": params,
            "timeout": timeout or self.settings.timeout,
            "impersonate": impersonate,
            "allow_redirects": True,
        }
        if proxy:
            kwargs["proxies"] = {"http": proxy, "https": proxy}
        if data is not None:
            kwargs["data"] = data
        if json is not None:
            kwargs["json"] = json
        resp = getattr(curl_requests, method.lower())(url, **kwargs)
        return Response(
            status_code=resp.status_code,
            text=resp.text,
            headers={k: str(v) for k, v in resp.headers.items()},
            url=str(resp.url),
        )

    async def get(self, url: str, **kwargs: Any) -> Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Response:
        return await self.request("POST", url, **kwargs)

    async def aclose(self) -> None:
        for client in self._clients.values():
            with contextlib.suppress(Exception):
                await client.aclose()
        self._clients.clear()


_shared: HttpClient | None = None


def get_http_client(settings: Settings | None = None) -> HttpClient:
    global _shared
    if settings is not None:
        return HttpClient(settings)
    if _shared is None:
        _shared = HttpClient()
    return _shared
