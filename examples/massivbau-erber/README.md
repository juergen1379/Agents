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
- [ ] Hosting mit PHP 8.1+ wählen und den Kundenzugang unter `/admin/` einrichten
- [ ] Entwurfs-Hinweis oben auf der Seite entfernen (`.draft-note` in `index.html`)
- [ ] Optional: Formular an einen Versanddienst anbinden. Aktuell öffnet es das
      E-Mail-Programm des Besuchers (kein Server nötig).

## Kundenzugang: Texte und Bilder selbst ändern

Unter `/admin/` liegt ein passwortgeschützter Bearbeitungsbereich. Der Kunde
sieht dort die Website, klickt Texte an und ändert sie direkt, klickt Bilder an
und lädt ein neues hoch. „Speichern" schreibt die Änderungen in die
`index.html`. Die Seite bleibt statisch und schnell, es gibt keine Datenbank.

**Voraussetzungen beim Hoster:** PHP 8.1 oder neuer (üblich bei All-Inkl,
IONOS, Strato, Hetzner), empfohlen mit der Bild-Erweiterung GD. Schreibrechte
für `index.html`, `admin/data/` und `assets/uploads/`. HTTPS.

**Einrichtung nach dem Hochladen:**

1. `https://<domain>/admin/` aufrufen. Beim ersten Aufruf erscheint „Zugang
   einrichten". Dort das Passwort festlegen (mindestens 12 Zeichen). Das bitte
   **sofort nach dem Hochladen** tun, denn bis dahin kann jeder Besucher dieser
   Adresse das Passwort setzen.
2. Passwort an den Kunden übergeben. Er kann es im Bearbeitungsbereich ändern.

**Was der Kunde ändern kann:** rund 100 Textstellen (Überschriften, Absätze,
Listenpunkte, Kundenstimmen, Chronik, Stellenangebot) und alle 20 Fotos samt
Bildbeschreibung. Leistungstitel werden im Mega-Menü automatisch mitgeändert.

**Was er selbst hinzufügen kann:** In acht Listen legt „+" einen neuen Eintrag
an (als Kopie des Eintrags daneben), „×" löscht ihn, die Pfeile verschieben
ihn: Galeriebilder, Kundenstimmen, Chronik, Vorteile, Digital-Punkte und die
drei Aufzählungen im Stellenangebot. Jede Liste behält mindestens einen und
höchstens 60 Einträge.

**Was er nicht ändern kann:** Aufbau und Reihenfolge der Abschnitte, Menü,
Leistungs-Kacheln, Hero-Folien, Stellenkarten, Telefonnummern,
E-Mail-Adressen, Anschrift, Schaltflächen, Impressum und Datenschutz. Neue
Abschnitte oder ganz neue Elementarten legt weiterhin die Agentur an.

**Sicherheit und Sicherung:**

- Vor jedem Speichern wird der alte Stand gesichert (die letzten 30 Stände,
  wiederherstellbar über „Sicherungen").
- Texte werden als reiner Text gespeichert, HTML wird maskiert.
- Bilder werden geprüft, auf höchstens 1600 px Breite verkleinert und neu
  gespeichert. Erlaubt sind JPG, PNG und WebP bis 12 MB.
- Nach fünf falschen Passwörtern ist die Anmeldung für 15 Minuten gesperrt.
- Passwort vergessen: die Datei `admin/data/config.php` per FTP löschen und die
  Einrichtung neu durchlaufen.

**Neue bearbeitbare Stellen:** ein Text-Element ohne Kind-Elemente bekommt
`data-edit="eindeutiger-schluessel"`, ein Bild `data-edit-img="img-name"`.
Eine erweiterbare Liste bekommt `data-repeat="name"` am Behälter, `data-item`
an jedem Eintrag und die Kommentar-Marken `<!--repeat:name-->` sowie
`<!--item:name-->` (siehe Galerie in `index.html`). Listen dürfen nicht
ineinander liegen, und der Eintrag selbst darf kein `data-edit` tragen.

**Lokal ausprobieren:**

```bash
php -S localhost:8000
```

Dann `http://localhost:8000/admin/` öffnen.

## Einzeldatei zum Verschicken

```bash
python3 build-standalone.py
```

erzeugt `dist/massivbau-erber-entwurf.html`: eine einzige Datei mit Schrift,
Bildern, Stil und Skript, die per Doppelklick im Browser läuft.

Derselbe Befehl erzeugt `dist/massivbau-erber-kundenzugang-demo.html`: eine
Demo des Kundenzugangs ohne Server. Oben auf „Bearbeiten" klicken, Passwort
`erber-demo`. Anmeldung, Upload und Speichern sind dort im Browser nachgestellt;
Änderungen bleiben nur im Speicher dieses Browsers und lassen sich über
„Sicherungen" zurücksetzen. Die Quellen der Demo liegen in `demo/`.

## Schrift

Red Hat Display (SIL Open Font License, siehe `assets/fonts/OFL.txt`), lokal
eingebunden.
