"""Laden und Validieren der Produktkonfiguration (products.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).with_name("products.yaml")


@dataclass(frozen=True)
class Safety:
    top: float
    right: float
    bottom: float
    left: float

    @classmethod
    def parse(cls, value) -> "Safety":
        if isinstance(value, (int, float)):
            return cls(value, value, value, value)
        return cls(value["top"], value["right"], value["bottom"], value["left"])

    @property
    def min(self) -> float:
        return min(self.top, self.right, self.bottom, self.left)


@dataclass(frozen=True)
class Product:
    id: str
    name: str
    trim_mm: tuple[float, float]
    bleed_mm: float
    safety: Safety
    min_dpi: float
    target_dpi: float
    viewing_distance_m: float
    max_tac: float
    max_pages: int
    allowed_scales: tuple[float, ...] = (1.0,)
    tolerance_mm: float = 0.5
    hairline_pt: float = 0.25
    hairline_red_pt: float = 0.1
    rgb_policy: str = "warn"
    spot_policy: str = "warn"
    extra: dict = field(default_factory=dict, compare=False)


def _validate(p: Product) -> None:
    w, h = p.trim_mm
    if w <= 0 or h <= 0:
        raise ValueError(f"{p.id}: Endformat muss positiv sein")
    if p.bleed_mm < 0 or p.safety.min < 0:
        raise ValueError(f"{p.id}: Beschnitt/Sicherheitsabstand dürfen nicht negativ sein")
    if p.min_dpi > p.target_dpi:
        raise ValueError(f"{p.id}: min_dpi darf nicht größer als target_dpi sein")
    if not p.allowed_scales or any(s <= 0 for s in p.allowed_scales):
        raise ValueError(f"{p.id}: allowed_scales ungültig")
    for policy in (p.rgb_policy, p.spot_policy):
        if policy not in ("warn", "error"):
            raise ValueError(f"{p.id}: Policy muss 'warn' oder 'error' sein")


def load_products(path: str | Path = DEFAULT_CONFIG) -> dict[str, Product]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    defaults = data.get("defaults", {})
    products: dict[str, Product] = {}
    for pid, raw in data["products"].items():
        cfg = {**defaults, **raw}
        product = Product(
            id=pid,
            name=cfg["name"],
            trim_mm=(float(cfg["trim_mm"][0]), float(cfg["trim_mm"][1])),
            bleed_mm=float(cfg["bleed_mm"]),
            safety=Safety.parse(cfg["safety_mm"]),
            min_dpi=float(cfg["min_dpi"]),
            target_dpi=float(cfg["target_dpi"]),
            viewing_distance_m=float(cfg["viewing_distance_m"]),
            max_tac=float(cfg["max_tac"]),
            max_pages=int(cfg["max_pages"]),
            allowed_scales=tuple(float(s) for s in cfg.get("allowed_scales", [1])),
            tolerance_mm=float(cfg.get("tolerance_mm", 0.5)),
            hairline_pt=float(cfg.get("hairline_pt", 0.25)),
            hairline_red_pt=float(cfg.get("hairline_red_pt", 0.1)),
            rgb_policy=cfg.get("rgb_policy", "warn"),
            spot_policy=cfg.get("spot_policy", "warn"),
        )
        _validate(product)
        products[pid] = product
    return products


def get_product(product_id: str, path: str | Path = DEFAULT_CONFIG) -> Product:
    products = load_products(path)
    try:
        return products[product_id]
    except KeyError:
        raise KeyError(
            f"Unbekanntes Produkt '{product_id}'. Verfügbar: {', '.join(sorted(products))}"
        ) from None
