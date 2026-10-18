"""Rendering und Textextraktion über PyMuPDF bzw. Ghostscript.

PyMuPDF-Seiten werden "normalisiert" (ohne /Rotate und /CropBox), damit Koordinaten
eindeutig in PDF-Koordinaten zurückgerechnet werden können.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

from .pdfdata import Box

GS_TIMEOUT_S = 180
MAX_RENDER_PX = 2500


class RenderError(RuntimeError):
    """Rendering technisch fehlgeschlagen (führt im Job zur Rückerstattung)."""


def open_normalized(path: str | Path) -> pymupdf.Document:
    doc = pymupdf.open(str(path))
    for page in doc:
        doc.xref_set_key(page.xref, "Rotate", "0")
        doc.xref_set_key(page.xref, "CropBox", "null")
    return doc


def to_pdf_box(page: pymupdf.Page, rect) -> Box:
    r = pymupdf.Rect(rect) * ~page.transformation_matrix
    return Box(min(r.x0, r.x1), min(r.y0, r.y1), max(r.x0, r.x1), max(r.y0, r.y1))


def to_fitz_rect(page: pymupdf.Page, box: Box) -> pymupdf.Rect:
    r = pymupdf.Rect(box.x0, box.y0, box.x1, box.y1) * page.transformation_matrix
    r.normalize()
    return r


@dataclass
class TextLine:
    text: str
    bbox: Box
    font_size: float


def text_lines(page: pymupdf.Page) -> list[TextLine]:
    lines: list[TextLine] = []
    data = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
            if not spans:
                continue
            text = "".join(s["text"] for s in spans).strip()
            box = None
            for s in spans:
                b = to_pdf_box(page, s["bbox"])
                box = b if box is None else Box(min(box.x0, b.x0), min(box.y0, b.y0),
                                                max(box.x1, b.x1), max(box.y1, b.y1))
            lines.append(TextLine(text, box, min(s["size"] for s in spans)))
    return lines


def render_rgb(page: pymupdf.Page, region: Box, dpi: float) -> np.ndarray:
    """Rendert einen Seitenausschnitt (PDF-Koordinaten) als RGB-Array (H, W, 3)."""
    clip = to_fitz_rect(page, region)
    longest_in = max(clip.width, clip.height) / 72
    dpi = min(dpi, MAX_RENDER_PX / longest_in) if longest_in > 0 else dpi
    pix = page.get_pixmap(dpi=max(int(dpi), 1), clip=clip, colorspace=pymupdf.csRGB, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)


def ghostscript_cmyk(path: str | Path, dpi: float) -> list[np.ndarray]:
    """Rendert alle Seiten mit Ghostscript nach CMYK. Rückgabe: Arrays (H, W, 4) in Prozent."""
    gs = shutil.which("gs") or shutil.which("gswin64c")
    if gs is None:
        raise RenderError("Ghostscript ist nicht installiert")
    with tempfile.TemporaryDirectory(prefix="druckcheck-gs-") as tmp:
        out = Path(tmp) / "page_%04d.tif"
        cmd = [gs, "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dNOINTERPOLATE",
               "-sDEVICE=tiff32nc", f"-r{max(int(dpi), 1)}", f"-sOutputFile={out}", str(path)]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=GS_TIMEOUT_S)
        except subprocess.TimeoutExpired as exc:
            raise RenderError("Ghostscript-Zeitüberschreitung") from exc
        if proc.returncode != 0:
            raise RenderError(f"Ghostscript-Fehler: {proc.stderr.decode(errors='replace')[:500]}")
        pages = []
        for tif in sorted(Path(tmp).glob("page_*.tif")):
            with Image.open(tif) as im:
                arr = np.asarray(im.convert("CMYK"), dtype=np.float32) * (100.0 / 255.0)
            pages.append(arr)
        return pages
