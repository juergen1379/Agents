"""Registry aller technischen Prüfungen (Reihenfolge = Reihenfolge im Bericht)."""

from .color import check_colorspaces, check_tac
from .fonts import check_fonts
from .geometry import check_geometry
from .images import check_image_resolution
from .marks import check_crop_marks, check_hairlines
from .safety import check_safety_margin
from .transparency import check_overprint, check_transparency

ALL_CHECKS = [
    ("geometry", "Format & Beschnitt", check_geometry),
    ("images", "Bildauflösung", check_image_resolution),
    ("colorspace", "Farbraum", check_colorspaces),
    ("tac", "Gesamtfarbauftrag", check_tac),
    ("fonts", "Schriften", check_fonts),
    ("safety", "Sicherheitsabstand", check_safety_margin),
    ("hairlines", "Haarlinien", check_hairlines),
    ("transparency", "Transparenzen", check_transparency),
    ("overprint", "Überdrucken", check_overprint),
    ("crop_marks", "Schnittmarken", check_crop_marks),
]

__all__ = ["ALL_CHECKS"]
