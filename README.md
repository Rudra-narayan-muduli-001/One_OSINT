# one-osint

A unified OSINT platform: email, username, phone, domain, IP and Google intelligence
in a single tool — with a CLI, REST API and web dashboard.

## Features

| Engine | Capabilities |
|---|---|
| **Username** | 700+ site presence check (WhatsMyName dataset), metadata extraction, permutations |
| **Email** | 80+ site registration check, reputation, breach databases, DNS/domain pivot, SMTP verify |
| **Phone** | Validation, formats, carrier, numverify, OVH, Google dork generators |
| **Domain** | Certificate transparency, DNS brute + resolve, subdomain takeover, ASN |
| **IP** | Geolocation, WHOIS, Shodan, ports |
| **Google** | Account registration probe, BSSID geolocation |
| **File** | EXIF/GPS metadata extraction |
| **Misc** | Google dorks, GitHub, ProtonMail, VIN decode, license plates |

## Install

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
one-osint --help
```

## Quick start

```bash
one-osint investigate user@example.com
one-osint investigate someusername --engines username
one-osint investigate "+33612345678" --engines phone
one-osint serve                 # REST API + web UI on :8000
```

## License

MIT. The bundled WhatsMyName dataset (`data/wmn-data.json`) is
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) — see
`data/NOTICE`. This tool is for authorized security research and
investigations only.
