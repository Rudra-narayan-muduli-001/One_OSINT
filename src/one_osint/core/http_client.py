from __future__ import annotations

import asyncio
import contextlib
import random
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .useragent import random_user_agent

try:
    from curl_cffi import requests as curl_requests

    _HAS_CURL = True
except ImportError:
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


def _pick_proxy(settings: Settings) -> str | None:
    if settings.tor:
        return "socks5h://127.0.0.1:9050"
    if settings.proxies:
        if settings.proxy_rotate:
            return random.choice(settings.proxies)
        return settings.proxies[0]
    return None


async def _curl_request(
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
    settings: Settings,
) -> Response:
    kwargs: dict[str, Any] = {
        "headers": headers,
        "params": params,
        "timeout": timeout or settings.timeout,
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


async def request(
    method: str,
    url: str,
    *,
    settings: Settings | None = None,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | str | None = None,
    json: dict[str, Any] | None = None,
    impersonate: str | None = None,
    timeout: float | None = None,
    http2: bool = True,
) -> Response:
    s = settings or Settings()
    hdrs = dict(headers or {})
    if s.user_agent_rotate and "User-Agent" not in hdrs:
        hdrs["User-Agent"] = random_user_agent()
    proxy = _pick_proxy(s)

    if impersonate and _HAS_CURL:
        return await asyncio.to_thread(
            _curl_request,
            method,
            url,
            headers=hdrs,
            params=params,
            data=data,
            json=json,
            impersonate=impersonate,
            timeout=timeout,
            proxy=proxy,
            settings=s,
        )

    client = httpx.AsyncClient(
        http2=http2,
        verify=s.verify_tls,
        timeout=httpx.Timeout(timeout or s.timeout),
        follow_redirects=True,
        headers={"Accept-Language": "en-US,en;q=0.9"},
        proxy=proxy,
    )
    try:
        kwargs: dict[str, Any] = {"params": params, "headers": hdrs}
        if data is not None:
            kwargs["data"] = data
        if json is not None:
            kwargs["json"] = json
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
    finally:
        with contextlib.suppress(Exception):
            await client.aclose()


async def get(url: str, **kwargs: Any) -> Response:
    return await request("GET", url, **kwargs)


async def post(url: str, **kwargs: Any) -> Response:
    return await request("POST", url, **kwargs)