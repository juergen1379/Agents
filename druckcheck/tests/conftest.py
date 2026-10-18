import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from druckcheck.document import load_document  # noqa: E402
from druckcheck.pdfbuilder import PdfBuilder  # noqa: E402
from druckcheck.products import get_product, load_products  # noqa: E402


@pytest.fixture
def products():
    return load_products()


@pytest.fixture
def build(tmp_path):
    """build(fn) → Pfad: fn(PdfBuilder) befüllt das PDF."""
    counter = {"n": 0}

    def _build(fn):
        counter["n"] += 1
        b = PdfBuilder()
        fn(b)
        return b.save(tmp_path / f"test_{counter['n']}.pdf")

    return _build


@pytest.fixture
def open_doc():
    docs = []

    def _open(path, product_id):
        doc = load_document(path, get_product(product_id))
        docs.append(doc)
        return doc

    yield _open
    for d in docs:
        d.close()


def a5_with_bleed(b: PdfBuilder, bleed=2.0, background=True):
    """A5-Seite (148 × 210) mit TrimBox und Beschnitt; gibt PageBuilder zurück."""
    p = b.page(148 + 2 * bleed, 210 + 2 * bleed)
    if bleed:
        p.set_trim_with_bleed(bleed)
    if background:
        p.rect(0, 0, 148 + 2 * bleed, 210 + 2 * bleed, cmyk=(0.1, 0, 0, 0))
    return p


def codes(result):
    return {f.code for f in result.findings}
