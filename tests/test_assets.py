from __future__ import annotations

from pathlib import Path

from racedna.db import connect, init_db
from racedna.import_assets import import_race_asset, parse_bias_tags
from racedna.import_meeting import import_meeting
from racedna.scorer import score_meeting, tips_by_race

ROOT = Path(__file__).resolve().parents[1]
MEETING_CSV = ROOT / "data/inbox/260801_Belmont_Park_5331.csv"


def test_parse_bias_tags():
    assert "rails" in parse_bias_tags("Rails bias, leaders favoured")
    assert "closers" in parse_bias_tags("closers getting home")
    assert "wide" in parse_bias_tags("wide running on")


def test_add_bias_asset_and_tip(tmp_path: Path):
    db = tmp_path / "assets.db"
    conn = connect(db)
    init_db(conn)
    import_meeting(conn, MEETING_CSV)

    fake = tmp_path / "bias_r1.png"
    fake.write_bytes(b"fake-image")

    stats = import_race_asset(
        conn,
        fake,
        kind="bias",
        note="rails + leaders",
        track="Belmont Park",
        meeting_date="2026-08-01",
        race_number=1,
        copy_into=tmp_path / "assets",
    )
    assert stats["race_id"]
    assert "rails" in stats["tags"]
    assert "leaders" in stats["tags"]

    tips = score_meeting(
        conn,
        track="Belmont Park",
        meeting_date="2026-08-01",
        going="Soft",
    )
    r1 = tips_by_race(tips, top_n=8)[1]
    joined = " ".join(" ".join(t.reasons) for t in r1).lower()
    assert "bias" in joined
