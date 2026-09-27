from __future__ import annotations

import re

# Shared regex patterns for email and phone detection
# Used by core/detect.py and modules/email/enum_engine.py

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().\-]{5,}$")

# More permissive patterns for extraction from text bodies
_RE_EMAIL = re.compile(r"([A-Za-z0-9._%+\-*]+\*?@[A-Za-z0-9.\-*]+\.[A-Za-z*]{2,})")
_RE_PHONE = re.compile(r"(\+?[0-9*]{4,}[0-9*]{4,})")


def is_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value.strip()))


def is_phone(value: str) -> bool:
    value = value.strip()
    if not _PHONE_RE.match(value):
        return False
    digits = re.sub(r"\D", "", value)
    return 7 <= len(digits) <= 15 and (value.startswith("+") or len(digits) > 10)


def extract_emails(text: str) -> list[str]:
    return _RE_EMAIL.findall(text)


def extract_phones(text: str) -> list[str]:
    return _RE_PHONE.findall(text)