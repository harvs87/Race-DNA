from __future__ import annotations

from pathlib import Path

from racedna.db import connect, init_db
from racedna.import_meeting import import_meeting
from racedna.import_sectionals import import_sectional
from racedna.ocr import ocr_image
from racedna.scorer import score_meeting, tips_by_race
from racedna.sectional_parse import parse_sectional_text

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
SECTIONALS = ROOT / "data/inbox/sectionals"
MEETING_CSV = ROOT / "data/inbox/260801_Belmont_Park_5331.csv"


def test_parse_pipe_sectional_text():
    text = (SECTIONALS / "ellismayne.sectional.txt").read_text(encoding="utf-8")
    page = parse_sectional_text(text)
    assert page.horse_name == "Ellismayne"
    assert page.settle == 8
    assert len(page.rows) >= 3
    assert page.rows[0].l6 == 35.0
    assert page.rows[0].split_2_f == 3


def test_import_sectional_json_and_score(tmp_path: Path):
    db = tmp_path / "sec.db"
    conn = connect(db)
    init_db(conn)
    import_meeting(conn, MEETING_CSV)

    stats = import_sectional(conn, SECTIONALS / "want_a_winner.sectional.json")
    assert stats["horse_name"] == "Want A Winner"
    assert stats["rows"] == 3
    assert stats["horse_id"] is not None

    horse = conn.execute(
        "SELECT run_style, settle FROM horses WHERE id = ?",
        (stats["horse_id"],),
    ).fetchone()
    assert horse["settle"] == 2
    assert "Leader" in (horse["run_style"] or "")

    tips = score_meeting(
        conn,
        track="Belmont Park",
        meeting_date="2026-08-01",
        going="Soft",
    )
    r1 = tips_by_race(tips, top_n=5)[1]
    want = next(t for t in r1 if t.horse == "Want A Winner")
    joined = " ".join(want.reasons).lower()
    assert "run style" in joined or "sectional" in joined or "l6" in joined or "forward" in joined


def test_ocr_image_roundtrip():
    import pytest

    try:
        from pytesseract import TesseractNotFoundError
    except ImportError:  # pragma: no cover
        pytest.skip("pytesseract not installed")

    png = FIXTURES / "demo_closer_sectionals.png"
    try:
        text = ocr_image(png)
    except TesseractNotFoundError:
        pytest.skip("system tesseract not installed")
    # OCR should at least recover horse marker / settle-ish content
    assert "DEMO" in text.upper() or "CLOSER" in text.upper() or "SETTLE" in text.upper()
    page = parse_sectional_text(text)
    # Allow OCR noise but expect at least one dated row or header horse
    assert page.horse_name is not None or len(page.rows) >= 1
