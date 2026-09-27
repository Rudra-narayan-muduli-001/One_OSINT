from __future__ import annotations

from urllib.parse import quote

SOCIAL_SITES = ["facebook.com", "twitter.com", "linkedin.com", "instagram.com", "vk.com"]

DISPOSABLE_SMS_SITES = [
    "hs3x.com", "receive-sms-now.com", "smslisten.com", "smsnumbersonline.com",
    "freesmscode.com", "catchsms.com", "smstibo.com", "smsreceiving.com",
    "getfreesmsnumber.com", "sellaite.com", "receive-sms-online.info",
    "receivesmsonline.com", "receive-a-sms.com", "sms-receive.net",
    "receivefreesms.com", "receive-sms.com", "receivetxt.com", "freephonenum.com",
    "freesmsverification.com", "receive-sms-online.com", "smslive.co",
]

REPUTATION_SITES = [
    "whosenumber.info", "findwhocallsme.com", "yellowpages.ca", "phonenumbers.ie",
    "who-calledme.com", "usphonesearch.net", "whocalled.us", "quinumero.info",
    "numinfo.net", "sync.me", "whocallsyou.de", "pastebin.com", "whycall.me",
    "locatefamily.com", "spytox.com",
]

FILE_TYPES = ["doc", "docx", "odt", "pdf", "rtf", "sxw", "psw", "ppt", "pptx", "pps", "csv", "txt", "xls"]


def build_phone_dorks(number: str) -> dict[str, list[str]]:
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


def build_generic_dorks(target: str) -> list[str]:
    return [
        f"intext:'{target}'",
        f'"{target}" filetype:pdf',
        f'"{target}" filetype:csv',
        f'"{target}" site:pastebin.com',
        f'"{target}" site:github.com',
        f'"{target}" site:linkedin.com',
        f'"{target}" site:facebook.com',
        f'"{target}" -site:linkedin.com -site:facebook.com',
    ]


def dorks_to_findings(dorks: dict[str, list[str]] | list[str]) -> list[dict]:
    """Convert dork queries to finding-like dicts for module results."""
    out = []
    if isinstance(dorks, dict):
        for group, queries in dorks.items():
            for q in queries:
                out.append({
                    "site": "google",
                    "status": "possible",
                    "category": group,
                    "url": f"https://www.google.com/search?q={quote(q)}",
                    "reason": "ready-to-run search link (not verified)",
                    "extra": {"query": q},
                })
    else:
        for q in dorks:
            out.append({
                "site": "google",
                "status": "possible",
                "category": "dorks",
                "url": f"https://www.google.com/search?q={quote(q)}",
                "reason": "ready-to-run search link (not verified)",
                "extra": {"query": q},
            })
    return out