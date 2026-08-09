from __future__ import annotations

from pathlib import Path

from racedna.db import connect, init_db
from racedna.import_meeting import import_meeting
from racedna.import_results import import_results
from racedna.parsers import parse_date, parse_record, parse_sectional
from racedna.scorer import (
    _barrier_score,
    _class_rank,
    backtest_summary,
    score_meeting,
    tips_by_race,
)

ROOT = Path(__file__).resolve().parents[1]
MEETING_CSV = ROOT / "data/inbox/260801_Belmont_Park_5331.csv"
RESULTS_CSV = ROOT / "data/inbox/010826_Belmont_79ae.csv"


def test_parsers():
    assert parse_date("01/08/2026 00:00:00") == "2026-08-01"
    assert parse_date("8/1/2026 12:00:00 AM") == "2026-08-01"
    assert parse_record("33:6-5-6")["wins"] == 6
    assert parse_sectional("34.23sec 600m") == (34.23, 600)
    assert _class_rank("BenchMark 72+") is not None
    assert _class_rank("Maiden") < _class_rank("BenchMark 72+")
    soft_inside, _ = _barrier_score(2, 12, "Soft", 1200)
    soft_wide, _ = _barrier_score(13, 12, "Soft", 1200)
    assert soft_inside > soft_wide


def test_import_and_tip(tmp_path: Path):
    db = tmp_path / "test.db"
    conn = connect(db)
    init_db(conn)

    meeting_stats = import_meeting(conn, MEETING_CSV)
    assert meeting_stats["races"] == 8
    assert meeting_stats["runners"] == 90
    assert meeting_stats["form_runs"] > 500

    results_stats = import_results(conn, RESULTS_CSV)
    assert results_stats["results"] >= 7

    tips = score_meeting(
        conn,
        track="Belmont Park",
        meeting_date="2026-08-01",
        going="Soft",
    )
    by_race = tips_by_race(tips, top_n=3)
    assert set(by_race) == {1, 2, 3, 4, 5, 6, 7, 8}
    assert by_race[1][0].score >= by_race[1][-1].score
    # Tightened scorer should surface going/barrier reasons
    joined = " ".join(by_race[1][0].reasons).lower()
    assert "soft" in joined or "barrier" in joined or "belmont" in joined

    summary = backtest_summary(tips, top_n=1)
    assert summary["bets"] >= 1
