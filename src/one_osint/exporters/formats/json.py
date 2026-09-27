from __future__ import annotations

import json
from typing import Any


def export_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)