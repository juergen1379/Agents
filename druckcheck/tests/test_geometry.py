from druckcheck.checks.geometry import check_geometry
from druckcheck.models import Status

from conftest import a5_with_bleed, codes


def test_correct_a5_is_green(build, open_doc):
    doc = open_doc(build(lambda b: a5_with_bleed(b)), "flyer_a5")
    result = check_geometry(doc)
    assert result.status == Status.GREEN
    assert "geometry.bleed_ok" in codes(result)


def test_no_bleed_is_red(build, open_doc):
    doc = open_doc(build(lambda b: a5_with_bleed(b, bleed=0)), "flyer_a5")
    result = check_geometry(doc)
    assert result.status == Status.RED
    assert "geometry.no_bleed" in codes(result)


def test_too_little_bleed_is_yellow(build, open_doc):
    doc = open_doc(build(lambda b: a5_with_bleed(b, bleed=1)), "flyer_a5")
    result = check_geometry(doc)
    assert result.status == Status.YELLOW
    assert "geometry.too_little_bleed" in codes(result)


def test_wrong_format_red_with_hint(build, open_doc):
    doc = open_doc(build(lambda b: a5_with_bleed(b)), "visitenkarte")
    result = check_geometry(doc)
    assert result.status == Status.RED
    (f,) = [f for f in result.findings if f.code == "geometry.wrong_format"]
    assert "Flyer DIN A5" in f.data["matches"]
    assert "Flyer DIN A5" in f.message


def test_proportional_other_din_size_red_with_hint(build, open_doc):
    # DIN-Formate sind alle proportional: A5-Datei für A6-Flyer ist trotzdem falsch
    doc = open_doc(build(lambda b: a5_with_bleed(b)), "flyer_a6")
    result = check_geometry(doc)
    assert result.status == Status.RED
    (f,) = [f for f in result.findings if f.code == "geometry.scaled"]
    assert "Flyer DIN A5" in f.message


def test_too_many_pages(build, open_doc):
    def fn(b):
        for _ in range(3):
            a5_with_bleed(b)
    result = check_geometry(open_doc(build(fn), "flyer_a5"))
    assert "geometry.too_many_pages" in codes(result)
    assert result.status == Status.RED


def test_scaled_proportional_is_red(build, open_doc):
    doc = open_doc(build(lambda b: b.page(210, 297).rect(0, 0, 210, 297, cmyk=(0, 0, 0, .2))), "plakat_a1")
    result = check_geometry(doc)
    assert "geometry.scaled" in codes(result)
    assert result.status == Status.RED


def test_background_not_extended_into_bleed(build, open_doc):
    def fn(b):
        p = a5_with_bleed(b, background=False)
        p.rect(2, 2, 148, 210, cmyk=(0.6, 0, 0, 0))     # nur Endformat gefüllt
    result = check_geometry(open_doc(build(fn), "flyer_a5"))
    assert "geometry.bleed_not_filled" in codes(result)
    assert result.status == Status.RED


def test_one_side_not_extended_is_flagged(build, open_doc):
    def fn(b):
        p = a5_with_bleed(b, background=False)
        p.rect(0, 0, 150, 214, cmyk=(0.6, 0, 0, 0))     # rechts fehlt der Beschnitt
    result = check_geometry(open_doc(build(fn), "flyer_a5"))
    (f,) = [f for f in result.findings if f.code == "geometry.bleed_not_filled"]
    assert f.data["fraction_per_side"]["right"] > 0.9
    assert f.data["fraction_per_side"]["left"] == 0


def test_white_background_is_fine(build, open_doc):
    def fn(b):
        p = a5_with_bleed(b, background=False)
        p.text(20, 100, "Nur Text auf weiß", size_pt=14)
    result = check_geometry(open_doc(build(fn), "flyer_a5"))
    assert result.status == Status.GREEN


def test_18_1_at_one_to_ten(build, open_doc):
    doc = open_doc(build(lambda b: b.page(356, 252)), "grossflaeche_18_1")
    result = check_geometry(doc)
    assert result.status == Status.GREEN
    assert "geometry.scale_info" in codes(result)
