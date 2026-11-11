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

out = root / "dist" / "massivbau-erber-entwurf.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding="utf-8")
print(out, "%.0f KB" % (out.stat().st_size / 1024))
