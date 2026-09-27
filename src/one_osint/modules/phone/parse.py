from __future__ import annotations

import phonenumbers
from phonenumbers import PhoneNumberFormat

from ...core.dorks import build_phone_dorks


def parse_number(raw: str) -> dict | None:
    clean = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    try:
        num = phonenumbers.parse(clean, None)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(num):
        return None
    region = phonenumbers.region_code_for_number(num)
    return {
        "raw_local": num.national_number,
        "local": phonenumbers.format_number(num, PhoneNumberFormat.NATIONAL),
        "e164": phonenumbers.format_number(num, PhoneNumberFormat.E164),
        "international": phonenumbers.format_number(num, PhoneNumberFormat.INTERNATIONAL),
        "country_code": num.country_code,
        "country": region,
        "carrier": _carrier(num),
        "number_type": _line_type(num),
        "national_destination_code": getattr(num, "national_destination_code", None),
    }


def _carrier(num) -> str | None:
    try:
        carrier = __import__("phonenumbers.carrier", fromlist=["name_for_number"])
        return carrier.name_for_number(num, "en")
    except Exception:
        return None


def _line_type(num) -> str:
    try:
        t = phonenumbers.number_type(num)
        return {
            0: "FIXED_LINE",
            1: "MOBILE",
            2: "FIXED_LINE_OR_MOBILE",
            3: "TOLL_FREE",
            4: "PREMIUM_RATE",
            5: "SHARED_COST",
            6: "VOIP",
            7: "PERSONAL_NUMBER",
            8: "PAGER",
            9: "UAN",
            10: "VOICEMAIL",
        }.get(t, "UNKNOWN")
    except Exception:
        return "UNKNOWN"


# Re-export for backward compatibility
build_dorks = build_phone_dorks