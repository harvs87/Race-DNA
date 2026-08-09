"""Import Punting Form Meeting Sectionals + Benchmarks (official API JSON/CSV)."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from racedna.parsers import clean, parse_date, parse_float, parse_int


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _get(obj: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]
        # case-insensitive fallback
        low = key.lower()
        for existing, value in obj.items():
            if str(existing).lower() == low and value is not None:
                return value
    return None


def _as_list(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("payLoad", "payload", "races", "items", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
        # single race object
        if _get(payload, "raceId", "raceNumber", "raceNo") is not None:
            return [payload]
    raise ValueError(f"Unexpected PF payload type: {type(payload)!r}")


def _find_meeting(
    conn: sqlite3.Connection,
    *,
    external_id: str | int | None,
    track: str | None,
    meeting_date: str | None,
) -> int | None:
    if external_id is not None:
        row = conn.execute(
            "SELECT id FROM meetings WHERE external_id = ? LIMIT 1",
            (str(external_id),),
        ).fetchone()
        if row:
            return row["id"]
    if track and meeting_date:
        row = conn.execute(
            """
            SELECT id FROM meetings
            WHERE lower(track) = lower(?) AND meeting_date = ?
            LIMIT 1
            """,
            (track, meeting_date[:10]),
        ).fetchone()
        if row:
            return row["id"]
    return None


def _ensure_meeting(
    conn: sqlite3.Connection,
    *,
    external_id: str | int | None,
    track: str | None,
    meeting_date: str | None,
) -> int | None:
    meeting_id = _find_meeting(
        conn, external_id=external_id, track=track, meeting_date=meeting_date
    )
    if meeting_id is not None:
        if external_id is not None:
            conn.execute(
                """
                UPDATE meetings SET external_id = COALESCE(external_id, ?)
                WHERE id = ?
                """,
                (str(external_id), meeting_id),
            )
        return meeting_id
    if not track or not meeting_date:
        return None
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO meetings (external_id, track, meeting_date)
        VALUES (?, ?, ?)
        ON CONFLICT(track, meeting_date) DO UPDATE SET
            external_id = COALESCE(excluded.external_id, meetings.external_id)
        """,
        (str(external_id) if external_id is not None else None, track, meeting_date[:10]),
    )
    return cur.execute(
        "SELECT id FROM meetings WHERE track = ? AND meeting_date = ?",
        (track, meeting_date[:10]),
    ).fetchone()["id"]


def _find_race(
    conn: sqlite3.Connection,
    meeting_id: int | None,
    *,
    race_number: int | None,
    external_race_id: str | int | None,
) -> int | None:
    if meeting_id is None:
        return None
    if external_race_id is not None:
        row = conn.execute(
            """
            SELECT id FROM races
            WHERE meeting_id = ? AND external_id = ?
            LIMIT 1
            """,
            (meeting_id, str(external_race_id)),
        ).fetchone()
        if row:
            return row["id"]
    if race_number is not None:
        row = conn.execute(
            """
            SELECT id FROM races
            WHERE meeting_id = ? AND race_number = ?
            LIMIT 1
            """,
            (meeting_id, race_number),
        ).fetchone()
        if row:
            return row["id"]
    return None


def _ensure_race(
    conn: sqlite3.Connection,
    meeting_id: int | None,
    *,
    race_number: int | None,
    external_race_id: str | int | None,
    distance: int | None = None,
) -> int | None:
    race_id = _find_race(
        conn, meeting_id, race_number=race_number, external_race_id=external_race_id
    )
    if race_id is not None or meeting_id is None or race_number is None:
        if race_id is not None and external_race_id is not None:
            conn.execute(
                """
                UPDATE races SET external_id = COALESCE(external_id, ?)
                WHERE id = ?
                """,
                (str(external_race_id), race_id),
            )
        return race_id
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO races (meeting_id, external_id, race_number, distance)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(meeting_id, race_number) DO UPDATE SET
            external_id = COALESCE(excluded.external_id, races.external_id),
            distance = COALESCE(excluded.distance, races.distance)
        """,
        (
            meeting_id,
            str(external_race_id) if external_race_id is not None else None,
            race_number,
            distance,
        ),
    )
    return cur.execute(
        "SELECT id FROM races WHERE meeting_id = ? AND race_number = ?",
        (meeting_id, race_number),
    ).fetchone()["id"]


def _find_runner(
    conn: sqlite3.Connection,
    race_id: int | None,
    *,
    tab_no: int | None,
    horse_name: str | None,
    horse_external_id: str | int | None = None,
) -> tuple[int | None, int | None]:
    """Return (runner_id, horse_id)."""
    if race_id is None:
        return None, None
    if tab_no is not None:
        row = conn.execute(
            """
            SELECT runners.id AS runner_id, runners.horse_id AS horse_id
            FROM runners
            WHERE race_id = ? AND tab_no = ?
            LIMIT 1
            """,
            (race_id, tab_no),
        ).fetchone()
        if row:
            return row["runner_id"], row["horse_id"]
    if horse_name:
        row = conn.execute(
            """
            SELECT runners.id AS runner_id, runners.horse_id AS horse_id
            FROM runners
            JOIN horses ON horses.id = runners.horse_id
            WHERE runners.race_id = ? AND lower(horses.name) = lower(?)
            LIMIT 1
            """,
            (race_id, horse_name),
        ).fetchone()
        if row:
            return row["runner_id"], row["horse_id"]
    if horse_external_id is not None:
        row = conn.execute(
            """
            SELECT runners.id AS runner_id, runners.horse_id AS horse_id
            FROM runners
            JOIN horses ON horses.id = runners.horse_id
            WHERE runners.race_id = ? AND horses.external_id = ?
            LIMIT 1
            """,
            (race_id, str(horse_external_id)),
        ).fetchone()
        if row:
            return row["runner_id"], row["horse_id"]
    return None, None


def _ensure_horse(
    conn: sqlite3.Connection,
    *,
    name: str | None,
    external_id: str | int | None,
) -> int | None:
    if not name and external_id is None:
        return None
    if external_id is not None:
        row = conn.execute(
            "SELECT id FROM horses WHERE external_id = ?",
            (str(external_id),),
        ).fetchone()
        if row:
            if name:
                conn.execute(
                    "UPDATE horses SET name = COALESCE(name, ?) WHERE id = ?",
                    (name, row["id"]),
                )
            return row["id"]
    if name:
        row = conn.execute(
            "SELECT id FROM horses WHERE lower(name) = lower(?) ORDER BY id LIMIT 1",
            (name,),
        ).fetchone()
        if row:
            if external_id is not None:
                conn.execute(
                    """
                    UPDATE horses SET external_id = COALESCE(external_id, ?)
                    WHERE id = ?
                    """,
                    (str(external_id), row["id"]),
                )
            return row["id"]
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO horses (external_id, name) VALUES (?, ?)",
            (str(external_id) if external_id is not None else None, name),
        )
        return cur.lastrowid
    return None


def load_json_payload(path: str | Path) -> Any:
    text = Path(path).read_text(encoding="utf-8-sig")
    data = json.loads(text)
    if isinstance(data, dict):
        for key in ("payLoad", "payload", "Payload"):
            if key in data:
                return data[key]
    return data


def load_csv_rows(path: str | Path | None = None, text: str | None = None) -> list[dict[str, str]]:
    if path is not None:
        text = Path(path).read_text(encoding="utf-8-sig")
    if text is None:
        return []
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, str]] = []
    for raw in reader:
        row = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
        if any(row.values()):
            rows.append(row)
    return rows


def import_sectionals_payload(
    conn: sqlite3.Connection,
    payload: Any,
    *,
    source: str,
) -> dict[str, int]:
    races = _as_list(payload)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO pf_api_imports (kind, source_path, external_meeting_id, imported_at)
        VALUES ('sectionals', ?, NULL, ?)
        """,
        (source, _now()),
    )
    import_id = cur.lastrowid
    runners_n = 0
    races_n = 0
    linked_n = 0
    meeting_ext: str | None = None

    for race in races:
        if not isinstance(race, dict):
            continue
        races_n += 1
        meeting_ext = clean(str(_get(race, "meetingId") or meeting_ext or ""))
        track = clean(_get(race, "track"))
        meeting_date = parse_date(_get(race, "meetingDate", "meetingDateUTC"))
        race_no = parse_int(_get(race, "raceNo", "raceNumber"))
        race_ext = _get(race, "raceId")
        distance = parse_int(_get(race, "distance"))
        meeting_id = _ensure_meeting(
            conn,
            external_id=meeting_ext,
            track=track,
            meeting_date=meeting_date,
        )
        race_id = _ensure_race(
            conn,
            meeting_id,
            race_number=race_no,
            external_race_id=race_ext,
            distance=distance,
        )
        # Update race meta when present
        if race_id is not None:
            cur.execute(
                """
                UPDATE races SET
                    distance = COALESCE(?, distance),
                    official_time = COALESCE(?, official_time),
                    official_sectional = COALESCE(?, official_sectional),
                    sectional_distance = COALESCE(?, sectional_distance)
                WHERE id = ?
                """,
                (
                    distance,
                    clean(str(_get(race, "officialTime"))) if _get(race, "officialTime") is not None else None,
                    parse_float(_get(race, "officialSectionalTime")),
                    parse_int(_get(race, "officialSectionalDistance")),
                    race_id,
                ),
            )

        runner_items = _get(race, "runnerSectionals", "runners", "items") or []
        if not isinstance(runner_items, list):
            runner_items = []
        for item in runner_items:
            if not isinstance(item, dict):
                continue
            tab_no = parse_int(_get(item, "tabNumber", "tabNo"))
            horse_name = clean(_get(item, "runnerName", "horseName"))
            horse_ext = _get(item, "runnerId", "horseId")
            runner_id, horse_id = _find_runner(
                conn,
                race_id,
                tab_no=tab_no,
                horse_name=horse_name,
                horse_external_id=horse_ext,
            )
            if horse_id is None:
                horse_id = _ensure_horse(conn, name=horse_name, external_id=horse_ext)
            if runner_id is not None:
                linked_n += 1
            cur.execute(
                """
                INSERT INTO pf_sectionals (
                    import_id, meeting_id, race_id, runner_id, horse_id,
                    external_meeting_id, external_race_id, race_number, tab_no,
                    horse_name, form_date, track, distance,
                    time_to_fin, last1200, last1000, last800, last600, last400, last200, last100,
                    split_12_10, split_10_8, split_8_6, split_6_4, split_4_2, split_2_1,
                    pos_600, pos_400, pos_200, pos_fin, marg_fin,
                    meeting_rank_6f, meeting_rank_4f, meeting_rank_2f,
                    early_200_avg, raw_json
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?
                )
                """,
                (
                    import_id,
                    meeting_id,
                    race_id,
                    runner_id,
                    horse_id,
                    meeting_ext,
                    str(race_ext) if race_ext is not None else None,
                    race_no,
                    tab_no,
                    horse_name,
                    meeting_date,
                    track,
                    distance,
                    parse_float(_get(item, "timeToFin")),
                    parse_float(_get(item, "last1200Time")),
                    parse_float(_get(item, "last1000Time")),
                    parse_float(_get(item, "last800Time")),
                    parse_float(_get(item, "last600Time")),
                    parse_float(_get(item, "last400Time")),
                    parse_float(_get(item, "last200Time")),
                    parse_float(_get(item, "last100Time")),
                    parse_float(_get(item, "split1210")),
                    parse_float(_get(item, "split108")),
                    parse_float(_get(item, "split86")),
                    parse_float(_get(item, "split64")),
                    parse_float(_get(item, "split42")),
                    parse_float(_get(item, "split21")),
                    parse_int(_get(item, "pos600")),
                    parse_int(_get(item, "pos400")),
                    parse_int(_get(item, "pos200")),
                    parse_int(_get(item, "posFin")),
                    parse_float(_get(item, "margFin")),
                    parse_int(_get(item, "meetingRank6F")),
                    parse_int(_get(item, "meetingRank4F")),
                    parse_int(_get(item, "meetingRank2F")),
                    parse_float(_get(item, "early200Average")),
                    json.dumps(item),
                ),
            )
            runners_n += 1
            # Enrich form_runs sectional_time when we can match horse+date+track
            if horse_id is not None and meeting_date and parse_float(_get(item, "last600Time")):
                cur.execute(
                    """
                    UPDATE form_runs
                    SET sectional_time = COALESCE(sectional_time, ?),
                        sectional_distance = COALESCE(sectional_distance, 600)
                    WHERE id IN (
                        SELECT form_runs.id
                        FROM form_runs
                        JOIN runners ON runners.id = form_runs.runner_id
                        WHERE runners.horse_id = ?
                          AND form_runs.form_date = ?
                          AND (? IS NULL OR form_runs.track IS NULL
                               OR lower(form_runs.track) LIKE '%' || lower(substr(?, 1, 6)) || '%')
                        ORDER BY form_runs.id DESC
                        LIMIT 1
                    )
                    AND (sectional_time IS NULL OR sectional_time = 0)
                    """,
                    (
                        parse_float(_get(item, "last600Time")),
                        horse_id,
                        meeting_date[:10],
                        track,
                        track or "",
                    ),
                )

    if meeting_ext:
        cur.execute(
            "UPDATE pf_api_imports SET external_meeting_id = ? WHERE id = ?",
            (meeting_ext, import_id),
        )
    conn.commit()
    return {
        "import_id": import_id,
        "races": races_n,
        "runners": runners_n,
        "linked_runners": linked_n,
        "external_meeting_id": int(meeting_ext) if meeting_ext and meeting_ext.isdigit() else 0,
    }


def import_sectionals_csv_rows(
    conn: sqlite3.Connection,
    rows: Iterable[dict[str, str]],
    *,
    source: str,
) -> dict[str, int]:
    """Flattened CSV import — one row per runner."""
    # Group by race
    by_race: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        meeting_id = parse_int(_get(row, "MeetingId", "meetingId", "meeting id"))
        race_id = parse_int(_get(row, "RaceId", "raceId", "race id"))
        race_no = parse_int(_get(row, "RaceNo", "RaceNumber", "raceNo", "raceNumber", "race number"))
        key = (meeting_id, race_id, race_no)
        if key not in by_race:
            by_race[key] = {
                "meetingId": meeting_id,
                "track": _get(row, "Track", "track"),
                "meetingDate": _get(row, "MeetingDate", "meetingDate", "meeting date"),
                "raceId": race_id,
                "raceNo": race_no,
                "distance": parse_int(_get(row, "Distance", "distance")),
                "officialTime": _get(row, "OfficialTime", "officialTime"),
                "officialSectionalTime": _get(row, "OfficialSectionalTime", "officialSectionalTime"),
                "officialSectionalDistance": _get(
                    row, "OfficialSectionalDistance", "officialSectionalDistance"
                ),
                "runnerSectionals": [],
            }
        # Detect whether this row is a runner row
        tab = parse_int(_get(row, "TabNumber", "TabNo", "tabNumber", "tabNo", "horse number"))
        name = clean(_get(row, "RunnerName", "HorseName", "runnerName", "horseName", "horse name"))
        if tab is None and not name:
            continue
        runner = {
            "tabNumber": tab,
            "runnerName": name,
            "runnerId": parse_int(_get(row, "RunnerId", "runnerId", "HorseId", "horseId")),
            "timeToFin": _get(row, "TimeToFin", "timeToFin"),
            "last1200Time": _get(row, "Last1200Time", "last1200Time", "L1200"),
            "last1000Time": _get(row, "Last1000Time", "last1000Time", "L1000"),
            "last800Time": _get(row, "Last800Time", "last800Time", "L800"),
            "last600Time": _get(row, "Last600Time", "last600Time", "L600"),
            "last400Time": _get(row, "Last400Time", "last400Time", "L400"),
            "last200Time": _get(row, "Last200Time", "last200Time", "L200"),
            "last100Time": _get(row, "Last100Time", "last100Time", "L100"),
            "split1210": _get(row, "Split1210", "split1210"),
            "split108": _get(row, "Split108", "split108"),
            "split86": _get(row, "Split86", "split86"),
            "split64": _get(row, "Split64", "split64"),
            "split42": _get(row, "Split42", "split42"),
            "split21": _get(row, "Split21", "split21"),
            "pos600": _get(row, "Pos600", "pos600"),
            "pos400": _get(row, "Pos400", "pos400"),
            "pos200": _get(row, "Pos200", "pos200"),
            "posFin": _get(row, "PosFin", "posFin", "FinishPos"),
            "margFin": _get(row, "MargFin", "margFin", "Margin"),
            "meetingRank6F": _get(row, "MeetingRank6F", "meetingRank6F"),
            "meetingRank4F": _get(row, "MeetingRank4F", "meetingRank4F"),
            "meetingRank2F": _get(row, "MeetingRank2F", "meetingRank2F"),
            "early200Average": _get(row, "Early200Average", "early200Average"),
        }
        by_race[key]["runnerSectionals"].append(runner)
    return import_sectionals_payload(conn, list(by_race.values()), source=source)


def import_benchmarks_payload(
    conn: sqlite3.Connection,
    payload: Any,
    *,
    source: str,
) -> dict[str, int]:
    races = _as_list(payload)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO pf_api_imports (kind, source_path, external_meeting_id, imported_at)
        VALUES ('benchmarks', ?, NULL, ?)
        """,
        (source, _now()),
    )
    import_id = cur.lastrowid
    races_n = 0
    horses_n = 0
    linked_n = 0
    meeting_ext: str | None = None

    for race in races:
        if not isinstance(race, dict):
            continue
        races_n += 1
        meeting_ext = clean(str(_get(race, "meetingId") or meeting_ext or ""))
        track = clean(_get(race, "track"))
        meeting_date = parse_date(_get(race, "meetingDate"))
        race_no = parse_int(_get(race, "raceNumber", "raceNo"))
        race_ext = _get(race, "raceId")
        meeting_id = _ensure_meeting(
            conn,
            external_id=meeting_ext,
            track=track,
            meeting_date=meeting_date,
        )
        race_id = _ensure_race(
            conn,
            meeting_id,
            race_number=race_no,
            external_race_id=race_ext,
        )
        items = _get(race, "items", "runners", "benchmarks") or []
        if not isinstance(items, list):
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            tab_no = parse_int(_get(item, "tabNo", "tabNumber"))
            horse_name = clean(_get(item, "horseName", "runnerName"))
            horse_ext = _get(item, "horseId", "runnerId")
            runner_id, horse_id = _find_runner(
                conn,
                race_id,
                tab_no=tab_no,
                horse_name=horse_name,
                horse_external_id=horse_ext,
            )
            if horse_id is None:
                horse_id = _ensure_horse(conn, name=horse_name, external_id=horse_ext)
            if runner_id is not None:
                linked_n += 1
            # Upsert on race+tab or race+horse
            existing = None
            if race_id is not None and tab_no is not None:
                existing = cur.execute(
                    """
                    SELECT id FROM pf_benchmarks
                    WHERE race_id = ? AND tab_no = ?
                    LIMIT 1
                    """,
                    (race_id, tab_no),
                ).fetchone()
            values = (
                import_id,
                meeting_id,
                race_id,
                runner_id,
                horse_id,
                meeting_ext,
                str(race_ext) if race_ext is not None else None,
                race_no,
                tab_no,
                horse_name,
                str(horse_ext) if horse_ext is not None else None,
                parse_float(_get(item, "to600All")),
                parse_float(_get(item, "last600All")),
                parse_float(_get(item, "finishAll")),
                parse_float(_get(item, "to600Class")),
                parse_float(_get(item, "last600Class")),
                parse_float(_get(item, "finishClass")),
                parse_float(_get(item, "last400All")),
                parse_float(_get(item, "last200All")),
                parse_float(_get(item, "last100All")),
                parse_float(_get(item, "split64All")),
                parse_float(_get(item, "split42All")),
                parse_float(_get(item, "split21All")),
                parse_float(_get(item, "last400Class")),
                parse_float(_get(item, "last200Class")),
                parse_float(_get(item, "last100Class")),
                parse_float(_get(item, "split64Class")),
                parse_float(_get(item, "split42Class")),
                parse_float(_get(item, "split21Class")),
                json.dumps(item),
            )
            if existing:
                cur.execute(
                    """
                    UPDATE pf_benchmarks SET
                        import_id=?, meeting_id=?, race_id=?, runner_id=?, horse_id=?,
                        external_meeting_id=?, external_race_id=?, race_number=?, tab_no=?,
                        horse_name=?, external_horse_id=?,
                        to600_all=?, last600_all=?, finish_all=?,
                        to600_class=?, last600_class=?, finish_class=?,
                        last400_all=?, last200_all=?, last100_all=?,
                        split64_all=?, split42_all=?, split21_all=?,
                        last400_class=?, last200_class=?, last100_class=?,
                        split64_class=?, split42_class=?, split21_class=?,
                        raw_json=?
                    WHERE id=?
                    """,
                    values + (existing["id"],),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO pf_benchmarks (
                        import_id, meeting_id, race_id, runner_id, horse_id,
                        external_meeting_id, external_race_id, race_number, tab_no,
                        horse_name, external_horse_id,
                        to600_all, last600_all, finish_all,
                        to600_class, last600_class, finish_class,
                        last400_all, last200_all, last100_all,
                        split64_all, split42_all, split21_all,
                        last400_class, last200_class, last100_class,
                        split64_class, split42_class, split21_class,
                        raw_json
                    ) VALUES (
                        ?,?,?,?,?,
                        ?,?,?,?,
                        ?,?,
                        ?,?,?,
                        ?,?,?,
                        ?,?,?,
                        ?,?,?,
                        ?,?,?,
                        ?,?,?,
                        ?
                    )
                    """,
                    values,
                )
            horses_n += 1

    if meeting_ext:
        cur.execute(
            "UPDATE pf_api_imports SET external_meeting_id = ? WHERE id = ?",
            (meeting_ext, import_id),
        )
    conn.commit()
    return {
        "import_id": import_id,
        "races": races_n,
        "horses": horses_n,
        "linked_runners": linked_n,
        "external_meeting_id": int(meeting_ext) if meeting_ext and meeting_ext.isdigit() else 0,
    }


def import_benchmarks_csv_rows(
    conn: sqlite3.Connection,
    rows: Iterable[dict[str, str]],
    *,
    source: str,
) -> dict[str, int]:
    by_race: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        meeting_id = parse_int(_get(row, "MeetingId", "meetingId"))
        race_id = parse_int(_get(row, "RaceId", "raceId"))
        race_no = parse_int(_get(row, "RaceNumber", "RaceNo", "raceNumber", "raceNo"))
        key = (meeting_id, race_id, race_no)
        if key not in by_race:
            by_race[key] = {
                "meetingId": meeting_id,
                "track": _get(row, "Track", "track"),
                "meetingDate": _get(row, "MeetingDate", "meetingDate"),
                "raceId": race_id,
                "raceNumber": race_no,
                "items": [],
            }
        tab = parse_int(_get(row, "TabNo", "TabNumber", "tabNo", "tabNumber"))
        name = clean(_get(row, "HorseName", "RunnerName", "horseName", "runnerName"))
        if tab is None and not name:
            continue
        by_race[key]["items"].append(
            {
                "horseId": parse_int(_get(row, "HorseId", "horseId", "RunnerId")),
                "horseName": name,
                "tabNo": tab,
                "to600All": _get(row, "To600All", "to600All"),
                "last600All": _get(row, "Last600All", "last600All"),
                "finishAll": _get(row, "FinishAll", "finishAll"),
                "to600Class": _get(row, "To600Class", "to600Class"),
                "last600Class": _get(row, "Last600Class", "last600Class"),
                "finishClass": _get(row, "FinishClass", "finishClass"),
                "last400All": _get(row, "Last400All", "last400All"),
                "last200All": _get(row, "Last200All", "last200All"),
                "last100All": _get(row, "Last100All", "last100All"),
                "split64All": _get(row, "Split64All", "split64All"),
                "split42All": _get(row, "Split42All", "split42All"),
                "split21All": _get(row, "Split21All", "split21All"),
                "last400Class": _get(row, "Last400Class", "last400Class"),
                "last200Class": _get(row, "Last200Class", "last200Class"),
                "last100Class": _get(row, "Last100Class", "last100Class"),
                "split64Class": _get(row, "Split64Class", "split64Class"),
                "split42Class": _get(row, "Split42Class", "split42Class"),
                "split21Class": _get(row, "Split21Class", "split21Class"),
            }
        )
    return import_benchmarks_payload(conn, list(by_race.values()), source=source)


def import_sectionals_file(conn: sqlite3.Connection, path: str | Path) -> dict[str, int]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return import_sectionals_payload(conn, load_json_payload(path), source=str(path))
    return import_sectionals_csv_rows(conn, load_csv_rows(path), source=str(path))


def import_benchmarks_file(conn: sqlite3.Connection, path: str | Path) -> dict[str, int]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return import_benchmarks_payload(conn, load_json_payload(path), source=str(path))
    return import_benchmarks_csv_rows(conn, load_csv_rows(path), source=str(path))


def _normalize_run_style(value: Any) -> str | None:
    text = clean(value)
    if not text:
        return None
    t = text.lower().replace(" ", "")
    mapping = {
        "ld": "Leader",
        "leader": "Leader",
        "on": "On Pace",
        "onpace": "On Pace",
        "op": "On Pace",
        "mf": "Midfield",
        "midfield": "Midfield",
        "mf/bm": "Midfield",
        "bm": "Backmarker",
        "back": "Backmarker",
        "backmarker": "Backmarker",
        "off": "Off Pace",
        "offpace": "Off Pace",
    }
    # handle "mf/bm"
    if t in mapping:
        return mapping[t]
    for key, label in mapping.items():
        if key in t:
            return label
    return text.strip()


def _settle_from_rating(item: dict[str, Any]) -> int | None:
    pred = parse_float(_get(item, "predictedSettlePostion", "predictedSettlePosition"))
    avg = parse_float(
        _get(item, "averageHistoricalSettlePosition", "AverageHistoricalSettlePosition")
    )
    if pred is not None and pred > 0:
        return int(round(pred))
    if avg is not None and 0 < avg <= 20:
        return int(round(avg))
    return None


def import_ratings_payload(
    conn: sqlite3.Connection,
    payload: Any,
    *,
    source: str,
) -> dict[str, int]:
    """Import MeetingRatings rows (flat list of runners)."""
    rows = _as_list(payload)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO pf_api_imports (kind, source_path, external_meeting_id, imported_at)
        VALUES ('ratings', ?, NULL, ?)
        """,
        (source, _now()),
    )
    import_id = cur.lastrowid
    runners_n = 0
    linked_n = 0
    meeting_ext: str | None = None

    for item in rows:
        if not isinstance(item, dict):
            continue
        meeting_ext = clean(str(_get(item, "meetingId") or meeting_ext or ""))
        track = clean(_get(item, "track"))
        meeting_date = parse_date(_get(item, "meetingDate"))
        race_no = parse_int(_get(item, "raceNo", "raceNumber"))
        race_ext = _get(item, "raceId")
        tab_no = parse_int(_get(item, "tabNo", "tabNumber"))
        horse_name = clean(_get(item, "runnerName", "horseName"))
        horse_ext = _get(item, "runnerId", "horseId")
        run_style = _normalize_run_style(_get(item, "runStyle"))
        settle = _settle_from_rating(item)

        meeting_id = _ensure_meeting(
            conn,
            external_id=meeting_ext,
            track=track,
            meeting_date=meeting_date,
        )
        race_id = _ensure_race(
            conn,
            meeting_id,
            race_number=race_no,
            external_race_id=race_ext,
        )
        runner_id, horse_id = _find_runner(
            conn,
            race_id,
            tab_no=tab_no,
            horse_name=horse_name,
            horse_external_id=horse_ext,
        )
        if horse_id is None:
            horse_id = _ensure_horse(conn, name=horse_name, external_id=horse_ext)
        if horse_id is not None and (run_style or settle is not None):
            cur.execute(
                """
                UPDATE horses SET
                    run_style = COALESCE(?, run_style),
                    settle = COALESCE(?, settle)
                WHERE id = ?
                """,
                (run_style, settle, horse_id),
            )
        if runner_id is not None:
            linked_n += 1

        existing = None
        if race_id is not None and tab_no is not None:
            existing = cur.execute(
                """
                SELECT id FROM pf_ratings
                WHERE race_id = ? AND tab_no = ?
                LIMIT 1
                """,
                (race_id, tab_no),
            ).fetchone()

        values = (
            import_id,
            meeting_id,
            race_id,
            runner_id,
            horse_id,
            meeting_ext,
            str(race_ext) if race_ext is not None else None,
            race_no,
            tab_no,
            horse_name,
            str(horse_ext) if horse_ext is not None else None,
            run_style,
            settle,
            parse_float(_get(item, "averageHistoricalSettlePosition")),
            parse_float(_get(item, "predictedSettlePostion", "predictedSettlePosition")),
            parse_int(_get(item, "timeRank")),
            parse_float(_get(item, "timePrice")),
            parse_int(_get(item, "earlyTimeRank")),
            parse_float(_get(item, "earlyTimePrice")),
            parse_int(_get(item, "last600TimeRank")),
            parse_float(_get(item, "last600TimePrice")),
            parse_int(_get(item, "last400TimeRank")),
            parse_float(_get(item, "last400TimePrice")),
            parse_int(_get(item, "last200TimeRank")),
            parse_float(_get(item, "last200TimePrice")),
            parse_int(_get(item, "weightClassRank")),
            parse_float(_get(item, "weightClassPrice")),
            parse_int(_get(item, "timeAdjustedWeightClassRank")),
            parse_float(_get(item, "timeAdjustedWeightClassPrice")),
            parse_int(_get(item, "pfaiRank")),
            parse_float(_get(item, "pfaiScore")),
            parse_float(_get(item, "pfaiPrice")),
            parse_float(_get(item, "pfScore")),
            1 if _get(item, "isReliable") in (True, 1, "1", "true", "True") else 0,
            json.dumps(item),
        )
        if existing:
            cur.execute(
                """
                UPDATE pf_ratings SET
                    import_id=?, meeting_id=?, race_id=?, runner_id=?, horse_id=?,
                    external_meeting_id=?, external_race_id=?, race_number=?, tab_no=?,
                    horse_name=?, external_horse_id=?,
                    run_style=?, settle=?, avg_hist_settle=?, predicted_settle=?,
                    time_rank=?, time_price=?,
                    early_time_rank=?, early_time_price=?,
                    last600_rank=?, last600_price=?,
                    last400_rank=?, last400_price=?,
                    last200_rank=?, last200_price=?,
                    weight_class_rank=?, weight_class_price=?,
                    taw_class_rank=?, taw_class_price=?,
                    pfai_rank=?, pfai_score=?, pfai_price=?, pf_score=?,
                    is_reliable=?, raw_json=?
                WHERE id=?
                """,
                values + (existing["id"],),
            )
        else:
            cur.execute(
                """
                INSERT INTO pf_ratings (
                    import_id, meeting_id, race_id, runner_id, horse_id,
                    external_meeting_id, external_race_id, race_number, tab_no,
                    horse_name, external_horse_id,
                    run_style, settle, avg_hist_settle, predicted_settle,
                    time_rank, time_price,
                    early_time_rank, early_time_price,
                    last600_rank, last600_price,
                    last400_rank, last400_price,
                    last200_rank, last200_price,
                    weight_class_rank, weight_class_price,
                    taw_class_rank, taw_class_price,
                    pfai_rank, pfai_score, pfai_price, pf_score,
                    is_reliable, raw_json
                ) VALUES (
                    ?,?,?,?,?,
                    ?,?,?,?,
                    ?,?,
                    ?,?,?,?,
                    ?,?,
                    ?,?,
                    ?,?,
                    ?,?,
                    ?,?,
                    ?,?,
                    ?,?,
                    ?,?,?,?,
                    ?,?
                )
                """,
                values,
            )
        runners_n += 1

    if meeting_ext:
        cur.execute(
            "UPDATE pf_api_imports SET external_meeting_id = ? WHERE id = ?",
            (meeting_ext, import_id),
        )
    conn.commit()
    return {
        "import_id": import_id,
        "runners": runners_n,
        "linked_runners": linked_n,
        "external_meeting_id": int(meeting_ext) if meeting_ext and str(meeting_ext).isdigit() else 0,
    }


def import_ratings_csv_rows(
    conn: sqlite3.Connection,
    rows: Iterable[dict[str, str]],
    *,
    source: str,
) -> dict[str, int]:
    items = []
    for row in rows:
        items.append(
            {
                "meetingId": _get(row, "MeetingId", "meetingId"),
                "track": _get(row, "Track", "track"),
                "meetingDate": _get(row, "MeetingDate", "meetingDate"),
                "raceId": _get(row, "RaceId", "raceId"),
                "raceNo": _get(row, "RaceNo", "RaceNumber", "raceNo"),
                "tabNo": _get(row, "TabNo", "tabNo"),
                "runnerName": _get(row, "RunnerName", "HorseName", "runnerName"),
                "runnerId": _get(row, "RunnerId", "runnerId"),
                "runStyle": _get(row, "RunStyle", "runStyle"),
                "predictedSettlePostion": _get(
                    row, "PredictedSettlePostion", "PredictedSettlePosition"
                ),
                "averageHistoricalSettlePosition": _get(
                    row, "AverageHistoricalSettlePosition"
                ),
                "timeRank": _get(row, "TimeRank"),
                "timePrice": _get(row, "TimePrice"),
                "earlyTimeRank": _get(row, "EarlyTimeRank"),
                "earlyTimePrice": _get(row, "EarlyTimePrice"),
                "last600TimeRank": _get(row, "Last600TimeRank"),
                "last600TimePrice": _get(row, "Last600TimePrice"),
                "last400TimeRank": _get(row, "Last400TimeRank"),
                "last400TimePrice": _get(row, "Last400TimePrice"),
                "last200TimeRank": _get(row, "Last200TimeRank"),
                "last200TimePrice": _get(row, "Last200TimePrice"),
                "weightClassRank": _get(row, "WeightClassRank"),
                "weightClassPrice": _get(row, "WeightClassPrice"),
                "timeAdjustedWeightClassRank": _get(row, "TimeAdjustedWeightClassRank"),
                "timeAdjustedWeightClassPrice": _get(row, "TimeAdjustedWeightClassPrice"),
                "pfaiRank": _get(row, "PfaiRank", "PFAIRank"),
                "pfaiScore": _get(row, "PfaiScore", "PFAIScore"),
                "pfaiPrice": _get(row, "PfaiPrice", "PFAIPrice"),
                "pfScore": _get(row, "PFScore", "PfScore"),
                "isReliable": _get(row, "IsReliable", "isReliable"),
            }
        )
    return import_ratings_payload(conn, items, source=source)


def import_ratings_file(conn: sqlite3.Connection, path: str | Path) -> dict[str, int]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return import_ratings_payload(conn, load_json_payload(path), source=str(path))
    return import_ratings_csv_rows(conn, load_csv_rows(path), source=str(path))
