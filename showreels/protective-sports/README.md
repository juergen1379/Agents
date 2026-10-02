# PROTECTIVE — 30s Motion-Graphics Showreel

Emotionaler 30-Sekunden-Imagefilm für [protective-sports.com](https://protective-sports.com/)
(Cycling & Nordic Sportswear aus München, seit 1991). Komplett prozedural gerendert
(Python + numpy + Pillow → ffmpeg), 1920×1080, 60 fps, H.264 + AAC 320 kbit/s,
inklusive eigens synthetisiertem Soundtrack (120 BPM, A-Moll), der auf die Schnitte getimt ist.

## Storyboard

| Zeit | Kapitel | Bild | Typo |
|---|---|---|---|
| 0–3 s | 01 Origin | Schwarz, glühende Linie, Herzschlag | „Jeder Morgen / ist ein Versprechen.“ |
| 3–8 s | 01 Origin | Linie öffnet sich wie ein Auge → Alpen im Sonnenaufgang, Parallax, Staub im Licht | „München · seit 1991 — LEIDENSCHAFT trifft Textilkompetenz.“ |
| 8–13 s | 02 Road | Drop + Flash: Straße in den Sonnenuntergang, Speed-Lines, Kamera-Shake | „CYCLING“, Trikots / Hosen / Jacken / Accessoires, „Für Sie & Ihn“ |
| 13–17,5 s | 03 Nordic | Whip-Pan in die blaue Stunde, verschneite Gipfel, Schneefall in 3 Ebenen | „NORDIC — Gemacht für den Winter.“ |
| 17,5–22,5 s | 04 Values | Drei Panels wischen ins Bild | Verantwortung · Qualität · Innovation |
| 22,5–26 s | 05 Craft | Makro-Gewebe mit Licht-Sweep | Zähler 1991 → 2026, „35 Jahre Leidenschaft“ |
| 26–30 s | 06 Protective | Impact, Glut, Bergsilhouette | Logo-Reveal PROTECTIVE, Claim, URL |

## Rendern

```bash
pip install numpy pillow
python3 render.py                    # -> out/protective_showreel.mp4 (60 fps)
FPS=30 python3 render.py             # schnellerer Draft
python3 render.py --preview 4.5 19   # Einzelbilder als PNG
```

## Echte Fotos der Website einsetzen

Lege JPGs in `photos/` ab — sie ersetzen automatisch den prozeduralen Hintergrund
der jeweiligen Szene (inkl. Ken-Burns-Fahrt, Typo und Effekte bleiben gleich):

`dawn.jpg` (Intro/Berge) · `road.jpg` (Cycling) · `nordic.jpg` (Winter) · `textile.jpg` (Stoff-Detail) · `logo.jpg` (Abschluss)

Die Values-Panels übernehmen die Bilder aus Dawn/Road/Nordic automatisch.

Fonts: Bebas Neue & Inter (SIL Open Font License, siehe `fonts/`).
