from druckcheck.checks.safety import check_safety_margin
from druckcheck.models import Status

from conftest import a5_with_bleed, codes

# A5 mit 2 mm Beschnitt: Endformat liegt bei x = 2…150, y = 2…212 (mm)


def _check(build, open_doc, fn, product="flyer_a5"):
    return check_safety_margin(open_doc(build(fn), product))


def test_text_inside_safe_area(build, open_doc):
    result = _check(build, open_doc, lambda b: a5_with_bleed(b).text(20, 100, "Mitte", size_pt=12))
    assert result.status == Status.GREEN


def test_text_in_safety_margin_yellow(build, open_doc):
    result = _check(build, open_doc, lambda b: a5_with_bleed(b).text(3.5, 100, "Rand", size_pt=10))
    assert result.status == Status.YELLOW
    (f,) = result.findings
    assert f.code == "safety.text_in_margin"
    assert 0 < f.data["lines"][0]["distance_mm"] < 3


def test_text_crossing_trim_red(build, open_doc):
    result = _check(build, open_doc, lambda b: a5_with_bleed(b).text(130, 100, "Viel zu lang", size_pt=12))
    assert result.status == Status.RED
    assert "safety.text_cut" in codes(result)


def test_text_entirely_in_bleed_ignored(build, open_doc):
    result = _check(build, open_doc, lambda b: a5_with_bleed(b).text(20, 0.2, "x", size_pt=3))
    assert result.status == Status.GREEN


def test_logo_near_edge_yellow(build, open_doc):
    result = _check(build, open_doc, lambda b: a5_with_bleed(b).image(3, 180, 20, 20, px=(300, 300)))
    assert "safety.image_in_margin" in codes(result)


def test_full_bleed_image_not_flagged(build, open_doc):
    result = _check(build, open_doc, lambda b: a5_with_bleed(b).image(0, 100, 152, 114, px=(1800, 1350)))
    assert result.status == Status.GREEN


def test_rollup_bottom_margin(build, open_doc):
    # Rollup: unten 100 mm Sicherheitsabstand – Text 60 mm über der Unterkante ist zu tief
    def fn(b):
        p = b.page(860, 2010).set_trim_with_bleed(5)
        p.text(300, 65, "Zu tief", size_pt=60)
        p.text(300, 1000, "Gut", size_pt=60)
    result = _check(build, open_doc, fn, "rollup")
    assert result.status == Status.YELLOW
    lines = result.findings[0].data["lines"]
    assert [entry["text"] for entry in lines] == ["Zu tief"]


def test_wrong_format_not_checkable(build, open_doc):
    result = _check(build, open_doc, lambda b: b.page(100, 100), "flyer_a5")
    assert codes(result) == {"safety.not_checked"}
