# Architecture — one-osint

> Technical reference for the codebase structure, data flow, and design decisions.
> Companion to `README.md` (user-facing) and `design.md` (UI spec).

---

## 1. Overview

**one-osint** is a unified OSINT platform that runs parallel intelligence
engines against a single target (email, username, phone, domain, IP, file).
It ships three interfaces over one core:

```
            ┌─────────────────────────────────┐
            │          Web Dashboard           │  React 18 + Vite  →  web/src/
            │   (Investigate · History · Keys)│
            └──────────────┬──────────────────┘
                           │ REST + WebSocket
            ┌──────────────▼──────────────────┐
            │         FastAPI Server           │  src/one_osint/api/server.py
            │  /api/*  ·  /ws/investigate/*   │
            └──────────────┬──────────────────┘
                           │  run_investigation()
            ┌──────────────▼──────────────────┐
            │        CLI  (Typer + Rich)       │  src/one_osint/cli/main.py
            └──────────────┬──────────────────┘
                           │
            ┌──────────────▼──────────────────┐
            │        Orchestrator              │  src/one_osint/orchestrator/
            │  Investigation · 3-phase pipeline│
            └──────────────┬──────────────────┘
                           │  BaseModule.check()
            ┌──────────────▼──────────────────┐
            │      Modules (auto-discovered)   │  src/one_osint/modules/*/
            │  username · email · phone ·      │
            │  domain · ip · google · file ·   │
            │  misc                           │
            └──────────────┬──────────────────┘
                           │
            ┌──────────────▼──────────────────┐
            │        Core Services             │  src/one_osint/core/
            │  detect · config · storage ·    │
            │  http_client · result · paths   │
            └─────────────────────────────────┘
```

**Design principles**

| Principle | How it shows up |
|---|---|
| **One target, many engines** | Input-type detection routes to the right modules; unrelated modules run as secondary pivots. |
| **Pluggable modules** | Drop a `BaseModule` subclass in `modules/<domain>/` — auto-discovered, no registry edits. |
| **Async + bounded concurrency** | `asyncio.Semaphore(settings.concurrency)` caps parallel HTTP; per-module timeout `max(60, timeout*4)`. |
| **Unified result schema** | Every module returns `ModuleResult` → `Finding[]`; orchestrator, exporters, API, and UI consume one shape. |
| **Offline-safe by default** | Modules requiring API keys are skipped when keys are absent; never crash the pipeline. |
| **Streaming UX** | Orchestrator emits `EventSink` events → API fans out via WebSocket → UI updates live. |

---

## 2. Directory Layout

```
one-osint/
├── src/one_osint/              # Python package (hatchling, src-layout)
│   ├── __init__.py             # __version__ = "0.1.0"
│   ├── core/                   # Shared primitives
│   │   ├── detect.py           # InputType enum + regex classifiers
│   │   ├── config.py           # KeyVault + Settings + .env loader
│   │   ├── paths.py            # PROJECT_ROOT, DATA_DIR, CONFIG_DIR, DB_FILE
│   │   ├── http_client.py      # HttpClient (httpx + curl_cffi stealth)
│   │   ├── result.py           # Finding, ModuleResult, Status enums
│   │   ├── storage.py          # SQLite persistence (investigations, module_runs)
│   │   └── useragent.py        # Random UA pool
│   ├── modules/                # Pluggable OSINT engines
│   │   ├── base.py             # BaseModule ABC + discover_modules()
│   │   ├── username/           # WhatsMyName 700+ sites, permutations, curated
│   │   ├── email/              # enumeration, breaches, reputation, DNS pivot
│   │   ├── phone/              # parse + carriers + numverify + dorks
│   │   ├── domain/             # CT, DNS brute, takeover, ASN
│   │   ├── ip/                 # geo, WHOIS, Shodan, ports
│   │   ├── google/             # account probe, BSSID geolocation
│   │   ├── file/               # EXIF/GPS metadata
│   │   └── misc/               # GitHub, ProtonMail, VIN, dorks
│   ├── orchestrator/
│   │   ├── engine.py           # Investigation dataclass + 3-phase pipeline
│   │   └── runner.py           # run_investigation() entry point
│   ├── api/
│   │   └── server.py           # FastAPI app, REST + WebSocket
│   ├── cli/
│   │   └── main.py             # Typer app (investigate, modules, keys, serve)
│   └── exporters/
│       └── export.py           # JSON / CSV / Markdown / HTML / PDF
├── web/                        # Frontend (React + Vite)
│   ├── index.html
│   ├── vite.config.js          # dev proxy /api + /ws → :8000, base /static/
│   ├── package.json
│   └── src/
│       ├── main.jsx            # React root + ToastProvider + RunProvider
│       ├── App.jsx             # Shell: sidebar, topbar, hash routing
│       ├── api.js              # fetch wrappers + wsConnect()
│       ├── state.jsx           # RunContext (live investigation) + ToastContext
│       ├── engines.js          # Engine meta, detectType(), status helpers
│       ├── plain.jsx           # buildPlain() — human-friendly report grouping
│       ├── components/
│       │   ├── PlainView.jsx   # Dossier-style result cards
│       │   ├── CommandPalette.jsx  # ⌘K palette
│       │   └── ui.jsx          # Shared primitives
│       ├── screens/
│       │   ├── Investigate.jsx # Hero search + live engine grid
│       │   ├── Report.jsx      # Historical report view
│       │   ├── History.jsx     # Past investigations table
│       │   └── Keys.jsx        # API key status
│       └── styles/
│           ├── tokens.css      # Design tokens (paper / Dossier theme)
│           └── *.css
├── data/                       # Bundled datasets (wmn-data.json, wordlists)
├── tests/                      # pytest + pytest-asyncio + respx
├── run.py                      # One-shot launcher (venv re-exec + browser open)
├── pyproject.toml              # hatchling, deps, ruff, pytest config
└── design.md                   # Full UI redesign spec (SIGNAL → Dossier pivot)
```

---

## 3. Core (`src/one_osint/core/`)

### 3.1 `detect.py` — Input Classification

Regex-based classifier, evaluated in order:

1. `EMAIL_RE` → `InputType.EMAIL`
2. `PHONE_RE` (7–15 digits, `+` or >10 digits) → `PHONE`
3. `IPV4_RE` / `IPV6_RE` → `IP`
4. `DOMAIN_RE` → `DOMAIN`
5. `USERNAME_RE` (`[A-Za-z0-9_.\-]{3,64}`) → `USERNAME`
6. Fallback → `UNKNOWN`

Helpers: `normalize_email()`, `normalize_username()`, `domain_from_email()`.
Mirrored in `web/src/engines.js:detectType()` for instant UI feedback.

Source: `src/one_osint/core/detect.py:31`

### 3.2 `config.py` — Keys & Settings

**`SUPPORTED_KEYS`** maps canonical names → `(ENV_VAR, description)` for 16 services
(HIBP, EmailRep, Shodan, Numverify, Google CSE/CX, etc.).

**`KeyVault`** resolution order: `overrides` (CLI) → `os.environ` → `keys.yaml` file.
`.env` files at `PROJECT_ROOT/.env` and `CONFIG_DIR/.env` are loaded at import
via `_apply_env_file()` with `os.environ.setdefault` so real env wins.
Static helpers `KeyVault.set()` / `unset()` persist to `keys.yaml`.

**`Settings`** dataclass: `concurrency` (30), `timeout` (15s), `max_retries` (2),
`user_agent_rotate`, `proxies`, `tor`, `verify_tls`, `allow_loud`.

Source: `src/one_osint/core/config.py:66`, `src/one_osint/core/config.py:128`

### 3.3 `paths.py` — Filesystem Locations

```python
PROJECT_ROOT  # src/one_osint/core → parents[3]
DATA_DIR      # $ONE_OSINT_DATA or <root>/data
CONFIG_DIR    # $ONE_OSINT_CONFIG or %APPDATA%/one-osint (win) / ~/.config/one-osint
KEYS_FILE     # CONFIG_DIR/keys.yaml
DB_FILE       # CONFIG_DIR/one-osint.sqlite3
RESULTS_DIR / LOG_DIR / CACHE_DIR  # auto-created
```

Source: `src/one_osint/core/paths.py:1`

### 3.4 `http_client.py` — Stealth HTTP

`HttpClient` wraps `httpx.AsyncClient` (HTTP/2) with:

- **UA rotation** — `random_user_agent()` per request unless header already set.
- **Proxy rotation** — `tor` → `socks5h://127.0.0.1:9050`, else `random.choice(proxies)`.
- **Impersonation** — when `impersonate` is set and `curl_cffi` is installed,
  the request runs via `curl_requests` in `asyncio.to_thread` (Chrome TLS fingerprint).
- **Connection pooling** — `dict[(http2, proxy) → AsyncClient]` keyed cache.
- **Singleton** — `get_http_client()` returns a process-wide instance (first caller's
  settings win); `Investigation.run()` → `finally: await client.aclose()`.

Source: `src/one_osint/core/http_client.py:52`, `src/one_osint/orchestrator/engine.py:54`

### 3.5 `result.py` — Unified Schema

```python
class Status(StrEnum):       FOUND | NOT_FOUND | ERROR | SKIPPED | RATE_LIMITED | POSSIBLE
class ModuleStatus(StrEnum): PENDING | RUNNING | DONE | ERROR | SKIPPED

@dataclass Finding:
    site: str; url: str|None; status: Status; category: str
    extra: dict; media: list[str]; reason: str|None

@dataclass ModuleResult:
    name: str; findings: list[Finding]; summary: dict
    error: str|None; skipped: bool; duration: float
```

`to_dict()` serializes for storage, API, and exporters. The `extra` bag carries
engine-specific enrichment (e.g., `emails`, `usernames`, `breach` payload).

Source: `src/one_osint/core/result.py:15`

### 3.6 `storage.py` — SQLite Persistence

One connection per call (safe across threads/tasks), `WAL` journal mode.

| Table | Columns |
|---|---|
| `investigations` | `id` (hex 16), `target`, `input_type`, `status`, `created_at`, `finished_at`, `report_json` |
| `module_runs` | `id` (autoinc), `investigation_id` FK, `module`, `status`, `duration`, `result_json` |

Operations: `create_investigation()`, `update_investigation()`, `save_module_run()`,
`get_investigation()`, `get_module_runs()`, `list_investigations(limit)`,
`delete_investigation()`.

Source: `src/one_osint/core/storage.py:18`

---

## 4. Modules (`src/one_osint/modules/`)

### 4.1 Contract — `base.py`

```python
class BaseModule(ABC):
    name: str = ""               # machine name, e.g. "email_breaches"
    description: str = ""
    input_types: tuple[str,...]  # which InputType values it handles
    opt_in: bool = False         # needs --opt-in / allow_opt_in
    requires_key: str|None = None

    def can_run(self, input_type: str) -> bool: ...
    async def check(self, target: str) -> ModuleResult: ...
```

Source: `src/one_osint/modules/base.py:22`

### 4.2 Discovery

`discover_modules()` walks `pkgutil.walk_packages(modules.__path__)` and indexes
every `BaseModule` subclass whose `__module__` matches the file it was found in.
Result is cached in `_MODULES`. `get_modules_for(input_type)` instantiates all
matching, runnable modules (respects `opt_in` and `requires_key`).

Source: `src/one_osint/modules/base.py:56`

### 4.3 Module Catalog

| Domain | Files | What it does |
|---|---|---|
| **username** | `whatsmyname.py`, `wmn_engine.py`, `permute.py`, `curated.py` | 700+ site presence via WhatsMyName dataset (`data/wmn-data.json`), curated high-value sites, username permutations |
| **email** | `enumeration.py`, `enum_sites.py`, `enum_engine.py`, `breaches.py`, `reputation.py`, `dns_pivot.py` | 80+ site registration checks, breach DBs (HIBP/IntelX/BreachDirectory/HudsonRock), EmailRep reputation, DNS/MX pivot, SMTP verify |
| **phone** | `parse.py`, `scanners.py` | `phonenumbers` validation + formats, carrier lookup, numverify/OVH, Google dork generators |
| **domain** | `scanners.py` | Certificate Transparency (crt.sh/CertSpotter), DNS brute + `aiodns` resolve, subdomain takeover heuristics, ASN/OTX |
| **ip** | `scanners.py` | Geolocation, WHOIS, Shodan host/ports, reverse DNS |
| **google** | `scanners.py` | Google account registration probe, BSSID/WiGLE geolocation, CSE dorks |
| **file** | `metadata.py` | EXIF/GPS via `piexif`/`Pillow`, `pypdf` text, hash |
| **misc** | `scanners.py` | GitHub code search, ProtonMail existence, VIN decode, license plates, generic dorks |

Adding a new capability = create `src/one_osint/modules/<domain>/my_engine.py`
with a `BaseModule` subclass — no other file changes.

---

## 5. Orchestrator (`src/one_osint/orchestrator/`)

### 5.1 `Investigation` — `engine.py`

```python
@dataclass Investigation:
    target: str
    input_type: InputType
    settings: Settings
    keys: KeyVault
    modules: list[str]        # explicit filter; empty = auto
    allow_opt_in: bool
    event_sink: EventSink|None
    storage: Storage|None
    results: list[ModuleResult]
    pivots: dict[str, list[str]]
```

`run()` → `_run_pipeline()` with guaranteed `get_http_client().aclose()` in `finally`.

**Three-phase pipeline** — `src/one_osint/orchestrator/engine.py:58`

```
Phase 1 — Primary    concurrent run of modules where input_type ∈ module.input_types
Phase 2 — Pivots     _collect_field() harvests extra.emails/usernames/domains/phones
Phase 3 — Secondary  concurrent run of remaining modules (e.g. domain checks on email's domain)
```

Per-module execution (`run_one`):

- `asyncio.Semaphore(concurrency)` bounds parallelism.
- Emits `module_start` before, `module_done` after (with `findings`, `summary`, `duration`, `error`).
- Timeout `asyncio.wait_for(check(), max(60, timeout*4))` → `ModuleResult(error="timeout")`.
- Exceptions → `ModuleResult(error=str(exc))`.
- Persists via `storage.save_module_run()`.

**Pivots** — `src/one_osint/orchestrator/engine.py:135` collects `extra[field]` strings
lowercased and deduped into `pivots = {emails, usernames, domains, phones}` for the final report.

**Report** — `build_report()` returns `{target, input_type, created_at, pivots, modules[], found_accounts, module_count}`.

### 5.2 `runner.py` — Entry Point

`run_investigation(target, keys, settings, modules, allow_opt_in, event_sink, storage)`
constructs an `Investigation` with auto-detected `InputType` and calls `run()`.
Used by both CLI and API.

Source: `src/one_osint/orchestrator/runner.py:12`

---

## 6. CLI (`src/one_osint/cli/main.py`)

Typer app `one-osint` (entry point `one_osint.cli.main:app`):

| Command | Description |
|---|---|
| `investigate <target>` | Full investigation; `--modules`, `--output`, `--allow-loud`, `--opt-in`, `--tor`, `--proxy`, `--concurrency`, `--timeout`, `--quiet` |
| `modules` | Table of discovered modules with input types + required keys |
| `keys [--set k=v] [--unset k] [--list]` | Manage `keys.yaml` |
| `serve [--host] [--port]` | Start FastAPI + Uvicorn |
| `version` | Print version |

Live progress: `event_sink` prints `module_done` lines with Rich; `_print_summary()` renders a final table + panel.

`run.py` at repo root re-execs under `.venv` if needed, health-checks `GET /health`,
and auto-opens the browser.

Source: `src/one_osint/cli/main.py:44`, `run.py:55`

---

## 7. API Server (`src/one_osint/api/server.py`)

FastAPI `app` with `CORSMiddleware(allow_origins=["*"])`.
Serves built frontend from `src/one_osint/webui/static` if present; `GET /` returns `index.html`.

### REST Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | `{status, version}` |
| `GET` | `/api/modules` | List discovered modules with metadata |
| `GET` | `/api/keys` | `KeyVault().list_keys()` with `set` booleans |
| `POST` | `/api/investigate` → `202` | Create investigation, spawn `asyncio.create_task(worker())`, return `{investigation_id, target, input_type}` |
| `GET` | `/api/report/{inv_id}` | Full report JSON or `{modules_so_far}` if still running |
| `GET` | `/api/report/{inv_id}/export?format=` | Export via `report_to_text()` |
| `GET` | `/api/investigations?limit=` | Recent investigations |
| `DELETE` | `/api/investigation/{inv_id}` | Delete investigation + module runs |

Source: `src/one_osint/api/server.py:47`

### WebSocket

`WS /ws/investigate/{inv_id}` — `src/one_osint/api/server.py:187`

```
Client                          Server
  │  POST /api/investigate ──────►│  create inv_id, queue = Queue()
  │◄── {investigation_id} ────────│  worker() starts, sink → queue.put(event)
  │  WS /ws/investigate/{id} ────►│  queue.get() loop → ws.send_json(event)
  │◄── investigation_start ───────│
  │◄── module_start (× N) ────────│
  │◄── module_done  (× N) ────────│
  │◄── investigation_done ────────│
```

`_active: dict[inv_id → Queue]` + `_tasks: set[Task]` (prevents GC). The `queue.get()` loop
uses `wait_for(..., 1s)` so disconnect cleanup is responsive. `investigate()`'s internal
`queue` is separate from `_active` — the worker double-writes `investigation_done`.

---

## 8. Exporters (`src/one_osint/exporters/export.py`)

| Format | Function | Notes |
|---|---|---|
| `json` | `export_json()` | `json.dumps(report, indent=2)` |
| `csv` | `export_csv()` | One row per finding; CSV-injection neutralized via `_neutralize()` |
| `md` | `export_markdown()` | Per-module sections with findings + truncated summaries |
| `html` | `export_html()` | Self-contained HTML with inline styles |
| `pdf` | `export_pdf()` | ReportLab A4 with styled tables |

`write_export(report, path, fmt)` dispatches by extension.

Source: `src/one_osint/exporters/export.py:170`

---

## 9. Web Frontend (`web/`)

### 9.1 Stack

- **React 18** + **Vite 5** (`@vitejs/plugin-react`), `base: /static/`
- Dev proxy: `/api` + `/ws` → `127.0.0.1:8000` (`web/vite.config.js:8`)
- No UI framework — plain CSS with design tokens (`web/src/styles/tokens.css`)
- Hash routing (`#/investigate`, `#/history`, `#/report/<id>`, `#/keys`)

### 9.2 App Shell — `web/src/App.jsx`

`App` owns: hash route (`parseHash`), sidebar rail state (`localStorage signal.rail`),
health polling (`GET /health` every 20s), `⌘K` / `Ctrl+K` palette, `/` focus-search.
Layout: `.shell` → `aside.sidebar` (logo + `NAV` + health dot) + `div.main`
(`TopProgress` + `header.topbar` + `main.content`). `ErrorBoundary` catches render crashes.

### 9.3 State — `web/src/state.jsx`

**`ToastProvider`** — `push(kind, msg)` enqueues ≤5 toasts, auto-dismiss 5s (crit persists).

**`RunProvider`** — single live investigation:

```js
run = { phase, invId, target, startedAt, modules:[{name,status,count,duration}], events[], report, error }
totals = { findings, errors, done, total }
connLost, start(target, moduleNames, optIn), stop(), reset(), hydrate(invId)
```

Event handling (`onEvent`): `investigation_start` seeds queued modules,
`module_start` → `running`, `module_done` → `done/error` (merges pivot re-runs),
`investigation_done` → `hydrate()` fetches full report, `error` → toast.
`wsConnect()` from `web/src/api.js:26` manages the WebSocket.

### 9.4 Helpers — `web/src/engines.js` & `web/src/plain.jsx`

- `ENGINES` — per-engine hue/tint/text + `TYPE_ORDER`, `detectType()` (mirrors `detect.py`),
  `engineOf(moduleName)`, `humanModule()`, `statusVariant()`, `relTime()`/`absTime()`.
- `buildPlain(report)` — groups findings into `{accounts, breaches, facts, leads, others, errors}`,
  dedupes accounts by `site|url`, picks headline/stamp, builds `sections[]` for `PlainView`.

### 9.5 Screens

| Screen | File | Role |
|---|---|---|
| Investigate | `screens/Investigate.jsx` | Hero search + type chips + live engine grid + log drawer |
| Report | `screens/Report.jsx` | Plain dossier + technical toggle + export actions |
| History | `screens/History.jsx` | Filterable table of past investigations |
| Keys | `screens/Keys.jsx` | Per-service key status + masked inputs |

### 9.6 Design Tokens — `web/src/styles/tokens.css`

Paper / Dossier theme (shipped v2): cream canvas `#F7F4EC`, ink `#211F18`,
forest accent `#1E6B4F`, serif display (Fraunces), plain-language cards.
`design.md` retains the original SIGNAL (dark) palette for reference; `tokens.css` is truth.

---

## 10. Data Flow — End to End

```
User types "alice@example.com" + Enter
        │
        ▼
CLI or Web → detect_input_type() → "email"
        │
        ▼
run_investigation() / POST /api/investigate
        │
        ▼
Investigation._build_pipeline() → get_modules_for("email")
        │  e.g. [email_enumeration, email_breaches, email_reputation,
        │         username_wmn (skipped — wrong type), domain_ct …]
        │
        ├── Phase 1: asyncio.gather(run_one × primary)  ──► event: module_start/done
        ├── Phase 2: _run_pivots() harvests extra.*     ──► pivots dict
        └── Phase 3: asyncio.gather(run_one × secondary)
        │
        ▼
build_report() → {target, input_type, pivots, modules[], found_accounts}
        │
        ├── Storage.update_investigation(status="done", report_json)
        ├── EventSink → WebSocket → UI live update
        └── CLI: Rich table + optional write_export(path)
```

---

## 11. Configuration Resolution

```
CLI --set / --proxy / --tor flags
        │
        ▼
KeyVault(overrides={...})
        │
        ├─► os.environ  (HIBP_API_KEY, SHODAN_API_KEY, …)
        │       ▲
        │       │  .env loader at import (PROJECT_ROOT/.env, CONFIG_DIR/.env)
        │
        └─► keys.yaml  (CONFIG_DIR/keys.yaml, written by `one-osint keys --set`)
```

Missing keys never abort — `BaseModule.can_run()` returns `False`, module is excluded.

---

## 12. Extending — Adding a Module

1. Create `src/one_osint/modules/<domain>/my_source.py`:

```python
from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule

class MySourceModule(BaseModule):
    name = "domain_my_source"
    description = "Check my-source for domain exposure"
    input_types = ("domain",)
    requires_key = "my_key"   # optional; omit if no key needed

    async def check(self, target: str) -> ModuleResult:
        # use self.keys.get("my_key"), self.settings, get_http_client()
        return ModuleResult(name=self.name, findings=[...], summary={...})
```

2. No registration needed — `discover_modules()` finds it on next run.
3. Add the key to `SUPPORTED_KEYS` in `core/config.py` if it needs one.
4. Add a test in `tests/` with `respx` mocking the HTTP call.

---

## 13. Testing & Tooling

- **Tests**: `pytest` + `pytest-asyncio` (`asyncio_mode = auto`), `respx` for HTTP mocking.
  `tests/test_api.py`, `test_core.py`, `test_wmn.py`, `test_email_enum.py`.
- **Lint**: `ruff` (`E,F,I,UP,B`, line 100, py312) · **Types**: `mypy`
- **Build**: `hatchling`, `src`-layout, `one-osint` console script.

```bash
pip install -e ".[dev]"
pytest
ruff check src/ tests/
mypy src/
```

---

## 14. Security & Reliability Notes

- **Never trust `extra` HTML** — `export_html()` uses `html.escape`; PDF/CSV neutralize formulas.
- **No secrets in reports** — `KeyVault.list_keys()` returns booleans, never values.
- **Timeouts are hard** — `wait_for(..., max(60, timeout*4))` prevents one slow engine from stalling the batch.
- **WAL + per-call connections** in SQLite avoid locking under concurrent investigations.
- **CORS open** (`allow_origins=["*"]`) — intended for local use; restrict when exposing publicly.
