from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from racedna.db import connect, init_db
from racedna.import_meeting import import_meeting
from racedna.web import create_app

ROOT = Path(__file__).resolve().parents[1]
MEETING_CSV = ROOT / "data/inbox/260801_Belmont_Park_5331.csv"
RESULTS_CSV = ROOT / "data/inbox/010826_Belmont_79ae.csv"
SECTIONAL_JSON = ROOT / "data/inbox/sectionals/want_a_winner.sectional.json"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "web.db"
    monkeypatch.setenv("RACEDNA_DB", str(db))
    monkeypatch.chdir(tmp_path)
    app = create_app()
    return TestClient(app)


def test_home_and_upload_meeting(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "RaceDNA" in r.text
    assert "v0.5.1" in r.text

    r = client.get("/health")
    assert r.json()["version"] == "0.5.1"

    with MEETING_CSV.open("rb") as fh:
        r = client.post(
            "/upload/meeting",
            files={"file": ("meeting.csv", fh, "text/csv")},
            follow_redirects=False,
        )
    assert r.status_code == 303

    r = client.get("/")
    assert "Belmont Park" in r.text


def test_meeting_tips_and_race_asset(client: TestClient):
    db = Path(os.environ["RACEDNA_DB"])
    conn = connect(db)
    init_db(conn)
    import_meeting(conn, MEETING_CSV)

    r = client.get("/meetings/1")
    assert r.status_code == 200
    assert "Tips" in r.text

    r = client.get("/races/1")
    assert r.status_code == 200
    assert "Attach for this race" in r.text

    r = client.post(
        "/races/1/assets",
        data={"kind": "bias", "note": "rails + leaders"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    r = client.get("/races/1")
    assert "rails" in r.text
    assert "bias" in r.text.lower()


def test_upload_results_and_sectionals(client: TestClient):
    with MEETING_CSV.open("rb") as fh:
        client.post("/upload/meeting", files={"file": ("meeting.csv", fh, "text/csv")})
    with RESULTS_CSV.open("rb") as fh:
        r = client.post(
            "/upload/results",
            files={"file": ("results.csv", fh, "text/csv")},
            follow_redirects=False,
        )
    assert r.status_code == 303

    with SECTIONAL_JSON.open("rb") as fh:
        r = client.post(
            "/races/1/sectionals",
            data={
                "horse_name": "Want A Winner",
                "run_style": "Leader (Settle - 2)",
                "settle": "2",
            },
            files={"file": ("want_a_winner.sectional.json", fh, "application/json")},
            follow_redirects=False,
        )
    assert r.status_code == 303

    r = client.get("/races/1")
    assert r.status_code == 200
    assert "Want A Winner" in r.text


def test_screenshot_only_sectionals_without_ocr(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from racedna.ocr import OcrUnavailable
    import racedna.import_sectionals as sec_mod

    def _boom(_path):
        raise OcrUnavailable("no tesseract in test")

    monkeypatch.setattr(sec_mod, "ocr_image", _boom)

    with MEETING_CSV.open("rb") as fh:
        client.post("/upload/meeting", files={"file": ("meeting.csv", fh, "text/csv")})

    png = b"\x89PNG\r\n\x1a\n" + b"fake"
    r = client.post(
        "/races/1/sectionals",
        data={
            "horse_name": "Want A Winner",
            "run_style": "Leader (Settle - 2)",
            "settle": "2",
        },
        files={"file": ("want.png", png, "image/png")},
        follow_redirects=False,
    )
    assert r.status_code == 303

    r = client.get("/races/1")
    assert r.status_code == 200
    assert "Want A Winner" in r.text
    # horse style should be applied even without OCR rows
    from racedna.db import connect

    conn = connect(os.environ["RACEDNA_DB"])
    horse = conn.execute(
        "SELECT run_style, settle FROM horses WHERE lower(name)=lower(?)",
        ("Want A Winner",),
    ).fetchone()
    assert horse is not None
    assert horse["settle"] == 2
    assert "Leader" in (horse["run_style"] or "")
