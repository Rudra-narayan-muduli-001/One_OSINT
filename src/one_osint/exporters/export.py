"""Report exporters: JSON, CSV, Markdown, HTML, PDF."""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path
from typing import Any


def export_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False)


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


def _neutralize(value: str) -> str:
    if value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


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


def export_pdf(report: dict[str, Any], out_path: Path | None = None) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    path = out_path or Path("report.pdf")
    doc = SimpleDocTemplate(str(path), pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleX", parent=styles["Title"], fontSize=18)
    h2 = ParagraphStyle("H2X", parent=styles["Heading2"], spaceBefore=10, fontSize=13)
    body = styles["BodyText"]

    story: list = [Paragraph(f"OSINT Report: {report['target']}", title)]
    story.append(Paragraph(
        f"Input type: {report['input_type']} &nbsp;·&nbsp; "
        f"Findings: {report.get('found_accounts', 0)} &nbsp;·&nbsp; "
        f"Modules: {report.get('module_count', 0)}", body))
    story.append(Spacer(1, 6))

    for mod in report.get("modules", []):
        story.append(Paragraph(f"{mod['name']} ({mod['duration']:.1f}s)", h2))
        if mod.get("error"):
            story.append(Paragraph(f"<font color='red'>error: {html.escape(mod['error'])}</font>", body))
        rows = [["Status", "Site", "Category", "URL", "Details"]]
        for f in mod.get("findings", []):
            rows.append([
                f["status"], f["site"], f.get("category", ""),
                f.get("url", ""),
                html.escape(json.dumps(f.get("extra") or {}, ensure_ascii=False))[:220],
            ])
        table = Table(rows, repeatRows=1, colWidths=[16 * mm, 28 * mm, 20 * mm, 55 * mm, None])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b3b3b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
        story.append(Spacer(1, 8))

    doc.build(story)
    return path


def write_export(report: dict[str, Any], path: Path, fmt: str) -> Path:
    fmt = fmt.lstrip(".").lower()
    path = Path(path)
    if fmt == "json":
        path.write_text(export_json(report), encoding="utf-8")
    elif fmt == "csv":
        path.write_text(export_csv(report), encoding="utf-8", newline="")
    elif fmt == "md":
        path.write_text(export_markdown(report), encoding="utf-8")
    elif fmt == "html":
        path.write_text(export_html(report), encoding="utf-8")
    elif fmt == "pdf":
        export_pdf(report, path)
    else:
        raise ValueError(f"unsupported format: {fmt}")
    return path
