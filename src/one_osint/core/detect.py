"""Input type detection: route a raw string to the right engine."""

from __future__ import annotations

import re
from enum import StrEnum

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().\-]{5,}$")
_DOMAIN_RE = re.compile(
    r"^(?!\-)(?:[A-Za-z0-9\-]{1,63}\.)+[A-Za-z]{2,}$"
)
_IPV4_RE = re.compile(
    r"^(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])(\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){3}$"
)
_IPV6_RE = re.compile(r"^(?=[0-9A-Fa-f:]*:)[0-9A-Fa-f:]{2,45}$")
#: local-part variants that make a bare string look like a username first
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,64}$")


class InputType(StrEnum):
    EMAIL = "email"
    USERNAME = "username"
    PHONE = "phone"
    DOMAIN = "domain"
    IP = "ip"
    FILE = "file"
    UNKNOWN = "unknown"


def detect_input_type(value: str) -> InputType:
    """Classify an investigation target string."""
    value = value.strip()
    if not value:
        return InputType.UNKNOWN
    if _EMAIL_RE.match(value):
        return InputType.EMAIL
    if _PHONE_RE.match(value) and any(c.isdigit() for c in value):
        digits = re.sub(r"\D", "", value)
        if 7 <= len(digits) <= 15:
            # A string of digits could be a username; require '+' or length > 10
            if value.startswith("+") or len(digits) > 10:
                return InputType.PHONE
    if _IPV4_RE.match(value) or _IPV6_RE.match(value):
        return InputType.IP
    if _DOMAIN_RE.match(value) and "." in value:
        return InputType.DOMAIN
    if _USERNAME_RE.match(value):
        return InputType.USERNAME
    return InputType.UNKNOWN


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_username(value: str) -> str:
    return value.strip()


def domain_from_email(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()
