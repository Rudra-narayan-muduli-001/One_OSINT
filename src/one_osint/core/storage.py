"""SQLite persistence: investigations, module runs, findings."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .paths import DB_FILE


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Storage:
    """Thin SQLite wrapper. One connection per call - safe across threads/tasks."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DB_FILE
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS investigations (
                    id TEXT PRIMARY KEY,
                    target TEXT NOT NULL,
                    input_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    report_json TEXT
                );
                CREATE TABLE IF NOT EXISTS module_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    investigation_id TEXT NOT NULL,
                    module TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration REAL,
                    result_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_module_runs_inv
                    ON module_runs(investigation_id);
                """
            )

    def create_investigation(self, target: str, input_type: str) -> str:
        inv_id = uuid.uuid4().hex[:16]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO investigations (id, target, input_type, status, created_at) "
                "VALUES (?, ?, ?, 'running', ?)",
                (inv_id, target, input_type, _now()),
            )
        return inv_id

    def update_investigation(self, inv_id: str, status: str, report: dict | None = None) -> None:
        with self._connect() as conn:
            if report is not None:
                conn.execute(
                    "UPDATE investigations SET status = ?, report_json = ?, finished_at = ? "
                    "WHERE id = ?",
                    (status, json.dumps(report), _now(), inv_id),
                )
            else:
                conn.execute(
                    "UPDATE investigations SET status = ?, finished_at = ? WHERE id = ?",
                    (status, _now(), inv_id),
                )

    def save_module_run(
        self, inv_id: str, module: str, status: str, duration: float, result: dict
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO module_runs (investigation_id, module, status, duration, result_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (inv_id, module, status, duration, json.dumps(result)),
            )

    def get_investigation(self, inv_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,)).fetchone()
            return dict(row) if row else None

    def get_module_runs(self, inv_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT module, status, duration, result_json FROM module_runs "
                "WHERE investigation_id = ? ORDER BY id",
                (inv_id,),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["result"] = json.loads(d.pop("result_json") or "{}")
                out.append(d)
            return out

    def list_investigations(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, target, input_type, status, created_at, finished_at "
                "FROM investigations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_investigation(self, inv_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM investigations WHERE id = ?", (inv_id,))
            conn.execute("DELETE FROM module_runs WHERE investigation_id = ?", (inv_id,))
            return cur.rowcount > 0
