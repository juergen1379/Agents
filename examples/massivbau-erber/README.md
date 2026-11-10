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
| Referenzen | `#referenzen` | **Demofotos**, noch keine echten Projekte |
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
- [ ] Demofotos (Hero-Folien 2 und 3, Referenzen) durch echte Fotos und
      Projektdaten ersetzen, sonst Referenzen samt Menüpunkt mit `hidden` ausblenden
- [ ] Impressum: Komplementär-GmbH, Registergericht, Registernummer, USt-ID
- [ ] Datenschutzerklärung schreiben und prüfen lassen
- [ ] Entwurfs-Hinweis oben auf der Seite entfernen (`.draft-note` in `index.html`)
- [ ] Optional: Formular an einen Versanddienst anbinden. Aktuell öffnet es das
      E-Mail-Programm des Besuchers (kein Server nötig).

## Schrift

Red Hat Display (SIL Open Font License, siehe `assets/fonts/OFL.txt`), lokal
eingebunden.

## Demofotos

Die Bilder in `assets/demo/` stammen von Unsplash (Unsplash-Lizenz, freie
Nutzung) und zeigen keine Bauten des Betriebs. Sie sind auf der Seite als
„Demofoto" gekennzeichnet. Foto-IDs: `1541888946425-d81bb19240f5`,
`1517581177682-a085bb7ffb15`, `1449844908441-8829872d2607`,
`1523217582562-09d0def993a6`, `1504307651254-35680f356dfd`.

## Einzeldatei zum Verschicken

```bash
python3 build-standalone.py
```

erzeugt `dist/massivbau-erber-entwurf.html`: eine einzige Datei mit Schrift,
Bildern, Stil und Skript, die per Doppelklick im Browser läuft.
