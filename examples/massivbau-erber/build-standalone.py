#!/usr/bin/env python3
"""Baut aus index.html, styles.css, script.js und den Schriften eine einzige HTML-Datei
zum Verschicken: dist/massivbau-erber-entwurf.html (läuft per Doppelklick, ohne Server)."""
import base64, pathlib, re

root = pathlib.Path(__file__).parent
read = lambda p: (root / p).read_text(encoding="utf-8")

html, css, js = read("index.html"), read("styles.css"), read("script.js")

def data_uri(path, mime):
    return "data:%s;base64,%s" % (mime, base64.b64encode((root / path).read_bytes()).decode())

# Schriften und Favicon einbetten
css = re.sub(r'url\("(assets/fonts/[^"]+\.woff2)"\)',
             lambda m: 'url("%s")' % data_uri(m.group(1), "font/woff2"), css)
css += """
/* Nur in der Einzeldatei: Impressum und Datenschutz als einblendbare Abschnitte */
.legal-inline { display: none; background: var(--paper); color: var(--ink); }
.legal-inline:target { display: block; }
"""

def legal(page, anchor):
    body = re.search(r'<div class="container">(.*?)</div>\s*</main>', read(page), re.S).group(1)
    body = body.replace("<h1>", "<h2>").replace("</h1>", "</h2>").replace("<h2>", "<h3>", 0)
    return ('<section class="legal legal-inline" id="%s" aria-label="%s"><div class="container">%s'
            '<p><a class="back-link" href="#start">Nach oben</a></p></div></section>\n'
            % (anchor, anchor.capitalize(), body))

def swap(text, old, new, count=None):
    assert old in text, old
    return text.replace(old, new) if count is None else text.replace(old, new, count)

html = re.sub(r'\s*<link rel="preload"[^>]+>', "", html)
html = re.sub(r'src="(assets/img/[^"]+\.webp)"',
              lambda m: 'src="%s"' % data_uri(m.group(1), "image/webp"), html)
html = swap(html, '<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">',
            '<link rel="icon" href="%s">' % data_uri("assets/favicon.svg", "image/svg+xml"))
html = swap(html, '<link rel="stylesheet" href="styles.css">', "<style>\n%s</style>" % css)
html = swap(html, '<script src="script.js" defer></script>', "<script>\n%s</script>" % js)
html = swap(html, 'href="impressum.html"', 'href="#impressum"')
html = swap(html, 'href="datenschutz.html"', 'href="#datenschutz"')
html = swap(html, "<footer class=\"site-footer\">",
            legal("impressum.html", "impressum") + legal("datenschutz.html", "datenschutz")
            + "<footer class=\"site-footer\">")
html = swap(html, "<head>", '<head>\n  <meta name="robots" content="noindex">')

plain = html
out = root / "dist" / "massivbau-erber-entwurf.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding="utf-8")
print(out, "%.0f KB" % (out.stat().st_size / 1024))

# ---------- Zweite Datei: Demo des Kundenzugangs (läuft ohne Server im Browser) ----------
demo = plain
demo = swap(demo, "<script>document.documentElement.classList.add('js');</script>",
            "<script>window.DEMO_EDIT = location.hash === '#bearbeiten' && (function () { try { return sessionStorage.getItem('erber-demo') === '1'; } catch (e) { return false; } })();"
            " if (!window.DEMO_EDIT) document.documentElement.classList.add('js');</script>")
demo = swap(demo, "<script>\n%s</script>" % js, "<script>\nif (!window.DEMO_EDIT) {\n%s\n}\n</script>" % js)
demo = swap(demo, "</style>", read("admin/editor.css") + "\n/* In der Ansicht keine Bearbeitungsrahmen */\nhtml.js img[data-edit-img] { outline: 0; cursor: auto; filter: none; }\n.draft-note button { margin-left: 12px; min-height: 36px; padding: 0 14px; border: 0; border-radius: 4px; background: #c0452a; color: #fff; font: inherit; font-weight: 700; cursor: pointer; }\n.draft-note button:hover { background: #fff; color: #2b2d2c; }\n</style>", 1)
note = re.search(r'<aside class="draft-note".*?</aside>', demo, re.S).group(0)
demo = swap(demo, note, '<aside class="draft-note" aria-label="Demo-Hinweis">\n  <strong>Demo Kundenzugang.</strong> So ändert der Kunde Texte und Bilder selbst.'
            ' <button type="button" data-demo-login>Bearbeiten</button>\n</aside>')
demo = swap(demo, "</body>", read("demo/demo-ui.html")
            + "<script>\nwindow.__erberEditor = function () {\n%s\n};\n</script>\n<script>\n%s</script>\n</body>" % (read("admin/editor.js"), read("demo/demo.js")))
out2 = root / "dist" / "massivbau-erber-kundenzugang-demo.html"
out2.write_text(demo, encoding="utf-8")
print(out2, "%.0f KB" % (out2.stat().st_size / 1024))
