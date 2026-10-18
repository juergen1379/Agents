import pytest

from druckcheck.products import Safety, get_product, load_products

EXPECTED = {
    "visitenkarte": (85, 55), "flyer_a6": (105, 148), "flyer_a5": (148, 210),
    "flyer_a4": (210, 297), "plakat_a1": (594, 841), "plakat_a0": (841, 1189),
    "grossflaeche_18_1": (3560, 2520), "bauzaunbanner": (3400, 1730), "rollup": (850, 2000),
}


def test_all_products_present_with_correct_trim(products):
    assert set(EXPECTED) <= set(products)
    for pid, trim in EXPECTED.items():
        assert products[pid].trim_mm == trim


def test_product_fields_plausible(products):
    for p in products.values():
        assert p.min_dpi <= p.target_dpi
        assert p.viewing_distance_m > 0
        assert 200 <= p.max_tac <= 400
        assert p.max_pages >= 1
        assert 1.0 in p.allowed_scales


def test_safety_per_side():
    rollup = get_product("rollup")
    assert rollup.safety.bottom == 100
    assert rollup.safety.top == 30
    assert rollup.safety.min == 30
    assert Safety.parse(3) == Safety(3, 3, 3, 3)


def test_unknown_product_raises():
    with pytest.raises(KeyError, match="Unbekanntes Produkt"):
        get_product("gibt_es_nicht")


def test_invalid_config_rejected(tmp_path):
    cfg = tmp_path / "p.yaml"
    cfg.write_text("""
products:
  kaputt:
    name: x
    trim_mm: [100, 100]
    bleed_mm: 2
    safety_mm: 3
    min_dpi: 300
    target_dpi: 200
    viewing_distance_m: 1
    max_tac: 300
    max_pages: 1
""", encoding="utf-8")
    with pytest.raises(ValueError, match="min_dpi"):
        load_products(cfg)
