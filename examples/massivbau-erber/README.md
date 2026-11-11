# Massivbau Erber · Landingpage (Entwurf)

Statische One-Page-Landingpage mit Ankermenü für die Massivbau Erber GmbH & Co KG,
Zeilarn. Reines HTML, CSS und JavaScript, kein Build-Schritt, keine externen
Dienste, keine Cookies.

## Ansehen

```bash
python3 -m http.server 8000
```

Dann `http://localhost:8000` öffnen. (Direkt als Datei geöffnet lädt der Browser
die Schrift nicht; dafür gibt es die Einzeldatei, siehe unten.)

## Aufbau

| Bereich | Anker | Inhalt |
|---|---|---|
| Header | – | Logo, Ankermenü mit Mega-Menü „Leistungen", Telefon-Button |
| Hero-Slider | `#start` | Drei Folien mit Fotos, Vor/Zurück, Punkte, Pause |
| Claim-Balken | – | Claim, Erfahrung, Teamgröße, Region |
| Leistungen | `#leistungen` | Sechs Kernkompetenzen mit Fotos |
| Vorteile | `#vorteile` | „Warum zu den Erbers?", vier Punkte |
| Digital | `#digital` | Digitale Arbeitsweise auf der Baustelle |
| Referenzen | `#referenzen` | Galerie mit neun Projektfotos, drei Kundenstimmen |
| Unternehmen | `#unternehmen` | Chronik seit 1995, Teamfoto, Visitenkarte, Kundenzitat |
| Karriere | `#karriere` | Stellenangebot Maurer-Azubis und Maurer-Gesellen (m/w/d) |
| Kontakt | `#kontakt` | Telefon, E-Mail, Instagram, Anfrageformular |
| Footer | – | Anschrift, Kontakt, Impressum, Datenschutz |
| Sticky-Kontakt | – | Desktop: schwebender Button; Handy: Leiste „Anrufen / Anfrage" |

Gestaltungsregeln stehen in `DESIGN.md`.

## Woher die Inhalte stammen

Texte, Fakten, Kundenstimmen, Impressumsdaten und alle Fotos stammen von
https://www.massivbau-erber.com/ (Stand November 2026). Die Texte wurden
gekürzt und neu geordnet, Aussagen und Zahlen aber nicht verändert. Logo,
Farben, Claim sowie Mobilnummer und E-Mail von Sandro Erber stammen von der
Visitenkarte.

Bewusst nicht übernommen: drei Stockfotos der alten Seite (Pexels) und die
Formulierung „garantierte Terminsicherheit" (übernommen ist „Zuverlässigkeit &
Termintreue").

## Vor der Veröffentlichung zu klären

- [ ] Texte und Bildauswahl freigeben
- [ ] Stellenangebot: Aufgaben, Anforderungen und „Das erwartet Dich" bestätigen
      (die Stellen stammen vom Banner, die Kurzbeschreibung ist ein Vorschlag)
- [ ] Bildunterschriften für die Referenzen liefern, falls gewünscht (Ort, Bauaufgabe)
- [ ] Einverständnis der abgebildeten Mitarbeiter für die Teamfotos prüfen
- [ ] Soll die Mobilnummer von Sandro Erber öffentlich auf der Seite stehen?
- [ ] Datenschutzerklärung schreiben und prüfen lassen (die alte Seite hat keine)
- [ ] Entwurfs-Hinweis oben auf der Seite entfernen (`.draft-note` in `index.html`)
- [ ] Optional: Formular an einen Versanddienst anbinden. Aktuell öffnet es das
      E-Mail-Programm des Besuchers (kein Server nötig).

## Einzeldatei zum Verschicken

```bash
python3 build-standalone.py
```

erzeugt `dist/massivbau-erber-entwurf.html`: eine einzige Datei mit Schrift,
Bildern, Stil und Skript, die per Doppelklick im Browser läuft.

## Schrift

Red Hat Display (SIL Open Font License, siehe `assets/fonts/OFL.txt`), lokal
eingebunden.
