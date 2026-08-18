"""FastAPI application: REST API + WebSocket streaming for investigations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..core.config import KeyVault, Settings
from ..core.detect import detect_input_type
from ..core.storage import Storage
from ..modules.base import discover_modules
from ..orchestrator.runner import run_investigation

app = FastAPI(title="one-osint", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_WEBUI_DIR = Path(__file__).resolve().parent.parent / "webui" / "static"
if _WEBUI_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=_WEBUI_DIR), name="static")


@app.get("/")
async def index() -> PlainTextResponse:
    idx = _WEBUI_DIR / "index.html"
    if not idx.is_file():
        raise HTTPException(404, "web UI not built")
    return PlainTextResponse(idx.read_text(encoding="utf-8"), media_type="text/html")

#: investigation_id -> asyncio.Queue of events (for WebSocket fan-out)
_active: dict[str, asyncio.Queue] = {}
#: strong refs to background workers (prevents GC of pending tasks)
_tasks: set[asyncio.Task] = set()


class InvestigateRequest(BaseModel):
    target: str
    modules: list[str] | None = None
    allow_loud: bool = False
    tor: bool = False
    allow_opt_in: bool = False
    proxies: list[str] | None = None


class ExportRequest(BaseModel):
    format: str = "json"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/modules")
async def list_modules() -> list[dict[str, Any]]:
    out = []
    for name, cls in sorted(discover_modules().items()):
        out.append(
            {
                "name": name,
                "description": cls.description,
                "input_types": list(cls.input_types),
                "opt_in": cls.opt_in,
                "requires_key": cls.requires_key,
            }
        )
    return out


@app.get("/api/keys")
async def list_keys() -> list[dict[str, Any]]:
    return KeyVault().list_keys()


@app.post("/api/investigate", status_code=202)
async def investigate(req: InvestigateRequest) -> dict[str, Any]:
    target = req.target.strip()
    input_type = detect_input_type(target)
    if input_type.value == "unknown":
        raise HTTPException(400, f"cannot detect input type for: {target}")

    storage = Storage()
    settings = Settings(
        allow_loud=req.allow_loud, tor=req.tor, proxies=req.proxies or []
    )
    queue: asyncio.Queue = asyncio.Queue()
    inv_id = storage.create_investigation(target, input_type.value)
    _active[inv_id] = queue

    async def sink(event: dict[str, Any]) -> None:
        await queue.put(event)
        if event.get("type") == "investigation_done":
            storage.update_investigation(inv_id, "done")

    async def worker() -> None:
        try:
            report = await run_investigation(
                target,
                keys=KeyVault(),
                settings=settings,
                modules=req.modules,
                allow_opt_in=req.allow_opt_in,
                event_sink=sink,
                storage=None,
            )
            storage.update_investigation(inv_id, "done", report)
        except Exception:
            storage.update_investigation(inv_id, "error")
        finally:
            await queue.put({"type": "investigation_done", "investigation_id": inv_id})

    task = asyncio.create_task(worker())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"investigation_id": inv_id, "target": target, "input_type": input_type.value}


@app.get("/api/report/{inv_id}")
async def get_report(inv_id: str) -> dict[str, Any]:
    storage = Storage()
    inv = storage.get_investigation(inv_id)
    if not inv:
        raise HTTPException(404, "investigation not found")
    report = inv.get("report_json")
    if report:
        import json

        return json.loads(report)
    runs = storage.get_module_runs(inv_id)
    return {
        "id": inv_id,
        "target": inv["target"],
        "status": inv["status"],
        "modules_so_far": runs,
    }


@app.get("/api/report/{inv_id}/export")
async def export_report(inv_id: str, format: str = "json") -> PlainTextResponse:
    import io

    storage = Storage()
    inv = storage.get_investigation(inv_id)
    if not inv or not inv.get("report_json"):
        raise HTTPException(404, "no finished report for this investigation")
    import json

    report = json.loads(inv["report_json"])
    buf = io.StringIO()
    buf.write(report_to_text(report, format))
    return PlainTextResponse(buf.getvalue())


def report_to_text(report: dict[str, Any], fmt: str) -> str:
    from ..exporters.export import export_csv, export_json, export_markdown

    if fmt == "json":
        return export_json(report)
    if fmt == "csv":
        return export_csv(report)
    if fmt == "md":
        return export_markdown(report)
    raise HTTPException(400, f"unsupported format: {fmt}")


@app.get("/api/investigations")
async def list_investigations(limit: int = 50) -> list[dict[str, Any]]:
    return Storage().list_investigations(limit)


@app.delete("/api/investigation/{inv_id}")
async def delete_investigation(inv_id: str) -> dict[str, bool]:
    return {"deleted": Storage().delete_investigation(inv_id)}


@app.websocket("/ws/investigate/{inv_id}")
async def ws_investigate(ws: WebSocket, inv_id: str) -> None:
    await ws.accept()
    queue = _active.get(inv_id)
    if queue is None:
        await ws.send_json({"type": "error", "message": "unknown investigation"})
        await ws.close()
        return
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                await ws.send_json(event)
            except TimeoutError:
                if inv_id not in _active:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        _active.pop(inv_id, None)
