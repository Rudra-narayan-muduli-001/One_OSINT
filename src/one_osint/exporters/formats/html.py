from __future__ import annotations

import html
import json
from typing import Any


def export_html(report: dict[str, Any]) -> str:
    status_icons = {"found": "🟢", "not_found": "⚪", "error": "🔴", "skipped": "🟡"}
    mods = []
    for mod in report.get("modules", []):
        rows = []
        for f in mod.get("findings", []):
            icon = status_icons.get(f["status"], "•")
            extra = html.escape(json.dumps(f.get("extra") or {}, ensure_ascii=False)[:300])
            url = f'<a href="{html.escape(f.get("url", ""))}">link</a>' if f.get("url") else ""
            rows.append(
                f"<tr><td>{icon}</td><td>{html.escape(f['site'])}</td>"
                f"<td>{f['status']}</td><td>{html.escape(f.get('category', ''))}</td>"
                f"<td>{url}</td><td><code>{extra}</code></td></tr>"
            )
        error = f"<p class='err'>error: {html.escape(mod['error'])}</p>" if mod.get("error") else ""
        summary = (
            f"<pre>{html.escape(json.dumps(mod.get('summary', {}), indent=2, ensure_ascii=False)[:1500])}</pre>"
            if mod.get("summary")
            else ""
        )
        mods.append(
            f"<section><h2>{html.escape(mod['name'])} <small>({mod['duration']:.1f}s)</small></h2>"
            f"{error}{summary}<table><thead><tr><th></th><th>Site</th><th>Status</th>"
            f"<th>Category</th><th>URL</th><th>Details</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></section>"
        )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>OSINT Report: {html.escape(report['target'])}</title>
<style>
 body {{ font-family: system-ui; margin: 2rem auto; max-width: 1000px; color: #222; }}
 h1 {{ border-bottom: 2px solid #444; padding-bottom: .4rem; }}
 h2 small {{ color: #888; font-weight: normal; }}
 table {{ border-collapse: collapse; width: 100%; margin: .6rem 0 1.6rem; font-size: .9rem; }}
 td, th {{ border: 1px solid #ddd; padding: .3rem .5rem; text-align: left; vertical-align: top; }}
 code, pre {{ background: #f4f4f4; padding: .2rem .4rem; font-size: .8rem; white-space: pre-wrap; }}
 .err {{ color: #b00; }} pre {{ padding: .6rem; }}
</style></head><body>
<h1>OSINT Report: {html.escape(report['target'])}</h1>
<p>Input type: <code>{report['input_type']}</code> · Generated: {report.get('created_at', '')} ·
Findings: {report.get('found_accounts', 0)} · Modules: {report.get('module_count', 0)}</p>
{''.join(mods)}
</body></html>"""