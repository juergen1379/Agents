"""Einstiegspunkt der technischen Prüfung."""

from __future__ import annotations

import logging
from pathlib import Path

from . import __version__
from .checks import ALL_CHECKS
from .document import PdfUnreadableError, load_document
from .models import CheckResult, Report, Status
from .products import Product, get_product

log = logging.getLogger(__name__)


class CheckExecutionError(RuntimeError):
    """Mindestens eine Prüfung ist technisch fehlgeschlagen. Der Job soll dann
    automatisch erstatten statt einen unvollständigen Bericht zu verschicken."""

    def __init__(self, failed: dict[str, str], partial: Report | None = None):
        super().__init__("Prüfung fehlgeschlagen: " + ", ".join(f"{k}: {v}" for k, v in failed.items()))
        self.failed = failed
        self.partial = partial


def run_checks(pdf_path: str | Path, product: Product | str, *, strict: bool = True) -> Report:
    """Führt alle technischen Prüfungen aus.

    strict=True: wirft CheckExecutionError, falls eine Prüfung abstürzt (Produktivbetrieb).
    strict=False: überspringt die abgestürzte Prüfung (z. B. für die Kommandozeile).
    PdfUnreadableError wird immer durchgereicht – das ist ein Kundenproblem, kein Systemfehler.
    """
    if isinstance(product, str):
        product = get_product(product)
    doc = load_document(pdf_path, product)
    results: list[CheckResult] = []
    failed: dict[str, str] = {}
    try:
        for check_id, _title, fn in ALL_CHECKS:
            try:
                results.append(fn(doc))
            except Exception as exc:  # noqa: BLE001 – jede Prüfung isoliert
                log.exception("Prüfung %s fehlgeschlagen", check_id)
                failed[check_id] = f"{type(exc).__name__}: {exc}"
        report = Report(
            file_name=Path(pdf_path).name,
            product_id=product.id,
            product_name=product.name,
            page_count=doc.page_count,
            status=Status.worst(r.status for r in results),
            checks=results,
            engine_version=__version__,
        )
    finally:
        doc.close()
    if failed and strict:
        raise CheckExecutionError(failed, report)
    return report


__all__ = ["run_checks", "CheckExecutionError", "PdfUnreadableError"]
