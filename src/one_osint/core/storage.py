from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .paths import CONFIG_DIR


def _now() -> str:
    return datetime.now(UTC).isoformat()


RESULTS_FILE = CONFIG_DIR / "investigations.jsonl"


class Storage:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or RESULTS_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def _write_all(self, data: list[dict]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")

    def create_investigation(self, target: str, input_type: str) -> str:
        inv_id = uuid.uuid4().hex[:16]
        inv = {
            "id": inv_id,
            "target": target,
            "input_type": input_type,
            "status": "running",
            "created_at": _now(),
            "finished_at": None,
            "report": None,
            "module_runs": [],
        }
        data = self._read_all()
        data.append(inv)
        self._write_all(data)
        return inv_id

    def update_investigation(self, inv_id: str, status: str, report: dict | None = None) -> None:
        data = self._read_all()
        for inv in data:
            if inv["id"] == inv_id:
                inv["status"] = status
                inv["finished_at"] = _now()
                if report is not None:
                    inv["report"] = report
                break
        self._write_all(data)

    def save_module_run(
        self, inv_id: str, module: str, status: str, duration: float, result: dict
    ) -> None:
        data = self._read_all()
        for inv in data:
            if inv["id"] == inv_id:
                inv["module_runs"].append(
                    {
                        "module": module,
                        "status": status,
                        "duration": duration,
                        "result": result,
                    }
                )
                break
        self._write_all(data)

    def get_investigation(self, inv_id: str) -> dict | None:
        for inv in self._read_all():
            if inv["id"] == inv_id:
                return inv
        return None

    def get_module_runs(self, inv_id: str) -> list[dict]:
        for inv in self._read_all():
            if inv["id"] == inv_id:
                return inv.get("module_runs", [])
        return []

    def list_investigations(self, limit: int = 50) -> list[dict]:
        data = self._read_all()
        data.sort(key=lambda x: x["created_at"], reverse=True)
        out = []
        for inv in data[:limit]:
            out.append(
                {
                    "id": inv["id"],
                    "target": inv["target"],
                    "input_type": inv["input_type"],
                    "status": inv["status"],
                    "created_at": inv["created_at"],
                    "finished_at": inv["finished_at"],
                }
            )
        return out

    def delete_investigation(self, inv_id: str) -> bool:
        data = self._read_all()
        new_data = [inv for inv in data if inv["id"] != inv_id]
        if len(new_data) < len(data):
            self._write_all(new_data)
            return True
        return False