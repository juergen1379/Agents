"""Beispiel-PDFs mit typischen Fehlern – für Tests, Demo und den Beispielbericht.

Jedes Beispiel definiert das Produkt und die erwarteten Ampelfarben pro Prüfung.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .pdfbuilder import PdfBuilder


@dataclass(frozen=True)
class Sample:
    file_name: str
    product_id: str
    description: str
    build: Callable[[Path], Path]
    expected: dict[str, str]     # check_id -> green/yellow/red (nicht genannte: green)


def _flyer_a5_ok(path: Path) -> Path:
    b = PdfBuilder()
    p = b.page(152, 214).set_trim_with_bleed(2)                 # 148 × 210 + 2 mm Beschnitt
    p.rect(0, 0, 152, 214, cmyk=(0.05, 0.02, 0, 0))             # Hintergrund bis in den Beschnitt
    p.image(0, 107, 152, 107, px=(1800, 1267))                  # ~300 dpi, randabfallend
    p.rect(12, 30, 128, 50, cmyk=(0.9, 0.3, 0, 0.1))
    p.text(18, 60, "Sommerfest 2026", size_pt=28, cmyk=(0, 0, 0, 0))
    p.text(18, 40, "Samstag, 4. Juli - Stadtpark", size_pt=12, cmyk=(0, 0, 0, 0))
    p.text(12, 12, "www.beispiel-verein.de", size_pt=9)
    return b.save(path)


def _flyer_a5_canva_rgb(path: Path) -> Path:
    """Typischer Canva-Export "PDF Standard": RGB, kein Beschnitt, Text am Rand."""
    b = PdfBuilder()
    p = b.page(148, 210)
    p.rect(0, 0, 148, 210, rgb=(1, 0.85, 0.2))
    p.image(0, 105, 148, 105, px=(1750, 1240), mode="RGB")
    p.text(15, 70, "Flohmarkt", size_pt=36, rgb=(0.1, 0.1, 0.4))
    p.text(1.5, 4, "Eintritt frei - Infos unter 0123 456789", size_pt=9, rgb=(0, 0, 0))
    return b.save(path)


def _plakat_a1_unscharf(path: Path) -> Path:
    """Foto aus dem Internet auf A1 hochgezogen, dazu ein "sattes" Schwarz mit 400 %."""
    b = PdfBuilder()
    p = b.page(600, 847).set_trim_with_bleed(3)                 # 594 × 841 + 3 mm
    p.rect(0, 0, 600, 847, cmyk=(0, 0, 0, 0.05))
    p.image(0, 300, 600, 547, px=(800, 730))                    # ~34 dpi
    p.rect(0, 0, 600, 300, cmyk=(1, 1, 1, 1))                   # 400 % Farbauftrag
    p.text(40, 200, "KONZERT", size_pt=180, cmyk=(0, 0, 0, 0))
    p.text(40, 120, "12. Mai - Stadthalle", size_pt=60, cmyk=(0, 0, 0, 0))
    return b.save(path)


def _visitenkarte_word(path: Path) -> Path:
    """Selbst gebaute Visitenkarte: Schrift nicht eingebettet, Haarlinie, Hintergrund
    endet am Endformat, Telefonnummer ragt über den Rand."""
    b = PdfBuilder()
    p = b.page(89, 59)                                          # 85 × 55 + 2 mm, ohne TrimBox
    p.rect(2, 2, 85, 55, cmyk=(0.7, 0, 0.3, 0))                 # nur bis zum Endformat
    p.text(8, 40, "Anna Beispiel", size_pt=14, embedded=False, cmyk=(0, 0, 0, 0))
    p.text(8, 33, "Fotografie", size_pt=9, embedded=False, cmyk=(0, 0, 0, 0))
    p.line(8, 30, 60, 30, width_pt=0.1, cmyk=(0, 0, 0, 0))      # Zierlinie, 0,1 pt
    p.text(3.0, 4.0, "Tel. 0170 1234567 - anna@beispiel.de", size_pt=7, embedded=False,
           cmyk=(0, 0, 0, 0))
    p.text(60, 1.0, "Rückseite beachten", size_pt=6, embedded=False, cmyk=(0, 0, 0, 0))
    return b.save(path)


def _flyer_a6_schnittmarken(path: Path) -> Path:
    """Export "mit Schnittmarken": Seite größer als Endformat + Beschnitt, Marken in
    Passermarkenfarbe, dazu Transparenz und eine HKS-Sonderfarbe."""
    b = PdfBuilder()
    margin = 12.0                                               # 2 mm Beschnitt + Markenbereich
    w, h = 105 + 2 * margin, 148 + 2 * margin
    p = b.page(w, h)
    trim = (margin, margin, margin + 105, margin + 148)
    p.rect(margin - 2, margin - 2, 109, 152, cmyk=(0, 0.2, 0.9, 0))   # Hintergrund mit 2 mm Beschnitt
    p.spot_color("HKS", "HKS 43 K", (1, 0.6, 0, 0))
    p.rect(margin + 10, margin + 90, 85, 40, spot=("HKS", 1))
    p.extgstate("Soft", ca=0.6, CA=0.6)
    p.rect(margin + 20, margin + 40, 65, 40, cmyk=(0, 1, 0, 0), gs="Soft")
    p.text(margin + 15, margin + 20, "Jetzt anmelden!", size_pt=16)
    p.crop_marks(trim, offset_mm=3, length_mm=5, width_pt=0.25)
    return b.save(path)


def _bauzaunbanner_falsch(path: Path) -> Path:
    """Banner im falschen Seitenverhältnis (1:10 angelegt mit 300 × 170 mm statt
    340 × 173 mm), weißer Text auf "Überdrucken", RGB-Foto."""
    b = PdfBuilder()
    p = b.page(300, 170)
    p.rect(0, 0, 300, 170, cmyk=(0.8, 0.1, 0, 0))
    p.image(180, 20, 100, 130, px=(4000, 5200), mode="RGB")
    p.extgstate("OP", OP=True, op=True, OPM=1)
    p.text(20, 100, "Hier entsteht", size_pt=40, cmyk=(0, 0, 0, 0), gs="OP")
    p.text(20, 70, "Ihr neues Zuhause", size_pt=40, cmyk=(0, 0, 0, 0), gs="OP")
    return b.save(path)


SAMPLES: list[Sample] = [
    Sample("00_flyer_a5_korrekt.pdf", "flyer_a5",
           "Referenz: korrekt angelegter A5-Flyer (alles grün).",
           _flyer_a5_ok, {}),
    Sample("01_flyer_a5_canva_rgb_ohne_beschnitt.pdf", "flyer_a5",
           "Canva-Export ohne Beschnitt, in RGB, Text zu nah am Rand.",
           _flyer_a5_canva_rgb,
           {"geometry": "red", "colorspace": "yellow", "safety": "yellow"}),
    Sample("02_plakat_a1_unscharf_farbauftrag.pdf", "plakat_a1",
           "Hochgezogenes Internetfoto (34 dpi) und 400 % Farbauftrag.",
           _plakat_a1_unscharf,
           {"images": "red", "tac": "red"}),
    Sample("03_visitenkarte_schrift_haarlinie.pdf", "visitenkarte",
           "Schrift nicht eingebettet, Haarlinie, Hintergrund nicht im Beschnitt, Text am Rand.",
           _visitenkarte_word,
           {"geometry": "red", "fonts": "red", "safety": "red", "hairlines": "red"}),
    Sample("04_flyer_a6_schnittmarken_transparenz.pdf", "flyer_a6",
           "Mit Schnittmarken exportiert, Sonderfarbe HKS 43 K, Transparenz.",
           _flyer_a6_schnittmarken,
           {"crop_marks": "red", "colorspace": "yellow", "transparency": "yellow"}),
    Sample("05_bauzaunbanner_falsches_format_ueberdrucken.pdf", "bauzaunbanner",
           "Falsches Seitenverhältnis, weißer Text überdruckt, RGB-Foto.",
           _bauzaunbanner_falsch,
           {"geometry": "red", "colorspace": "yellow", "overprint": "red", "safety": "yellow"}),
]


def generate_all(directory: str | Path) -> list[Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return [s.build(directory / s.file_name) for s in SAMPLES]
