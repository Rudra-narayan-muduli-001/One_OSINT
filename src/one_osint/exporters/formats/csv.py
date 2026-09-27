from __future__ import annotations

import csv
import io
import json
from typing import Any


def _neutralize(value: str) -> str:
    if value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_csv(report: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["module", "site", "status", "category", "url", "extra"])
    for mod in report.get("modules", []):
        for f in mod.get("findings", []):
            extra = json.dumps(f.get("extra") or {}, ensure_ascii=False)
            writer.writerow([
                mod["name"], f["site"], f["status"], f.get("category", ""),
                f.get("url", ""), _neutralize(extra),
            ])
    return buf.getvalue()