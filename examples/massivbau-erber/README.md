# Massivbau Erber · Landingpage (Entwurf)

Statische One-Page-Landingpage mit Ankermenü für die Massivbau Erber GmbH & Co KG,
Zeilarn. Reines HTML, CSS und JavaScript, kein Build-Schritt, keine externen
Dienste, keine Cookies.

## Ansehen

```bash
python3 -m http.server 8000
```

Dann `http://localhost:8000` öffnen. (Direkt als Datei geöffnet lädt der Browser
die Schrift nicht.)

## Aufbau

| Bereich | Anker | Inhalt |
|---|---|---|
| Header | – | Logo, Ankermenü mit Mega-Menü „Leistungen", Telefon-Button |
| Hero-Slider | `#start` | Drei Folien mit Planzeichnungen, Vor/Zurück, Punkte, Pause |
| Claim-Balken | – | „Starke Bauten für Generationen · Natürlich Massiv!" |
| Leistungen | `#leistungen` | Sechs Leistungen, asymmetrisches Raster |
| Warum massiv | `#massiv` | Wandschnitt mit vier Argumenten |
| Ablauf | `#ablauf` | Fünf Schritte |
| Referenzen | `#referenzen` | **Platzhalter**, noch keine echten Projekte |
| Betrieb | `#betrieb` | Kurztext und Visitenkarte Sandro Erber |
| Kontakt | `#kontakt` | Telefon, E-Mail, Anfrageformular |
| Footer | – | Anschrift, Kontakt, Impressum, Datenschutz |
| Sticky-Kontakt | – | Desktop: schwebender Button; Handy: Leiste „Anrufen / Anfrage" |

Gestaltungsregeln stehen in `DESIGN.md`.

## Woher die Inhalte stammen

Gesichert (von der Visitenkarte): Firmenname, früherer Name, Geschäftsführer,
Anschrift, Telefon, E-Mail, Claim, Logo und Farben.

Die bisherige Website war beim Bau nicht erreichbar. Alles Weitere ist
branchentypisch angenommen und im Entwurf als solches gekennzeichnet.

## Vor dem Livegang zu klären

- [ ] Die sechs Leistungen bestätigen oder anpassen
- [ ] Einsatzgebiet bestätigen („Landkreis Rottal-Inn und Umgebung")
- [ ] Ablauf-Texte bestätigen (Angebot, Ansprechpartner auf der Baustelle)
- [ ] Logo: nachgezeichnete Bildmarke durch die Original-Vektordatei ersetzen
- [ ] Referenzen: echte Fotos und Projektdaten liefern, sonst Sektion und
      Menüpunkt mit `hidden` ausblenden
- [ ] Impressum: Komplementär-GmbH, Registergericht, Registernummer, USt-ID
- [ ] Datenschutzerklärung schreiben und prüfen lassen
- [ ] Entwurfs-Hinweis oben auf der Seite entfernen (`.draft-note` in `index.html`)
- [ ] Optional: Formular an einen Versanddienst anbinden. Aktuell öffnet es das
      E-Mail-Programm des Besuchers (kein Server nötig).

## Schrift

Red Hat Display (SIL Open Font License, siehe `assets/fonts/OFL.txt`), lokal
eingebunden.
