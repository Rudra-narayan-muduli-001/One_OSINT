from __future__ import annotations

import json
from typing import Any


def export_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# OSINT Report: {report['target']}")
    lines.append("")
    lines.append(f"- **Input type:** `{report['input_type']}`")
    lines.append(f"- **Generated:** {report.get('created_at', '')}")
    lines.append(f"- **Modules run:** {report.get('module_count', 0)}")
    lines.append(f"- **Findings:** {report.get('found_accounts', 0)}")
    pivots = report.get("pivots") or {}
    for kind, values in pivots.items():
        if values:
            lines.append(f"- **Pivots ({kind}):** {', '.join(values)}")
    lines.append("")
    for mod in report.get("modules", []):
        lines.append(f"## {mod['name']}  ({mod['duration']:.1f}s)")
        if mod.get("error"):
            lines.append(f"> error: {mod['error']}")
        if mod.get("summary"):
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(mod["summary"], indent=2, ensure_ascii=False)[:2000])
            lines.append("```")
        for f in mod.get("findings", []):
            icon = {"found": "FOUND", "not_found": "absent", "error": "ERR", "skipped": "skip"}.get(
                f["status"], f["status"]
            )
            line = f"- [{icon}] {f['site']}"
            if f.get("url"):
                line += f" — {f['url']}"
            if f.get("extra"):
                line += f"  `{json.dumps(f['extra'], ensure_ascii=False)[:200]}`"
            lines.append(line)
        lines.append("")
    return "\n".join(lines)