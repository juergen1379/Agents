import json

import pytest

from druckcheck import engine
from druckcheck.checks import ALL_CHECKS
from druckcheck.cli import main
from druckcheck.engine import CheckExecutionError, PdfUnreadableError, run_checks
from druckcheck.models import Status
from druckcheck.samples import SAMPLES

from conftest import a5_with_bleed


def test_full_run_and_json(build):
    report = run_checks(build(lambda b: a5_with_bleed(b).text(20, 50, "Hallo")), "flyer_a5")
    assert report.status == Status.GREEN
    assert [c.check_id for c in report.checks] == [c[0] for c in ALL_CHECKS]
    data = json.loads(json.dumps(report.to_dict(), ensure_ascii=False))
    assert data["status"] == "green" and data["product_id"] == "flyer_a5"


def test_unreadable_pdf(tmp_path):
    bad = tmp_path / "kaputt.pdf"
    bad.write_bytes(b"%PDF-1.4 das ist kein pdf")
    with pytest.raises(PdfUnreadableError):
        run_checks(bad, "flyer_a5")


def test_encrypted_pdf(build, tmp_path):
    import pikepdf

    src = build(lambda b: a5_with_bleed(b))
    enc = tmp_path / "enc.pdf"
    with pikepdf.open(src) as pdf:
        pdf.save(enc, encryption=pikepdf.Encryption(user="geheim", owner="geheim"))
    with pytest.raises(PdfUnreadableError, match="passwort"):
        run_checks(enc, "flyer_a5")


def test_crashing_check_raises_in_strict_mode(build, monkeypatch):
    def boom(doc):
        raise RuntimeError("kaputt")

    patched = [(cid, t, boom if cid == "tac" else fn) for cid, t, fn in ALL_CHECKS]
    monkeypatch.setattr(engine, "ALL_CHECKS", patched)
    path = build(lambda b: a5_with_bleed(b))
    with pytest.raises(CheckExecutionError) as exc:
        run_checks(path, "flyer_a5")
    assert "tac" in exc.value.failed
    lenient = run_checks(path, "flyer_a5", strict=False)
    assert "tac" not in [c.check_id for c in lenient.checks]


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s.file_name)
def test_samples_produce_expected_traffic_lights(sample, tmp_path):
    path = sample.build(tmp_path / sample.file_name)
    report = run_checks(path, sample.product_id)
    actual = {c.check_id: c.status.value for c in report.checks}
    expected = {cid: sample.expected.get(cid, "green") for cid, _, _ in ALL_CHECKS}
    assert actual == expected


def test_cli_text_and_json(build, capsys):
    path = build(lambda b: a5_with_bleed(b, bleed=0))
    assert main([str(path), "-p", "flyer_a5"]) == 0
    out = capsys.readouterr().out
    assert "Format & Beschnitt" in out and "keinen Beschnitt" in out
    assert main([str(path), "-p", "flyer_a5", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "red"
