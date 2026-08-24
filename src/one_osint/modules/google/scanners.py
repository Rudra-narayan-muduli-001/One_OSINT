"""Google intelligence: account registration probe, BSSID geolocation."""

from __future__ import annotations

import time

from ...core.config import Settings
from ...core.http_client import get_http_client
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule


class GoogleEmailProbe(BaseModule):
    name = "google_email_probe"
    description = "Gmail/Google account registration probe (gxlu check)"
    input_types = ("email",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        try:
            resp = await http.get(f"https://mail.google.com/mail/gxlu?email={target}")
            cookie = resp.headers.get("Set-Cookie", "")
            if resp.status_code == 200 or ("SID" in cookie or "COMPASS" in cookie):
                result.summary = {"registered": True}
                result.findings.append(
                    Finding(site="google", status=Status.FOUND, category="google",
                            extra={"probe_status": resp.status_code})
                )
            elif resp.status_code == 404:
                result.summary = {"registered": False}
                result.findings.append(Finding(site="google", status=Status.NOT_FOUND, category="google"))
            else:
                result.summary = {"registered": None, "status": resp.status_code}
                result.findings.append(Finding(site="google", status=Status.ERROR, category="google"))
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="google", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result


class GoogleBssidGeo(BaseModule):
    name = "google_bssid_geo"
    description = "Wi-Fi BSSID geolocation via Google Geolocation API"
    input_types = ("ip",)
    requires_key = "google_geolocation"

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        http = get_http_client(self.settings or Settings())
        key = self.keys.get("google_geolocation") if self.keys else None
        try:
            resp = await http.post(
                "https://www.googleapis.com/geolocation/v1/geolocate",
                params={"key": key},
                json={"wifiAccessPoints": [{"macAddress": target, "signalStrength": -50}]},
            )
            if resp.status_code != 200:
                result.error = f"google geolocation returned {resp.status_code}"
                result.findings.append(Finding(site="google", status=Status.ERROR))
            else:
                d = resp.json()
                loc = d.get("location", {})
                result.summary = d
                result.findings.append(
                    Finding(
                        site="google", status=Status.FOUND, category="geo",
                        extra={
                            "bssid": target,
                            "latitude": loc.get("lat"),
                            "longitude": loc.get("lng"),
                            "accuracy": d.get("accuracy"),
                        },
                    )
                )
        except Exception as exc:
            result.error = str(exc)
            result.findings.append(Finding(site="google", status=Status.ERROR))
        result.duration = time.perf_counter() - started
        return result
