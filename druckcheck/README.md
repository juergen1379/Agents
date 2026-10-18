# DruckCheck – technische Prüf-Engine (Etappe 1)

Deterministische Prüfung von Druck-PDFs **ohne KI** auf Basis von pikepdf, PyMuPDF und Ghostscript.
Ergebnis ist ein strukturierter Bericht mit Ampel (grün/gelb/rot) pro Prüfpunkt, der in den
nächsten Etappen in den Kunden-PDF-Bericht und die KI-Bewertung (Teil 2) einfließt.

## Installation

```bash
sudo apt-get install ghostscript        # wird für den Gesamtfarbauftrag benötigt
pip install -e ".[dev]"
```

## Benutzung

```bash
python -m druckcheck --produkte                              # verfügbare Produkte
python -m druckcheck samples/01_flyer_a5_canva_rgb_ohne_beschnitt.pdf -p flyer_a5
python -m druckcheck datei.pdf -p plakat_a1 --json           # maschinenlesbar
```

```python
from druckcheck.engine import run_checks, CheckExecutionError, PdfUnreadableError

report = run_checks("datei.pdf", "flyer_a5")     # strict=True: Absturz einer Prüfung → Exception
report.status            # Status.RED / YELLOW / GREEN
report.to_dict()         # JSON-fähig, inkl. Messwerten und stabilen Fehlercodes
```

* `PdfUnreadableError` – Datei kaputt, verschlüsselt oder leer (Kundenproblem → Hinweis an den Kunden).
* `CheckExecutionError` – eine Prüfung ist technisch abgestürzt (unser Problem → automatische Erstattung).

## Prüfungen

| Prüfung | Was wird gemessen | Rot | Gelb |
|---|---|---|---|
| **Format & Beschnitt** (`geometry`) | TrimBox/BleedBox bzw. MediaBox gegen Endformat ± 0,5 mm, Hoch/Quer, Maßstab (z. B. 1:10), Seitenzahl; gerendert: läuft das Motiv wirklich in den Beschnitt? | falsches Format, falscher Maßstab, kein Beschnitt, zu viele Seiten, Motiv endet auf ≥ 25 % einer Kante am Endformat | zu wenig Beschnitt, Motiv endet auf ≥ 5 % einer Kante, unterschiedliche Seitengrößen |
| **Bildauflösung** (`images`) | effektive dpi jedes platzierten Bildes **im Endformat** (CTM, Form-XObjects, Inline-Bilder, Maßstab) | < `min_dpi` | < `target_dpi` |
| **Farbraum** (`colorspace`) | Farbräume aller Bilder, Flächen, Linien, Texte, Verläufe (ICC, Separation, DeviceN, Indexed, Muster) | nur bei `rgb_policy/spot_policy: error` | RGB, Sonderfarben, Passermarkenfarbe, Lab |
| **Gesamtfarbauftrag** (`tac`) | Ghostscript-CMYK-Separation, Summe C+M+Y+K je Pixel, nur im Druckbereich (Endformat + Beschnitt) | > `max_tac` auf ≥ 1 cm² | > `max_tac` auf kleiner Fläche |
| **Schriften** (`fonts`) | tatsächlich verwendete Schriften (nicht nur deklarierte, unsichtbarer OCR-Text ausgenommen) | nicht eingebettet | – |
| **Sicherheitsabstand** (`safety`) | Textzeilen und Bilder vs. Sicherheitszone (auch je Seite unterschiedlich, z. B. Rollup unten 10 cm) | Text ragt über das Endformat | Text oder Logo im Sicherheitsabstand |
| **Haarlinien** (`hairlines`) | effektive Konturstärke (inkl. Skalierung, Endformat-Maßstab), nur Linien im Endformat | ≤ 0,1 pt oder 0 pt | < 0,25 pt |
| **Transparenzen** (`transparency`) | Deckkraft, Füllmethoden, weiche Masken, Bilder mit Alphakanal | – | vorhanden |
| **Überdrucken** (`overprint`) | weiße Flächen/Texte/Linien mit Überdrucken (verschwinden im Druck) | vorhanden | – |
| **Schnittmarken** (`crop_marks`) | kurze achsparallele Linien in Verlängerung der Endformatkanten, Passermarkenfarbe | Marken im Druck-/Beschnittbereich | Marken außerhalb der BleedBox (sauberes PDF/X) |

Jede Beanstandung hat einen stabilen `code` (z. B. `geometry.no_bleed`, `fonts.not_embedded`).
Daran hängen in der Bericht-Etappe die laienverständlichen Erklärungen und Lösungsanleitungen
(„So stellst du in Canva den Beschnitt ein …“).

## Produktkonfiguration

`druckcheck/products.yaml` – Endformat, Beschnitt, Sicherheitsabstand (einheitlich oder je Seite),
Mindest-/Ziel-dpi, Betrachtungsdistanz, max. Farbauftrag, max. Seitenzahl, zulässige Maßstäbe.
Neue Produkte = neuer YAML-Eintrag, kein Code.

## Beispiel-PDFs

`python samples/generate_samples.py` erzeugt sie neu (Definitionen in `druckcheck/samples.py`):

| Datei | Produkt | Typische Fehler | Ergebnis |
|---|---|---|---|
| `00_flyer_a5_korrekt.pdf` | Flyer A5 | – (Referenz) | alles grün |
| `01_flyer_a5_canva_rgb_ohne_beschnitt.pdf` | Flyer A5 | kein Beschnitt, RGB, Text am Rand | 🔴 Format · 🟡 Farbraum · 🟡 Sicherheitsabstand |
| `02_plakat_a1_unscharf_farbauftrag.pdf` | Plakat A1 | Foto mit 34 dpi, 400 % Farbauftrag | 🔴 Bildauflösung · 🔴 Farbauftrag |
| `03_visitenkarte_schrift_haarlinie.pdf` | Visitenkarte | Schrift nicht eingebettet, 0,1-pt-Linie, Hintergrund nicht im Beschnitt, Text angeschnitten | 🔴 Format · 🔴 Schriften · 🔴 Sicherheitsabstand · 🔴 Haarlinien |
| `04_flyer_a6_schnittmarken_transparenz.pdf` | Flyer A6 | mit Schnittmarken exportiert, HKS-Sonderfarbe, Transparenz | 🔴 Schnittmarken · 🟡 Farbraum · 🟡 Transparenz |
| `05_bauzaunbanner_falsches_format_ueberdrucken.pdf` | Bauzaunbanner | falsches Seitenverhältnis, weißer Text auf Überdrucken, RGB | 🔴 Format · 🔴 Überdrucken · 🟡 Farbraum · 🟡 Sicherheitsabstand |

## Tests

```bash
pytest -q          # 103 Tests, inkl. Ende-zu-Ende-Lauf über alle Beispiel-PDFs
```

Test-PDFs werden mit `druckcheck/pdfbuilder.py` gezielt erzeugt (exakte Boxen, Farbräume,
Bildauflösungen, eingebettete/nicht eingebettete Schriften usw.).

## Bekannte Grenzen (bewusst, für spätere Etappen)

* Schnittmarken, die als **Pixel in ein Bild** eingerechnet sind, werden nicht erkannt.
* Bilder mit **JPEG 2000 ohne Farbraumangabe** werden als „Farbraum unbekannt“ gemeldet.
* Der Farbauftrag von **RGB-Inhalten** hängt von Ghostscripts Standard-Umrechnung ab
  (ohne Ausgabeprofil der Druckerei).
* Glyphenprozeduren in Type3-Schriften werden nicht auf Farben/Linien untersucht.
* Analyse ist auf 50 Seiten und 3 Mio. Content-Operationen pro Seite begrenzt (Schutz vor Missbrauch).
