from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

try:
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
    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False


def export_pdf(report: dict[str, Any], out_path: Path | None = None) -> Path:
    if not _HAS_REPORTLAB:
        raise RuntimeError("PDF export requires 'reportlab' package. Install with: pip install 'one-osint[pdf]'")
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