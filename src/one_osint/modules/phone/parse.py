"""Phone number parsing, validation and Google dork generation."""

from __future__ import annotations

import phonenumbers
from phonenumbers import PhoneNumberFormat

DISPOSABLE_SMS_SITES = [
    "hs3x.com", "receive-sms-now.com", "smslisten.com", "smsnumbersonline.com",
    "freesmscode.com", "catchsms.com", "smstibo.com", "smsreceiving.com",
    "getfreesmsnumber.com", "sellaite.com", "receive-sms-online.info",
    "receivesmsonline.com", "receive-a-sms.com", "sms-receive.net",
    "receivefreesms.com", "receive-sms.com", "receivetxt.com", "freephonenum.com",
    "freesmsverification.com", "receive-sms-online.com", "smslive.co",
]

SOCIAL_SITES = ["facebook.com", "twitter.com", "linkedin.com", "instagram.com", "vk.com"]

REPUTATION_SITES = [
    "whosenumber.info", "findwhocallsme.com", "yellowpages.ca", "phonenumbers.ie",
    "who-calledme.com", "usphonesearch.net", "whocalled.us", "quinumero.info",
    "numinfo.net", "sync.me", "whocallsyou.de", "pastebin.com", "whycall.me",
    "locatefamily.com", "spytox.com",
]

FILE_TYPES = ["doc", "docx", "odt", "pdf", "rtf", "sxw", "psw", "ppt", "pptx", "pps", "csv", "txt", "xls"]


def parse_number(raw: str) -> dict | None:
    """Parse and validate an international phone number."""
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


def build_dorks(number: str) -> dict[str, list[str]]:
    """Generate Google dork queries for a phone number (phoneinfoga-style)."""
    e164 = number.replace(" ", "")
    local = number.split()[-1] if " " in number else number
    clean = "".join(c for c in number if c.isdigit() or c == "+")

    social = [f"site:{s} \"{clean}\"" for s in SOCIAL_SITES]
    disposable = [f"site:{s} \"{clean}\"" for s in DISPOSABLE_SMS_SITES]
    reputation = [f"site:{s} \"{clean}\"" for s in REPUTATION_SITES]
    reputation.append(f"intitle:\"who called\" \"{clean}\"")
    reputation.append(f"inurl:\"phone\" \"{clean}\"")
    individuals = [
        f"\"{clean}\" -site:facebook.com -site:twitter.com",
        f"intext:\"{local}\" \"{clean}\"",
    ]
    files = [f"\"{clean}\" filetype:{ft}" for ft in FILE_TYPES]
    generic = [f"\"{clean}\"", f"\"{e164}\""]
    return {
        "social_media": social,
        "disposable_services": disposable,
        "reputation_reports": reputation,
        "individuals": individuals,
        "files": files,
        "generic": generic,
    }
