"""Kommandozeile: python -m druckcheck datei.pdf --produkt flyer_a5 [--json]"""

from __future__ import annotations

import argparse
import json
import sys

from .engine import PdfUnreadableError, run_checks
from .products import load_products

ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴"}


def main(argv: list[str] | None = None) -> int:
    products = load_products()
    parser = argparse.ArgumentParser(prog="druckcheck", description="Druck-PDF technisch prüfen")
    parser.add_argument("pdf", nargs="?")
    parser.add_argument("--produkt", "-p", choices=sorted(products))
    parser.add_argument("--json", action="store_true", help="Ergebnis als JSON ausgeben")
    parser.add_argument("--produkte", action="store_true", help="verfügbare Produkte auflisten")
    args = parser.parse_args(argv)

    if args.produkte or not args.pdf:
        for pid, p in products.items():
            print(f"{pid:20} {p.name}")
        return 0
    if not args.produkt:
        parser.error("--produkt ist erforderlich")

    try:
        report = run_checks(args.pdf, products[args.produkt], strict=False)
    except PdfUnreadableError as exc:
        print(f"PDF nicht lesbar: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0

    print(f"{report.file_name} – {report.product_name} – {report.page_count} Seite(n)")
    print(f"Gesamt: {ICON[report.status.value]} {report.status.value.upper()}\n")
    for check in report.checks:
        print(f"{ICON[check.status.value]} {check.title:22} {check.summary}")
        for f in check.findings:
            if f.status.value != "green" and f.message != check.summary:
                print(f"   {ICON[f.status.value]} {f.message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
