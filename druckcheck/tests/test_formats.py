import pikepdf
import pytest

from druckcheck.formats import find_matching_products, resolve_format
from druckcheck.pdfdata import page_boxes
from druckcheck.products import get_product


def _fmt(build, fn, product_id):
    path = build(fn)
    with pikepdf.open(path) as pdf:
        return resolve_format(page_boxes(pdf.pages[0]), get_product(product_id))


def test_trimbox_exact(build):
    fmt = _fmt(build, lambda b: b.page(152, 214).set_trim_with_bleed(2), "flyer_a5")
    assert fmt.ok and fmt.scale_allowed and fmt.source == "trimbox"
    assert fmt.scale == 1
    assert fmt.min_bleed_final_mm == pytest.approx(2, abs=0.01)


def test_mediabox_with_bleed_no_trimbox(build):
    fmt = _fmt(build, lambda b: b.page(152, 214), "flyer_a5")
    assert fmt.ok and fmt.source == "mediabox"
    assert fmt.min_bleed_final_mm == pytest.approx(2, abs=0.01)


def test_mediabox_without_bleed(build):
    fmt = _fmt(build, lambda b: b.page(148, 210), "flyer_a5")
    assert fmt.ok
    assert fmt.min_bleed_final_mm == pytest.approx(0, abs=0.01)


def test_within_tolerance(build):
    fmt = _fmt(build, lambda b: b.page(148.4, 209.7), "flyer_a5")
    assert fmt.ok and fmt.scale_allowed


def test_landscape_accepted(build):
    fmt = _fmt(build, lambda b: b.page(214, 152), "flyer_a5")
    assert fmt.ok and fmt.landscape


def test_one_to_ten_scale_for_18_1(build):
    fmt = _fmt(build, lambda b: b.page(356, 252), "grossflaeche_18_1")
    assert fmt.ok and fmt.scale_allowed
    assert fmt.scale == pytest.approx(0.1)


def test_proportional_but_not_allowed_scale(build):
    # A4 statt A1: proportional, Faktor 1/2,83
    fmt = _fmt(build, lambda b: b.page(210, 297), "plakat_a1")
    assert fmt.ok and not fmt.scale_allowed
    assert fmt.scale == pytest.approx(210 / 594, rel=1e-3)


def test_wrong_format(build):
    fmt = _fmt(build, lambda b: b.page(148, 210), "visitenkarte")
    assert not fmt.ok and fmt.trim is None


def test_wrong_trimbox(build):
    fmt = _fmt(build, lambda b: b.page(204, 214).set_trim_with_bleed(2), "flyer_a5")
    assert not fmt.ok and fmt.source == "trimbox"


def test_page_with_crop_mark_area_centered(build):
    # Endformat + 12 mm Rand (Beschnitt + Marken) → Endformat mittig erkannt
    fmt = _fmt(build, lambda b: b.page(105 + 24, 148 + 24), "flyer_a6")
    assert fmt.ok
    assert fmt.trim.as_mm() == pytest.approx([12, 12, 117, 160], abs=0.01)


def test_find_matching_products(products):
    assert "Flyer DIN A5" in find_matching_products(148, 210, products)
    assert "Flyer DIN A5" in find_matching_products(152, 214, products)
    assert find_matching_products(123, 45, products) == []
