from __future__ import annotations

from pathlib import Path
from typing import Any

from .formats.csv import export_csv, _neutralize
from .formats.html import export_html
from .formats.json import export_json
from .formats.markdown import export_markdown

try:
    from .formats.pdf import export_pdf
except ImportError:
    export_pdf = None  # type: ignore


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
        if export_pdf is None:
            raise RuntimeError("PDF export requires 'reportlab' package. Install with: pip install 'one-osint[pdf]'")
        export_pdf(report, path)
    else:
        raise ValueError(f"unsupported format: {fmt}")
    return path


__all__ = [
    "export_json",
    "export_markdown",
    "export_csv",
    "export_html",
    "export_pdf",
    "write_export",
    "_neutralize",
]