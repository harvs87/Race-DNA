from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ASSET_KINDS = {"bias", "sectionals", "form", "notes", "other"}

# Simple keyword tags pulled from free-text notes / filenames.
BIAS_PATTERNS: list[tuple[str, str]] = [
    (r"\brails?\b", "rails"),
    (r"\btrue\b", "true"),
    (r"\bwide\b", "wide"),
    (r"\bleaders?\b", "leaders"),
    (r"\bon[- ]?pace\b", "on_pace"),
    (r"\bclosers?\b", "closers"),
    (r"\bspeed\b", "speed"),
    (r"\bwet\b|\bsoft\b|\bheavy\b", "wet"),
    (r"\binside\b", "inside"),
    (r"\boutside\b", "outside"),
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_bias_tags(text: str | None) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for pattern, tag in BIAS_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            if tag not in found:
                found.append(tag)
    return found


def _resolve_race_id(
    conn: sqlite3.Connection,
    *,
    race_id: int | None = None,
    track: str | None = None,
    meeting_date: str | None = None,
    race_number: int | None = None,
) -> int:
    if race_id is not None:
        row = conn.execute("SELECT id FROM races WHERE id = ?", (race_id,)).fetchone()
        if not row:
            raise ValueError(f"Race id {race_id} not found")
        return int(row["id"])

    if not (track and meeting_date and race_number is not None):
        raise ValueError("Provide --race-id, or --track + --date + --race")

    meeting = conn.execute(
        "SELECT id FROM meetings WHERE track = ? AND meeting_date = ?",
        (track, meeting_date),
    ).fetchone()
    if not meeting:
        # soft match on track contains
        meeting = conn.execute(
            """
            SELECT id, track FROM meetings
            WHERE meeting_date = ? AND lower(track) LIKE ?
            ORDER BY id DESC LIMIT 1
            """,
            (meeting_date, f"%{track.lower()}%"),
        ).fetchone()
    if not meeting:
        raise ValueError(f"No meeting for {track!r} on {meeting_date}")

    race = conn.execute(
        "SELECT id FROM races WHERE meeting_id = ? AND race_number = ?",
        (meeting["id"], race_number),
    ).fetchone()
    if not race:
        raise ValueError(f"No race {race_number} on that meeting")
    return int(race["id"])


def import_race_asset(
    conn: sqlite3.Connection,
    path: str | Path | None = None,
    *,
    kind: str = "bias",
    note: str | None = None,
    race_id: int | None = None,
    track: str | None = None,
    meeting_date: str | None = None,
    race_number: int | None = None,
    copy_into: str | Path | None = "data/inbox/assets",
) -> dict:
    kind = (kind or "other").lower().strip()
    if kind not in ASSET_KINDS:
        raise ValueError(f"kind must be one of {sorted(ASSET_KINDS)}")
    if path is None and not note:
        raise ValueError("Provide a screenshot path and/or --note")

    resolved_race_id = _resolve_race_id(
        conn,
        race_id=race_id,
        track=track,
        meeting_date=meeting_date,
        race_number=race_number,
    )

    stored_path: str | None = None
    if path is not None:
        src = Path(path)
        if not src.exists():
            raise FileNotFoundError(src)
        if copy_into:
            dest_dir = Path(copy_into)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"race{resolved_race_id}_{kind}_{src.name}"
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            stored_path = str(dest)
        else:
            stored_path = str(src)

    blob = " ".join(x for x in (note, Path(path).stem if path else None) if x)
    tags = parse_bias_tags(blob)
    tags_csv = ",".join(tags) if tags else None

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO race_assets (race_id, kind, source_path, note, tags, imported_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (resolved_race_id, kind, stored_path, note, tags_csv, _now()),
    )
    conn.commit()
    return {
        "asset_id": cur.lastrowid,
        "race_id": resolved_race_id,
        "kind": kind,
        "source_path": stored_path,
        "note": note,
        "tags": tags,
    }


def list_race_assets(conn: sqlite3.Connection, race_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM race_assets
        WHERE race_id = ?
        ORDER BY id
        """,
        (race_id,),
    ).fetchall()


def bias_summary_for_race(conn: sqlite3.Connection, race_id: int) -> dict[str, object]:
    rows = list_race_assets(conn, race_id)
    tags: list[str] = []
    notes: list[str] = []
    for row in rows:
        if row["kind"] not in {"bias", "notes", "other"}:
            continue
        if row["note"]:
            notes.append(row["note"])
        if row["tags"]:
            for tag in str(row["tags"]).split(","):
                tag = tag.strip()
                if tag and tag not in tags:
                    tags.append(tag)
    return {"tags": tags, "notes": notes, "asset_count": len(rows)}
