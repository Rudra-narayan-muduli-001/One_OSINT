"""File metadata: EXIF/GPS extraction from images and documents."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from ...core.result import Finding, ModuleResult, Status
from ..base import BaseModule


def _gps_to_decimal(value) -> float | None:
    try:
        if value in (None, ""):
            return None
        v = float(value[0]) + float(value[1]) / 60 + float(value[2]) / 3600
        return v
    except Exception:
        return None


def _extract_image_meta(path: Path) -> dict:
    out: dict = {}
    try:
        import piexif

        exif_dict = piexif.load(str(path))
    except Exception:
        # piexif only parses JPEG/TIFF - fall back to Pillow for PNG/HEIC/WebP
        return _extract_image_meta_pillow(path)
    gps = exif_dict.get("GPS", {})
    lat = _gps_to_decimal(gps.get(piexif.GPSIFD.GPSLatitude))
    lon = _gps_to_decimal(gps.get(piexif.GPSIFD.GPSLongitude))
    lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef, b"N")
    lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef, b"E")
    if lat is not None and lon is not None:
        if isinstance(lat_ref, bytes) and lat_ref in (b"S", b"s"):
            lat = -lat
        if isinstance(lon_ref, bytes) and lon_ref in (b"W", b"w"):
            lon = -lon
        out["gps"] = {"latitude": round(lat, 6), "longitude": round(lon, 6)}
        out["google_maps"] = f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"
    exif = exif_dict.get("Exif", {})
    if exif.get(piexif.ExifIFD.DateTimeOriginal):
        out["date_taken"] = exif[piexif.ExifIFD.DateTimeOriginal].decode(errors="ignore")
    if exif.get(piexif.ExifIFD.LensMake):
        out["lens"] = exif[piexif.ExifIFD.LensMake].decode(errors="ignore")
    # Note: ExifIFD has no 'Model' tag — camera model lives in 0th IFD
    # so this branch is intentionally omitted (previously caused AttributeError)
    ifd0 = exif_dict.get("0th", {})
    if ifd0.get(piexif.ImageIFD.Make):
        out["camera_make"] = ifd0[piexif.ImageIFD.Make].decode(errors="ignore")
    if ifd0.get(piexif.ImageIFD.Software):
        out["software"] = ifd0[piexif.ImageIFD.Software].decode(errors="ignore")
    if ifd0.get(piexif.ImageIFD.Artist):
        out["author"] = ifd0[piexif.ImageIFD.Artist].decode(errors="ignore")
    if ifd0.get(piexif.ImageIFD.ImageDescription):
        out["description"] = ifd0[piexif.ImageIFD.ImageDescription].decode(errors="ignore")
    return out


def _extract_image_meta_pillow(path: Path) -> dict:
    from PIL import Image
    from PIL.ExifTags import TAGS

    out: dict = {}
    try:
        img = Image.open(str(path))
        raw = img.getexif()
    except Exception:
        return out
    for tag_id, value in raw.items():
        name = TAGS.get(tag_id, str(tag_id))
        if name in ("Make", "Model", "Software", "Artist"):
            out[name.lower()] = str(value)
        elif name == "ImageDescription":
            out["description"] = str(value)
    exif = raw.get_ifd(0x8769)
    for tag_id, value in exif.items():
        name = TAGS.get(tag_id, str(tag_id))
        if name == "DateTimeOriginal":
            out["date_taken"] = str(value)
        elif name == "LensMake":
            out["lens"] = str(value)
    gps_raw = exif.get_ifd(0x8825)

    def _deg(v):
        try:
            return float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
        except Exception:
            return None

    lat = _deg(gps_raw.get(2))
    lon = _deg(gps_raw.get(4))
    if lat is not None and lon is not None:
        if gps_raw.get(3) in ("S", "s"):
            lat = -lat
        if gps_raw.get(5) in ("W", "w"):
            lon = -lon
        out["gps"] = {"latitude": round(lat, 6), "longitude": round(lon, 6)}
        out["google_maps"] = f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"
    return out


def _extract_pdf_meta(path: Path) -> dict:
    from pypdf import PdfReader

    out: dict = {}
    try:
        reader = PdfReader(str(path))
        meta: dict = reader.metadata or {}
        for key in ("title", "author", "subject", "creator", "producer", "creation_date"):
            if meta.get(key):
                out[key] = str(meta[key])
    except Exception:
        pass
    return out


class FileMetadata(BaseModule):
    name = "file_metadata"
    description = "EXIF/GPS/document metadata extraction from a file"
    input_types = ("file",)

    async def check(self, target: str) -> ModuleResult:
        started = time.perf_counter()
        result = ModuleResult(name=self.name)
        path = Path(target)
        if not path.exists():
            result.error = f"file not found: {target}"
            result.findings.append(Finding(site="file", status=Status.ERROR, category="file"))
            result.duration = time.perf_counter() - started
            return result
        suffix = path.suffix.lower()
        if suffix in (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".heic"):
            meta = await asyncio.to_thread(_extract_image_meta, path)
        elif suffix == ".pdf":
            meta = await asyncio.to_thread(_extract_pdf_meta, path)
        else:
            meta = await _generic_meta(path)
        result.summary = {"file": target, "size": path.stat().st_size}
        if meta:
            result.findings.append(
                Finding(
                    site="file",
                    status=Status.FOUND,
                    category="file",
                    extra={"file": target, **meta},
                )
            )
            result.summary.update(meta)
        else:
            result.findings.append(Finding(site="file", status=Status.NOT_FOUND, category="file"))
        result.duration = time.perf_counter() - started
        return result


async def _generic_meta(path: Path) -> dict:
    meta: dict = {}
    stat = await asyncio.to_thread(path.stat)
    meta["size_bytes"] = stat.st_size
    meta["modified"] = time.ctime(stat.st_mtime)
    meta["created"] = time.ctime(stat.st_ctime)
    return meta
