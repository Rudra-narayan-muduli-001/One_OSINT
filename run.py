"""Instant launcher for one-osint: starts the API + web UI and opens the browser.

Usage:  python run.py [--port 8000] [--host 127.0.0.1] [--no-browser]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("ONE_OSINT_PORT", "8000"))
HOST = os.environ.get("ONE_OSINT_HOST", "127.0.0.1")


def _venv_python() -> Path | None:
    if sys.platform == "win32":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / ".venv" / "bin" / "python"
    return candidate if candidate.is_file() else None


def _open_browser(url: str) -> None:
    def _open() -> None:
        for _ in range(60):
            try:
                import urllib.request

                urllib.request.urlopen(url, timeout=2)
                webbrowser.open(url)
                return
            except Exception:
                time.sleep(0.5)

    threading.Thread(target=_open, daemon=True).start()


def _already_running(host: str, port: int) -> bool:
    try:
        import urllib.request

        urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2)
        return True
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one-osint")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"

    # Already running? Just open the browser.
    if _already_running(args.host, args.port):
        print(f"one-osint already running at {url}")
        if not args.no_browser:
            webbrowser.open(url)
        return

    # Re-exec under the project venv so bare `python run.py` works everywhere.
    if not sys.prefix.startswith(str(ROOT)):
        venv_py = _venv_python()
        if venv_py and os.path.abspath(sys.executable) != os.path.abspath(venv_py):
            raise SystemExit(
                subprocess.call([str(venv_py), str(Path(__file__).resolve())] + sys.argv[1:])
            )

    try:
        import uvicorn  # noqa: F401
        from one_osint.api.server import app
    except ImportError as exc:
        print(f"[red]Missing dependency: {exc}")
        print("Install with: pip install -e .[dev]")
        raise SystemExit(1) from exc

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        _open_browser(url)

    print(f"one-osint running at {url}  (docs at {url}/docs)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
