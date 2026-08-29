# one-osint

A unified OSINT platform — email, username, phone, domain, IP and Google intelligence
in a single tool. One target, many engines, live results — via **CLI**, **REST API**, and **web dashboard**.

> For authorized security research and investigations only.

---

## Features

| Engine | Capabilities |
|---|---|
| **Username** | 700+ site presence check (WhatsMyName dataset), curated high-value sites, permutations |
| **Email** | 80+ site registration check, reputation (EmailRep), breach databases (HIBP/IntelX/BreachDirectory/HudsonRock), DNS/MX pivot, SMTP verify |
| **Phone** | Validation & formatting (`phonenumbers`), carrier, numverify/OVH, Google dork generators |
| **Domain** | Certificate Transparency (crt.sh/CertSpotter), DNS brute + `aiodns` resolve, subdomain takeover heuristics, ASN/OTX |
| **IP** | Geolocation, WHOIS/reverse, Shodan host & ports |
| **Google** | Account registration probe, BSSID/WiGLE geolocation, CSE dorks |
| **File** | EXIF/GPS (`piexif`/`Pillow`), PDF text, hashes |
| **Misc** | GitHub code search, ProtonMail existence, VIN decode, license plates, dorks |

All engines run **concurrently** (`asyncio` + bounded semaphore), share one stealth HTTP client
(`httpx` HTTP/2 + optional `curl_cffi` Chrome impersonation), and return a single
`Finding`/`ModuleResult` schema consumed by every interface.

---

## Quick Start

```bash
# 1. Install
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"

# 2. Investigate anything — type is auto-detected
one-osint investigate user@example.com
one-osint investigate someusername --modules username_wmn,username_curated
one-osint investigate "+33 6 12 34 56 78" --modules phone_parse,phone_scanners
one-osint investigate example.com --output report.pdf

# 3. Or launch the web UI (REST API + dashboard on :8000)
one-osint serve
# — or —
python run.py                   # auto-uses .venv, opens browser

# 4. List what's available
one-osint modules
one-osint keys --list
```

---

## Installation

**Requirements:** Python ≥ 3.12

```bash
pip install -e .                # runtime
pip install -e ".[dev]"         # + pytest, respx, ruff, mypy
```

`run.py` at the repo root re-executes under `.venv` automatically, so bare
`python run.py` works even without activating the environment.

### Web dashboard (optional)

```bash
cd web
npm install
npm run dev     # Vite dev server on :5173, proxies /api + /ws → :8000
npm run build   # → bundled to be served by FastAPI at /static/
```

> The Python server serves `web/dist` via `src/one_osint/webui/static` when built.
> You can run the API without building the frontend.

---

## CLI Reference

```
one-osint investigate <TARGET>   Run a full investigation
  --modules, -m   Comma-separated module filter (default: auto by input type)
  --output, -o    Export path (.json/.csv/.md/.html/.pdf)
  --allow-loud    Allow modules that contact the target directly
  --opt-in        Include opt-in modules (paid/loud/credential)
  --tor           Route through Tor SOCKS on 127.0.0.1:9050
  --proxy         HTTP/SOCKS proxy (comma-separated, rotated)
  --concurrency   Parallel requests (1–200, default 30)
  --timeout       Per-request seconds (default 15)
  --quiet, -q     Only print summary

one-osint modules                List all discovered modules
one-osint keys                   Manage API keys (keys.yaml)
  --set name=value
  --unset name
  --list
one-osint serve                  Start REST API + WebSocket server
  --host, -H  (default 127.0.0.1)
  --port, -p  (default 8000)
one-osint version
```

Exit codes: `0` success · `2` bad input · `130` interrupted.

---

## REST API & WebSocket

When `one-osint serve` (or `python run.py`) is running:

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health + version |
| `GET` | `/api/modules` | Discovered modules with `input_types`, `requires_key` |
| `GET` | `/api/keys` | Key status (booleans only, never values) |
| `POST` | `/api/investigate` | Start investigation → `202 {investigation_id}` |
| `GET` | `/api/report/{id}` | Full report or `modules_so_far` while running |
| `GET` | `/api/report/{id}/export?format=json\|csv\|md` | Export |
| `GET` | `/api/investigations?limit=50` | Recent investigations |
| `DELETE` | `/api/investigation/{id}` | Delete |
| `WS` | `/ws/investigate/{id}` | Live event stream |

**Example:**

```bash
curl -X POST http://127.0.0.1:8000/api/investigate \
  -H "Content-Type: application/json" \
  -d '{"target":"alice@example.com"}'
# → {"investigation_id":"a1b2c3...","target":"alice@example.com","input_type":"email"}

curl http://127.0.0.1:8000/api/report/a1b2c3...
curl http://127.0.0.1:8000/api/report/a1b2c3.../export?format=md
```

**WebSocket events:** `investigation_start` → `module_start` → `module_done` (× N) → `investigation_done`.
The dashboard (`web/src/state.jsx:86`) consumes these to render live progress.

Interactive docs at `http://127.0.0.1:8000/docs` (Swagger).

---

## Web Dashboard

A **paper / Dossier** theme (warm cream `#F7F4EC`, ink `#211F18`, forest accent `#1E6B4F`,
serif display) with plain-language result cards and a global *Technical details* toggle.

| Screen | Route | Description |
|---|---|---|
| **New search** | `#/investigate` | Hero input + type chips + live engine grid + log drawer |
| **Report** | `#/report/<id>` | Dossier view grouped by breaches/accounts/facts/leads |
| **Past searches** | `#/history` | Filterable table of previous investigations |
| **Optional keys** | `#/keys` | Per-service key status + masked inputs |

Global shortcuts: `⌘K`/`Ctrl+K` command palette, `/` focus search.
Tokens are the source of truth at `web/src/styles/tokens.css`; full spec in `design.md`.

---

## Configuration — API Keys

Keys are optional. Modules that need a missing key are **skipped**, never failed.

**Resolution order:** CLI override → environment variable → `.env` file → `keys.yaml`

| How | Where |
|---|---|
| `one-osint keys --set shodan=TOKEN` | `~/.config/one-osint/keys.yaml` (or `%APPDATA%\one-osint` on Windows) |
| `SHODAN_API_KEY=...` in shell | Environment |
| `.env` at repo root or config dir | `.env` file (minimal `KEY=VALUE` parser, `#` comments) |

Copy `.env.example` → `.env` and fill what you have:

```bash
cp .env.example .env
# HIBP, EmailRep, BreachDirectory, IntelX, Shodan, Numverify,
# Google CSE/CX, HudsonRock, GitHub, VirusTotal, OTX, CertSpotter, RapidAPI …
```

Check status:

```bash
one-osint keys --list
curl http://127.0.0.1:8000/api/keys
```

---

## Project Structure

```
src/one_osint/
  core/          detect · config · paths · http_client · result · storage · useragent
  modules/       username · email · phone · domain · ip · google · file · misc  (+ base.py)
  orchestrator/  engine.py (3-phase pipeline) · runner.py
  api/           server.py (FastAPI + WebSocket)
  cli/           main.py (Typer + Rich)
  exporters/     export.py (JSON/CSV/Markdown/HTML/PDF)
web/
  src/           App.jsx · api.js · state.jsx · engines.js · plain.jsx
               components/ · screens/ · styles/tokens.css
  vite.config.js · index.html
tests/           pytest + respx
run.py           venv-aware launcher + browser opener
design.md        UI spec (SIGNAL → Dossier pivot)
ARCHITECTURE.md  Deep technical reference ← start here for contributing
```

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for data flow, storage schema, module contract,
and how to add a new engine.

---

## Exports

```bash
one-osint investigate alice@example.com --output report.json   # JSON
one-osint investigate alice@example.com --output report.csv    # CSV (formula-neutralized)
one-osint investigate alice@example.com --output report.md     # Markdown
one-osint investigate alice@example.com --output report.html   # Self-contained HTML
one-osint investigate alice@example.com --output report.pdf    # A4 PDF (ReportLab)
```

Or via API: `GET /api/report/{id}/export?format=json|csv|md`

---

## Development

```bash
pip install -e ".[dev]"
pytest                          # all tests (asyncio_mode = auto)
pytest tests/test_api.py -v
ruff check src/ tests/          # lint (E,F,I,UP,B, line 100, py312)
mypy src/                       # type check
```

**Adding a module:** create `src/one_osint/modules/<domain>/my_engine.py` with a
`BaseModule` subclass (`name`, `description`, `input_types`, `check()`).
It is auto-discovered — no registry edit needed. See `ARCHITECTURE.md:12`.

---

## Ethics & Legal

This tool is for **authorized** security research, educational use, and
investigations you have permission to perform. Do not use it to harass,
dox, or violate terms of service / local laws. Respect rate limits and
`--allow-loud` / `--opt-in` guards for intrusive modules.

---

## License

**CC BY-NC 4.0** — Creative Commons Attribution-NonCommercial 4.0 International.
See [`LICENSE`](LICENSE) and `pyproject.toml`.

You are free to share and adapt this work for **non-commercial purposes only**,
provided you give appropriate credit. Commercial use (including selling,
hosting as a paid service, or integrating into a commercial product) requires
separate permission from the licensor.

- Human-readable summary: <https://creativecommons.org/licenses/by-nc/4.0/>
- Full legal code: <https://creativecommons.org/licenses/by-nc/4.0/legalcode>

The bundled WhatsMyName dataset (`data/wmn-data.json`) remains separately licensed
under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) — see `data/NOTICE`.
