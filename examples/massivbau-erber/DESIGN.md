# DESIGN.md · Massivbau Erber

Richtung: **„Werkplan"**. Die Seite sieht aus wie ein Ausführungsplan: weißes
Papier, feine orange Planlinien, schwere Anthrazit-Flächen. Was sonst ein Foto
wäre, ist eine Zeichnung. Abgeleitet aus der Visitenkarte (Logo, Farben,
Outline-Bildmarke im Anschnitt, Anthrazit-Balken mit Claim).

Hinweis: Die Richtung stützt sich auf die Visitenkarte, nicht auf einen
Vergleich echter Websites (UXKIN war in der Sitzung nicht erreichbar).

## Farbe

| Token | Wert | Rolle |
|---|---|---|
| `--paper` | `#FFFFFF` | Standardfläche, Hero, Karten |
| `--stone` | `#F6F4F1` | Wechselfläche (Leistungen, Betrieb) |
| `--ink` | `#3E413F` | Marken-Anthrazit: Text, dunkle Sektionen |
| `--ink-deep` | `#2B2D2C` | Footer, Hover auf dunklen Buttons |
| `--muted` | `#5F6361` | Nebentext auf hell (≥ 4,5:1) |
| `--line` | `#DAD7D2` | Rahmen, Trennlinien |
| `--orange` | `#DA5636` | Marken-Orange: **nur** Linien, Icons, Zeichnungen, große Ziffern |
| `--orange-strong` | `#C0452A` | Orange für Flächen mit weißem Text und für kleinen Text auf hell (5,1:1 auf Weiß) |
| `--orange-on-dark` | `#FF9272` | Oranger Text auf Anthrazit (4,7:1) |
| `--error` | `#B3261E` | Formularfehler |

Regeln: Marken-Orange `#DA5636` hat auf Weiß nur 3,9:1 und auf Anthrazit 2,6:1,
deshalb nie für kleinen Text. Kein Dark Mode: Der feste Wechsel
Weiß / Anthrazit / Orange ist der Kontrastrhythmus der Marke.

Sektionsrhythmus: Hero weiß → Claim-Balken Anthrazit → Leistungen Stone →
Warum massiv weiß → Ablauf Anthrazit → Referenzen weiß → Betrieb Stone →
Kontakt Orange (einziger Orange-Block) → Footer Anthrazit tief.

## Typografie

Eine Familie: **Red Hat Display** (variabel 300–900, lokal gehostet).

| Rolle | Größe | Gewicht | Sonstiges |
|---|---|---|---|
| Display / H1 | `clamp(2.6rem, 6.2vw, 5rem)` / 0.98 | 900 | −0.03em |
| H2 | `clamp(2rem, 3.8vw, 3.25rem)` / 1.05 | 800 | −0.02em |
| H3 | `1.3rem` / 1.25 | 800 | −0.01em |
| Eyebrow | `0.8125rem` | 700 | Versalien, 0.2em, Maßstrich davor |
| Lead | `1.25rem` / 1.5 | 500 | |
| Fließtext | `1.125rem` / 1.6 | 400 | max. 62 Zeichen |
| Klein / Plantext | `0.875rem` | 500–600 | 0.04em |
| Ablauf-Ziffern | `clamp(3.5rem, 8vw, 6.5rem)` | 900 | nur Outline, dekorativ |

## Abstände und Raster

4er-Skala: 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96 · 128.
Sektionsabstand `clamp(64px, 9vw, 128px)`. Inhaltsbreite 1200px,
Seitenrand `clamp(20px, 4vw, 40px)`.

## Form und Tiefe

- Radius 4px (blockig wie das „E"). Keine Pills.
- Linien: 2px Signaturlinien, 1.75px Icons, 1px Maße und Rahmen.
- Keine weichen Schatten. Hover = harter Versatz (6px Orange). Einzige
  Ausnahme: Overlays (Mega-Menü, Kontakt-Dock) haben einen knappen Schatten,
  damit sie sich vom Inhalt lösen.
- Muster: Läuferverband (Ziegelraster) als feines Linienmuster, nur in der
  Leistungs-Sektion.

## Komponenten

- **Button primär**: Fläche `--orange-strong`, Text weiß 700, Höhe 52px,
  Pfeil wandert beim Hover 4px. **Sekundär**: 2px Rahmen Anthrazit.
  **Auf dunkel**: weißer Rahmen. Fokus überall: 3px Ring, auf dunkel weiß.
- **Header**: sticky, 76px, Logo links, Ankermenü, Telefon-Button rechts.
  „Leistungen" öffnet ein Mega-Menü (Disclosure-Button, Esc schließt).
  Aktiver Anker: Unterstrich + Gewicht, nicht nur Farbe.
- **Hero-Slider**: drei Folien, je Text links + Planzeichnung rechts, die sich
  selbst zeichnet. Vor/Zurück, Punkte, Pause. Autoplay hält bei Hover, Fokus
  und `prefers-reduced-motion` an.
- **Leistungs-Kacheln**: asymmetrisches Raster, weiße Fläche, 1px Rahmen,
  orange Eckmarke oben links.
- **Ablauf**: nummerierte Liste auf Anthrazit, Outline-Ziffern, Treppen-Einzug.
- **Referenz-Platzhalter**: gestrichelter Rahmen, sichtbar als Platzhalter
  beschriftet. Nie mit erfundenen Projekten füllen.
- **Kontakt**: Orange-Block mit riesiger Telefonnummer, Formular auf weißer
  Karte. Felder 52px hoch, Label darüber, Fehler unter dem Feld.
- **Sticky-Kontakt**: Desktop schwebender Button unten rechts mit
  Aufklapp-Aktionen; mobil feste Leiste „Anrufen | Anfrage".

## Bild und Icon

Keine Stockfotos. Planzeichnungen als Inline-SVG (Stroke Orange 2px,
Beschriftung Anthrazit). Icons: eigene Outline-SVGs, 32er Raster, 1.75px,
runde Enden, als Bauteile gezeichnet. Echte Baustellenfotos können die
Referenz-Platzhalter später ersetzen.
