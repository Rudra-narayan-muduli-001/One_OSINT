from __future__ import annotations

from .domain.scanners import (
    AsnLookup,
    CertTransparency,
    DnsBrute,
    SubdomainPassive,
    SubdomainTakeover,
)

# Explicit module registry - replaces pkgutil auto-discovery
from .email.breaches import (
    BreachDirectory,
    BreachHibp,
    BreachIntelX,
    HudsonRockStealer,
    PastebinSearch,
)
from .email.dns_pivot import DnsPivot, IpGeolocation, SmtpVerifier
from .email.enumeration import EmailEnumeration
from .email.reputation import EmailReputation
from .file.metadata import FileMetadata
from .google.scanners import GoogleBssidGeo, GoogleEmailProbe
from .ip.scanners import IpReverseDns, IpShodan, IpWhois
from .misc.scanners import (
    DarkWebSearch,
    GithubSearch,
    GoogleDorks,
    LicensePlateLookup,
    ProtonmailLookup,
    VinDecode,
)
from .phone.scanners import (
    PhoneDorks,
    PhoneGoogleCse,
    PhoneLocal,
    PhoneNumverify,
    PhoneOvh,
)
from .username.curated import UsernameGithub, UsernameMastodon, UsernameReddit
from .username.whatsmyname import UsernameWmn

# Build registry
_MODULES: dict[str, type] = {
    # Email modules
    "breach_hibp": BreachHibp,
    "breach_directory": BreachDirectory,
    "breach_intelx": BreachIntelX,
    "pastebin_search": PastebinSearch,
    "hudsonrock_stealer": HudsonRockStealer,
    "dns_pivot": DnsPivot,
    "ip_geolocation": IpGeolocation,
    "smtp_verify": SmtpVerifier,
    "email_enumeration": EmailEnumeration,
    "email_reputation": EmailReputation,
    # Domain modules
    "domain_crt": CertTransparency,
    "domain_dns_brute": DnsBrute,
    "domain_takeover": SubdomainTakeover,
    "domain_asn": AsnLookup,
    "domain_passive": SubdomainPassive,
    # IP modules
    "ip_whois": IpWhois,
    "ip_shodan": IpShodan,
    "ip_reverse_dns": IpReverseDns,
    # Phone modules
    "phone_local": PhoneLocal,
    "phone_numverify": PhoneNumverify,
    "phone_ovh": PhoneOvh,
    "phone_dorks": PhoneDorks,
    "phone_google_cse": PhoneGoogleCse,
    # Username modules
    "username_github": UsernameGithub,
    "username_reddit": UsernameReddit,
    "username_mastodon": UsernameMastodon,
    "username_whatsmyname": UsernameWmn,
    # File modules
    "file_metadata": FileMetadata,
    # Google modules
    "google_email_probe": GoogleEmailProbe,
    "google_bssid_geo": GoogleBssidGeo,
    # Misc modules
    "github_search": GithubSearch,
    "protonmail_lookup": ProtonmailLookup,
    "vin_decode": VinDecode,
    "google_dorks": GoogleDorks,
    "license_plate": LicensePlateLookup,
    "dark_web_search": DarkWebSearch,
}


def discover_modules() -> dict[str, type]:
    return _MODULES