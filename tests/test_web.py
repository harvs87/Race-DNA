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
            files={"file": ("want_a_winner.sectional.json", fh, "application/json")},
            follow_redirects=False,
        )
    assert r.status_code == 303

    r = client.get("/races/1")
    assert r.status_code == 200
    assert "Want A Winner" in r.text
