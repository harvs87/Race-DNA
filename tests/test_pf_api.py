from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from racedna.db import connect, init_db
from racedna.import_meeting import import_meeting
from racedna.import_pf_api import import_benchmarks_file, import_sectionals_file
from racedna.pf_api import (
    PfApiError,
    fetch_meeting_benchmarks,
    fetch_meeting_sectionals,
    resolve_api_key,
)
from racedna.scorer import score_meeting, tips_by_race

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
MEETING_CSV = ROOT / "data/inbox/260801_Belmont_Park_5331.csv"


def test_resolve_api_key_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PUNTINGFORM_API_KEY", "test-key-123")
    assert resolve_api_key() == "test-key-123"


def test_resolve_api_key_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("PUNTINGFORM_API_KEY", raising=False)
    monkeypatch.delenv("PF_API_KEY", raising=False)
    monkeypatch.setattr(
        "racedna.pf_api.DEFAULT_KEY_PATHS",
        (tmp_path / "missing_key",),
    )
    with pytest.raises(PfApiError, match="Missing Punting Form API key"):
        resolve_api_key()


def test_fetch_sectionals_uses_official_endpoint(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PUNTINGFORM_API_KEY", "k")
    payload = [{"meetingId": 1, "raceNo": 1, "runnerSectionals": []}]

    class FakeResp:
        status = 200
        headers = type(
            "H",
            (),
            {
                "get_content_charset": lambda self: "utf-8",
                "get_content_type": lambda self: "application/json",
            },
        )()

        def read(self):
            return json.dumps({"statusCode": 200, "payLoad": payload}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_open(req, timeout=60):
        assert "MeetingSectionals" in req.full_url
        assert "meetingId=241810" in req.full_url
        assert "apiKey=k" in req.full_url
        assert "api.puntingform.com.au" in req.full_url
        return FakeResp()

    data = fetch_meeting_sectionals(241810, opener=fake_open)
    assert data[0]["meetingId"] == 1


def test_import_pf_sectionals_and_benchmarks_json(tmp_path: Path):
    db = tmp_path / "pf.db"
    conn = connect(db)
    init_db(conn)
    import_meeting(conn, MEETING_CSV)

    # Ensure meeting external_id from fixture MeetingId can link
    conn.execute(
        "UPDATE meetings SET external_id = ? WHERE track = ? AND meeting_date = ?",
        ("241810", "Belmont Park", "2026-08-01"),
    )
    conn.commit()

    sec = import_sectionals_file(conn, FIXTURES / "241810_sectionals.json")
    assert sec["runners"] == 2
    assert sec["races"] == 1

    bm = import_benchmarks_file(conn, FIXTURES / "241810_benchmarks.json")
    assert bm["horses"] == 2
    assert bm["linked_runners"] >= 1  # Want A Winner should link by name/tab

    row = conn.execute(
        """
        SELECT finish_all, last600_all, horse_name
        FROM pf_benchmarks
        WHERE horse_name = 'Want A Winner'
        """
    ).fetchone()
    assert row is not None
    assert row["finish_all"] == 1.4
    assert row["last600_all"] == 1.1

    tips = score_meeting(
        conn,
        track="Belmont Park",
        meeting_date="2026-08-01",
        going="Soft",
    )
    r1 = tips_by_race(tips, top_n=8)[1]
    want = next(t for t in r1 if t.horse == "Want A Winner")
    joined = " ".join(want.reasons).lower()
    assert "pf" in joined and ("bmark" in joined or "finish" in joined)


def test_import_pf_csv_variants(tmp_path: Path):
    db = tmp_path / "pf_csv.db"
    conn = connect(db)
    init_db(conn)
    import_meeting(conn, MEETING_CSV)
    sec = import_sectionals_file(conn, FIXTURES / "241810_sectionals.csv")
    bm = import_benchmarks_file(conn, FIXTURES / "241810_benchmarks.csv")
    assert sec["runners"] == 2
    assert bm["horses"] == 2


def test_fetch_benchmarks_csv(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PUNTINGFORM_API_KEY", "k")

    class FakeResp:
        status = 200
        headers = type(
            "H",
            (),
            {
                "get_content_charset": lambda self: "utf-8",
                "get_content_type": lambda self: "text/plain",
            },
        )()

        def read(self):
            return b"MeetingId,HorseName\n1,Demo\n"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_open(req, timeout=60):
        assert "MeetingBenchmarks/csv" in req.full_url
        return FakeResp()

    text = fetch_meeting_benchmarks(99, as_csv=True, opener=fake_open)
    assert "HorseName" in text
