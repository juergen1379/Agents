"""Erzeugt die Beispiel-PDFs in diesem Ordner:  python samples/generate_samples.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from druckcheck.samples import SAMPLES, generate_all  # noqa: E402

if __name__ == "__main__":
    here = Path(__file__).parent
    generate_all(here)
    for s in SAMPLES:
        print(f"{s.file_name:55} {s.product_id:15} {s.description}")
