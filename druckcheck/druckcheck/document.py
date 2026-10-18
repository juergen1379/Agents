"""Gemeinsamer Prüfkontext: geöffnetes PDF, Seitenboxen, Formaterkennung, Inhaltsanalyse."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import pikepdf
import pymupdf

from .formats import FormatMatch, resolve_format
from .pdfdata import PageBoxes, PageContent, analyze_page, page_boxes
from .products import Product
from .render import open_normalized

MAX_PAGES_ANALYZED = 50


class PdfUnreadableError(Exception):
    """Datei ist kein lesbares PDF (beschädigt, verschlüsselt, leer)."""


@dataclass
class PageInfo:
    number: int                 # 1-basiert
    page: pikepdf.Page
    boxes: PageBoxes
    fmt: FormatMatch
    content: PageContent


@dataclass
class Document:
    path: Path
    product: Product
    pdf: pikepdf.Pdf
    pages: list[PageInfo] = field(default_factory=list)
    page_count: int = 0

    @cached_property
    def fitz(self) -> pymupdf.Document:
        return open_normalized(self.path)

    def fitz_page(self, number: int) -> pymupdf.Page:
        return self.fitz[number - 1]

    def close(self) -> None:
        if "fitz" in self.__dict__:
            self.fitz.close()
        self.pdf.close()


def load_document(path: str | Path, product: Product) -> Document:
    path = Path(path)
    try:
        pdf = pikepdf.open(path)
    except pikepdf.PasswordError as exc:
        raise PdfUnreadableError("Das PDF ist passwortgeschützt.") from exc
    except (pikepdf.PdfError, OSError, ValueError) as exc:
        raise PdfUnreadableError(f"Die Datei ist kein lesbares PDF ({exc}).") from exc
    if len(pdf.pages) == 0:
        pdf.close()
        raise PdfUnreadableError("Das PDF enthält keine Seiten.")
    doc = Document(path=path, product=product, pdf=pdf, page_count=len(pdf.pages))
    for i, page in enumerate(pdf.pages[:MAX_PAGES_ANALYZED]):
        boxes = page_boxes(page)
        doc.pages.append(PageInfo(
            number=i + 1,
            page=page,
            boxes=boxes,
            fmt=resolve_format(boxes, product),
            content=analyze_page(page),
        ))
    return doc
