"""Curated email-registration check sites.

Endpoints and detection markers are consolidated from public knowledge in
the email-data.json (blackbird) and mailsleuth/holehe/mosint sources.
Every entry follows the dual-marker contract of :class:`EnumSite`.
"""

from __future__ import annotations

from .enum_engine import _RE_EMAIL, _RE_PHONE, EnumSite, PreCheck, Rule


def _gravatar_recover(status: int, content: str, payload) -> dict | None:
    if status != 200 or payload is None:
        return None
    entry = (payload.get("entry") or [{}])[0]
    out: dict = {}
    for key, name in (
        ("displayName", "name"),
        ("preferredUsername", "username"),
        ("currentLocation", "location"),
        ("job_title", "job"),
        ("company", "company"),
        ("aboutMe", "about"),
    ):
        if entry.get(key):
            out[name] = entry[key]
    if entry.get("urls"):
        out["urls"] = [u.get("value") for u in entry["urls"] if u.get("value")]
    if entry.get("accounts"):
        out["linked_accounts"] = [a.get("url") for a in entry["accounts"] if a.get("url")]
    if entry.get("avatar_url") or entry.get("thumbnailUrl"):
        out["avatar"] = entry.get("thumbnailUrl") or entry.get("avatar_url")
    return out or None


def _adobe_recover(status: int, content: str, payload) -> dict | None:
    out: dict = {}
    m = _RE_EMAIL.search(content)
    if m and "authenticationMethods" in content:
        out["recovery_email"] = m.group(1)
    m = _RE_PHONE.search(content)
    if m and "authenticationMethods" in content:
        out["recovery_phone"] = m.group(1)
    if payload and isinstance(payload, list) and payload:
        entry = payload[0]
        if entry.get("displayName"):
            out["full_name"] = entry["displayName"]
    return out or None


def _eventbrite_recover(status: int, content: str, payload) -> dict | None:
    if payload and payload.get("user_id"):
        return {"user_id": payload["user_id"]}
    return None


def _protonmail_recover(status: int, content: str, payload) -> dict | None:
    if status != 200:
        return None
    out: dict = {}
    if "pub" in content or "BEGIN PGP" in content:
        out["pgp_key"] = True
    return out or None


# fmt: off
EMAIL_SITES: list[EnumSite] = [
    # ---- social ----
    EnumSite("Instagram", "social", "register",
        url="https://www.instagram.com/accounts/web_create_ajax/attempt/",
        http_method="POST",
        data="email={email}&username=oneosintprobe&first_name=Probe&opt_into_one_tap=false",
        headers={"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded"},
        found=[Rule("string", "email_is_taken")],
        not_found=[Rule("string", "email_is_available")],
        impersonate="chrome124",
        pre_check=PreCheck("https://www.instagram.com/accounts/emailsignup/", ("csrftoken",))),
    EnumSite("Facebook", "social", "login",
        url="https://www.facebook.com/login/identify/?ctx=recover",
        http_method="POST",
        data="lsd={csrftoken_value}&email={email}&did_submit=Search",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        found=[Rule("regex", r"<div class=\"bb bc\">")],
        not_found=[Rule("string", "No Search Results")],
        impersonate="chrome124"),
    EnumSite("Snapchat", "social", "login",
        url="https://accounts.snapchat.com/accounts/merlin/login",
        http_method="POST",
        data={"email": "{email}", "qphash": "", "prevent_auto_login": False,
              "app": "SCA", "next": "", "sso_client_id": ""},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        found=[Rule("json", True, "hasSnapchat")],
        not_found=[Rule("json", False, "hasSnapchat")]),
    EnumSite("Twitter", "social", "probe",
        url="https://api.twitter.com/i/users/email_available.json?email={email}",
        found=[Rule("json", True, "taken")],
        not_found=[Rule("json", False, "taken")]),
    EnumSite("Pinterest", "social", "register",
        url="https://www.pinterest.com/resource/UnauthUserResource/get/",
        http_method="POST",
        data="email={email}&username=oneosintprobe",
        found=[Rule("string", "\"already_registered\"")],
        not_found=[Rule("string", "\"user\"")],
        impersonate="chrome124"),
    EnumSite("Discord", "social", "register",
        url="https://discord.com/api/v9/auth/register",
        http_method="POST",
        json_body={"email": "{email}", "username": "oneosintprobe", "password": "Probe12345!",
                    "date_of_birth": "1990-01-01", "consent_to_send_helpful_emails": False},
        found=[Rule("string", "already registered")],
        not_found=[Rule("string", "captcha-required")],
        impersonate="chrome124"),
    EnumSite("Eventbrite", "social", "probe",
        url="https://www.eventbrite.com/api/v3/users/lookup/",
        http_method="POST",
        json_body={"email": "{email}", "source_user_id": "", "source_provider": ""},
        headers={"Cookie": "csrftoken={csrftoken_value}",
                 "X-Csrftoken": "{csrftoken_value}",
                 "Referer": "https://www.eventbrite.com/",
                 "Content-Type": "application/json"},
        found=[Rule("json", True, "exists")],
        not_found=[Rule("json", False, "exists")],
        recover=_eventbrite_recover,
        pre_check=PreCheck("https://www.eventbrite.com/", ("csrftoken",))),
    EnumSite("Strava", "social", "probe",
        url="https://www.strava.com/athletes/email_unique?email={email}",
        found=[Rule("string", "false")],
        not_found=[Rule("string", "true")]),
    EnumSite("Venmo", "finance", "probe",
        url="https://venmo.com/api/v5/users?email={email}",
        found=[Rule("string", "\"username\"")],
        not_found=[Rule("json", 404, "meta.status")],
        impersonate="chrome124"),
    EnumSite("Etsy", "shopping", "probe",
        url="https://www.etsy.com/api/v3/ajax/public/users/by-identity-optional",
        http_method="POST",
        json_body={"email": "{email}"},
        headers={"X-Requested-With": "XMLHttpRequest"},
        found=[Rule("json", 200, "status")],
        not_found=[Rule("json", 404, "status")],
        impersonate="chrome124"),

    # ---- coding / dev ----
    EnumSite("Replit", "dev", "probe",
        url="https://replit.com/data/users/email/{email}",
        found=[Rule("status", 200)],
        not_found=[Rule("status", 404)]),
    EnumSite("DevRant", "dev", "register",
        url="https://devrant.com/api/users/check-email",
        http_method="POST",
        json_body={"email": "{email}"},
        found=[Rule("json", "taken", "exists")],
        not_found=[Rule("json", "available", "exists")]),

    # ---- webmail ----
    EnumSite("Google", "webmail", "probe",
        url="https://mail.google.com/mail/gxlu?email={email}",
        found=[Rule("status", 200)],
        not_found=[Rule("status", 404)]),
    EnumSite("Outlook", "webmail", "login",
        url="https://login.microsoft.com/common/oauth2/token",
        http_method="POST",
        data={"grant_type": "password", "username": "{email}",
              "password": "OneOsintProbe123!", "client_id": "00000000-0000-0000-0000-000000000001",
              "resource": "https://graph.windows.net", "scope": "openid"},
        found=[Rule("string", "50126"), Rule("string", "50055"), Rule("string", "53004")],
        not_found=[Rule("string", "50034"), Rule("string", "50057")]),
    EnumSite("Zoho", "webmail", "login",
        url="https://accounts.zoho.in/signin/v2/lookup/{email}",
        http_method="POST",
        data="p=100000",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "X-ZCSRF-TOKEN": "csrf",
                 "X-ZC-ACCOUNT-MODE": "ZOHO"},
        found=[Rule("string", "User exists")],
        not_found=[Rule("string", "User does not exist")]),
    EnumSite("ProtonMail", "webmail", "probe",
        url="https://api.protonmail.ch/pks/lookup?op=get&search={email}",
        found=[Rule("string", "pub")],
        not_found=[Rule("status", 404)],
        recover=_protonmail_recover),

    # ---- CMS / productivity ----
    EnumSite("WordPress.com", "cms", "probe",
        url="https://public-api.wordpress.com/rest/v1.1/users/{email}/auth-options",
        found=[Rule("json", True, "email_verified")],
        not_found=[Rule("json", 404, "status")]),
    EnumSite("Vox Media", "cms", "register",
        url="https://auth.voxmedia.com/chorus_auth/email_valid.json",
        http_method="POST",
        data={"email": "{email}"},
        found=[Rule("string", "You cannot use this email address")],
        not_found=[Rule("json", True, "success")]),
    EnumSite("Gravatar", "images", "probe",
        url="https://gravatar.com/{input}.json",
        input_operation="hash-sha256",
        found=[Rule("status", 200), Rule("string", "displayName")],
        not_found=[Rule("status", 404)],
        recover=_gravatar_recover),
    EnumSite("Notion", "misc", "probe",
        url="https://www.notion.so/api/v3/getLoginOptions",
        http_method="POST",
        json_body={"email": "{email}"},
        found=[Rule("json", True, "hasAccount")],
        not_found=[Rule("json", False, "hasAccount")]),
    EnumSite("Any.do", "productivity", "register",
        url="https://sm-prod2.any.do/check_email",
        http_method="POST",
        json_body={"email": "{email}"},
        found=[Rule("json", True, "user_exists")],
        not_found=[Rule("json", False, "user_exists")]),
    EnumSite("LastPass", "software", "probe",
        url="https://lastpass.com/create_account.php?username={email}&check=avail&i=1",
        found=[Rule("string", "no")],
        not_found=[Rule("string", "yes")]),
    EnumSite("SAP", "software", "probe",
        url="https://core-api.account.sap.com/uid-core/employee/{email}/verify",
        found=[Rule("json", True, "hasUid")],
        not_found=[Rule("json", False, "hasUid")]),
    EnumSite("Firefox", "software", "probe",
        url="https://api.accounts.firefox.com/v1/account/status?email={email}",
        found=[Rule("json", True, "exists")],
        not_found=[Rule("json", False, "exists")]),
    EnumSite("HubSpot", "crm", "login",
        url="https://app.hubspot.com/api/login-api/v1/login",
        http_method="POST",
        json_body={"email": "{email}", "password": "OneOsintProbe123!"},
        found=[Rule("string", "INVALID_PASSWORD")],
        not_found=[Rule("string", "INVALID_USER")],
        impersonate="chrome124"),
    EnumSite("Insightly", "crm", "register",
        url="https://accounts.insightly.com/signup/isemailvalid",
        http_method="POST",
        data={"email": "{email}"},
        found=[Rule("string", "An account exists for this address")],
        not_found=[Rule("string", "VALID")]),
    EnumSite("Nimble", "crm", "probe",
        url="https://nimble.com/lib/register.php?email={email}",
        found=[Rule("string", "email is already registered")],
        not_found=[Rule("string", "email is available")]),
    EnumSite("Kommo", "crm", "login",
        url="https://kommo.com/account/check_login.php",
        http_method="POST",
        data="email={email}&password=OneOsintProbe123!",
        found=[Rule("json", "used", "status")],
        not_found=[Rule("json", "not_used", "status")]),

    # ---- shopping ----
    EnumSite("Amazon", "shopping", "login",
        url="https://www.amazon.com/ap/signin",
        http_method="POST",
        data={"email": "{email}", "password": "OneOsintProbe123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        found=[Rule("string", "auth-password-missing-alert")],
        not_found=[Rule("string", "Invalid email address")],
        impersonate="chrome124"),
    EnumSite("eBay", "shopping", "register",
        url="https://reg.ebay.com/reg/ajax/ValidateEmail",
        http_method="POST",
        data={"email": "{email}"},
        found=[Rule("json", True, "IsEmailRegistered")],
        not_found=[Rule("json", False, "IsEmailRegistered")],
        impersonate="chrome124"),
    EnumSite("OLX", "shopping", "probe",
        url="https://apigw.olx.com.br/v0/user/login/check_email",
        http_method="POST",
        json_body={"email": "{email}"},
        headers={"Content-Type": "application/json",
                 "X-Olx-Team-Key": "5XzjuCgmYE7qMlYpsLZbTvm98ik4CS4a"},
        found=[Rule("string", "EMAIL")],
        not_found=[Rule("string", "ACCOUNT_NOT_FOUND")]),
    EnumSite("Milanuncios", "shopping", "register",
        url="https://userprofiles.gw.milanuncios.com/api/v2/users",
        http_method="POST",
        json_body={"name": "Probe", "password": "1234561", "email": "{email}",
                    "isConsentApproved": "true", "sellerType": "PRIVATE", "role": "USER"},
        found=[Rule("status", 409), Rule("string", "email-already-exists")],
        not_found=[Rule("status", 400)]),
    EnumSite("NetShoes", "shopping", "probe",
        url="https://www.netshoes.com.br/auth/account/exists/{email}",
        found=[Rule("json", True, "exists")],
        not_found=[Rule("json", False, "exists")]),

    # ---- music / gaming / hobby ----
    EnumSite("Spotify", "music", "probe",
        url="https://spclient.wg.spotify.com/signup/public/v1/account?validate=1&email={email}",
        found=[Rule("json", 20, "status")],
        not_found=[Rule("json", 1, "status")]),
    EnumSite("Duolingo", "hobby", "probe",
        url="https://www.duolingo.com/2017-06-30/users?email={email}",
        found=[Rule("string", "username")],
        not_found=[Rule("json", 404, "status")]),
    EnumSite("Chess.com", "gaming", "probe",
        url="https://www.chess.com/callback/email/available?email={email}",
        found=[Rule("status", 226), Rule("string", "Email In Use")],
        not_found=[Rule("string", "Email Available")]),

    # ---- misc / software ----
    EnumSite("Adobe", "misc", "recovery",
        url="https://auth.services.adobe.com/signin/v2/users/accounts",
        http_method="POST",
        json_body={"username": "{email}", "usernameType": "EMAIL"},
        headers={"X-Ims-Clientid": "homepage_milo"},
        found=[Rule("status", 200), Rule("string", "authenticationMethods")],
        not_found=[Rule("string", "[]")],
        recover=_adobe_recover),
    EnumSite("Picsart", "art", "probe",
        url="https://api.picsart.com/users/email/existence?email_encoded=0&emails={email}",
        found=[Rule("json", 200, "status")],
        not_found=[Rule("string", "registration_flow")]),
    EnumSite("Imageshack", "images", "register",
        url="https://imageshack.com/rest_api/v2/user",
        http_method="POST",
        data="email={email}&username=oneosintprobe&password=1&set_cookies=true",
        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        found=[Rule("status", 400), Rule("string", "error_code\":30")],
        not_found=[Rule("status", 400), Rule("string", "error_code\":29")]),
    EnumSite("Tellonym", "social", "register",
        url="https://tellonym.me/api/v1/auth/check-email",
        http_method="POST",
        json_body={"email": "{email}"},
        found=[Rule("json", "used", "status")],
        not_found=[Rule("json", "free", "status")]),
]
# fmt: on


def build_email_sites(include_nsfw: bool = True) -> list[EnumSite]:
    if include_nsfw:
        return EMAIL_SITES
    return [s for s in EMAIL_SITES if s.category != "nsfw"]
