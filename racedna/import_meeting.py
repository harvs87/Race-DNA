from __future__ import annotations

import csv
import sqlite3
from collections import defaultdict
from pathlib import Path

from racedna.parsers import (
    clean,
    normalize_header,
    parse_date,
    parse_float,
    parse_int,
    parse_sectional,
)


def _row_get(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        if key in row and clean(row[key]) is not None:
            return clean(row[key])
        # tolerate leading spaces in headers
        for existing, value in row.items():
            if existing.strip() == key.strip() and clean(value) is not None:
                return clean(value)
    return None


def load_meeting_csv(path: str | Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        # normalize headers
        if reader.fieldnames is None:
            return []
        fieldmap = {name: normalize_header(name) for name in reader.fieldnames}
        rows: list[dict[str, str]] = []
        for raw in reader:
            row = {fieldmap[k]: (v or "").strip() for k, v in raw.items() if k is not None}
            if row.get("race number") in (None, "", "race number"):
                continue
            if not row.get("horse name"):
                continue
            rows.append(row)
        return rows


def import_meeting(conn: sqlite3.Connection, path: str | Path) -> dict[str, int]:
    rows = load_meeting_csv(path)
    if not rows:
        raise ValueError(f"No usable rows in {path}")

    first = rows[0]
    track = _row_get(first, "track") or "Unknown"
    meeting_date = parse_date(_row_get(first, "meeting date")) or "unknown"
    external_meeting = _row_get(first, "meeting id")
    country = _row_get(first, "country")

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO meetings (external_id, track, meeting_date, country)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(track, meeting_date) DO UPDATE SET
            external_id = COALESCE(excluded.external_id, meetings.external_id),
            country = COALESCE(excluded.country, meetings.country)
        """,
        (external_meeting, track, meeting_date, country),
    )
    meeting_id = cur.execute(
        "SELECT id FROM meetings WHERE track = ? AND meeting_date = ?",
        (track, meeting_date),
    ).fetchone()["id"]

    # Group by race then horse
    by_race: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rn = parse_int(row.get("race number"))
        if rn is None:
            continue
        by_race[rn].append(row)

    races_n = 0
    runners_n = 0
    form_n = 0

    for race_number, race_rows in sorted(by_race.items()):
        sample = race_rows[0]
        external_race = _row_get(sample, "race id")
        cur.execute(
            """
            INSERT INTO races (
                meeting_id, external_id, race_number, name, start_time, distance,
                class_text, age_restrictions, sex_restrictions, weight_type,
                weight_restrictions, prize_money
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(meeting_id, race_number) DO UPDATE SET
                external_id = COALESCE(excluded.external_id, races.external_id),
                name = COALESCE(excluded.name, races.name),
                start_time = COALESCE(excluded.start_time, races.start_time),
                distance = COALESCE(excluded.distance, races.distance),
                class_text = COALESCE(excluded.class_text, races.class_text),
                prize_money = COALESCE(excluded.prize_money, races.prize_money)
            """,
            (
                meeting_id,
                external_race,
                race_number,
                _row_get(sample, "race name"),
                _row_get(sample, "start time"),
                parse_int(_row_get(sample, "distance")),
                _row_get(sample, "class restrictions"),
                _row_get(sample, "age restrictions"),
                _row_get(sample, "sex restrictions"),
                _row_get(sample, "weight type"),
                _row_get(sample, "weight restrictions"),
                _row_get(sample, "race prizemoney") or _row_get(sample, "prizemoney"),
            ),
        )
        race_id = cur.execute(
            "SELECT id FROM races WHERE meeting_id = ? AND race_number = ?",
            (meeting_id, race_number),
        ).fetchone()["id"]
        races_n += 1

        by_horse: dict[tuple[str, str | None], list[dict[str, str]]] = defaultdict(list)
        for row in race_rows:
            key = (row["horse name"], _row_get(row, "horse id"))
            by_horse[key].append(row)

        for (horse_name, horse_ext), horse_rows in by_horse.items():
            h = horse_rows[0]
            horse_ext = _row_get(h, "horse id")
            if horse_ext:
                cur.execute(
                    """
                    INSERT INTO horses (external_id, name, age, sex, sire, dam, country)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(external_id) DO UPDATE SET
                        name = excluded.name,
                        age = COALESCE(excluded.age, horses.age),
                        sex = COALESCE(excluded.sex, horses.sex),
                        sire = COALESCE(excluded.sire, horses.sire),
                        dam = COALESCE(excluded.dam, horses.dam)
                    """,
                    (
                        horse_ext,
                        horse_name,
                        parse_int(_row_get(h, "horse age")),
                        _row_get(h, "horse sex"),
                        _row_get(h, "horse sire"),
                        _row_get(h, "horse dam"),
                        _row_get(h, "country"),
                    ),
                )
                horse_id = cur.execute(
                    "SELECT id FROM horses WHERE external_id = ?", (horse_ext,)
                ).fetchone()["id"]
            else:
                existing = cur.execute(
                    "SELECT id FROM horses WHERE name = ? AND external_id IS NULL",
                    (horse_name,),
                ).fetchone()
                if existing:
                    horse_id = existing["id"]
                else:
                    cur.execute(
                        """
                        INSERT INTO horses (external_id, name, age, sex, sire, dam, country)
                        VALUES (NULL, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            horse_name,
                            parse_int(_row_get(h, "horse age")),
                            _row_get(h, "horse sex"),
                            _row_get(h, "horse sire"),
                            _row_get(h, "horse dam"),
                            _row_get(h, "country"),
                        ),
                    )
                    horse_id = cur.lastrowid

            cur.execute(
                """
                INSERT INTO runners (
                    race_id, horse_id, tab_no, jockey, trainer, barrier, weight, claim,
                    last10, record, record_distance, record_track, record_track_distance,
                    record_firm, record_good, record_soft, record_heavy, record_synthetic,
                    record_first_up, record_second_up, prize_money
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(race_id, horse_id) DO UPDATE SET
                    tab_no = COALESCE(excluded.tab_no, runners.tab_no),
                    jockey = COALESCE(excluded.jockey, runners.jockey),
                    trainer = COALESCE(excluded.trainer, runners.trainer),
                    barrier = COALESCE(excluded.barrier, runners.barrier),
                    weight = COALESCE(excluded.weight, runners.weight),
                    last10 = COALESCE(excluded.last10, runners.last10),
                    record = COALESCE(excluded.record, runners.record),
                    record_track = COALESCE(excluded.record_track, runners.record_track),
                    record_soft = COALESCE(excluded.record_soft, runners.record_soft),
                    record_good = COALESCE(excluded.record_good, runners.record_good)
                """,
                (
                    race_id,
                    horse_id,
                    parse_int(_row_get(h, "horse number")),
                    _row_get(h, "horse jockey"),
                    _row_get(h, "horse trainer"),
                    parse_int(_row_get(h, "horse barrier")),
                    parse_float(_row_get(h, "horse weight")),
                    parse_float(_row_get(h, "horse claim")),
                    _row_get(h, "horse last10"),
                    _row_get(h, "horse record"),
                    _row_get(h, "horse record distance"),
                    _row_get(h, "horse record track"),
                    _row_get(h, "horse record track distance"),
                    _row_get(h, "horse record firm"),
                    _row_get(h, "horse record good"),
                    _row_get(h, "horse record soft"),
                    _row_get(h, "horse record heavy"),
                    _row_get(h, "horse record synthetic"),
                    _row_get(h, "horse record first up"),
                    _row_get(h, "horse record second up"),
                    _row_get(h, "horse prize money"),
                ),
            )
            runner_id = cur.execute(
                "SELECT id FROM runners WHERE race_id = ? AND horse_id = ?",
                (race_id, horse_id),
            ).fetchone()["id"]
            runners_n += 1

            # Replace form lines for this runner on re-import
            cur.execute("DELETE FROM form_runs WHERE runner_id = ?", (runner_id,))
            seen_form: set[tuple] = set()
            for fr in horse_rows:
                form_date = parse_date(_row_get(fr, "form meeting date"))
                form_track = _row_get(fr, "form track")
                form_pos = parse_int(_row_get(fr, "form position"))
                form_name = _row_get(fr, "form name")
                if not any([form_date, form_track, form_pos, form_name]):
                    continue
                key = (form_date, form_track, form_name, form_pos, _row_get(fr, "form distance"))
                if key in seen_form:
                    continue
                seen_form.add(key)
                sec_time, sec_dist = parse_sectional(_row_get(fr, "sectional"))
                cur.execute(
                    """
                    INSERT INTO form_runs (
                        runner_id, form_date, track, race_name, class_text, distance,
                        condition, jockey, weight, barrier, position, margin, price,
                        race_time, other_runners, sectional_raw, sectional_time,
                        sectional_distance, prize_money, prize_won
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        runner_id,
                        form_date,
                        form_track,
                        form_name,
                        _row_get(fr, "form class"),
                        parse_int(_row_get(fr, "form distance")),
                        _row_get(fr, "form track condition"),
                        _row_get(fr, "form jockey"),
                        parse_float(_row_get(fr, "form weight")),
                        parse_int(_row_get(fr, "form barrier")),
                        form_pos,
                        parse_float(_row_get(fr, "form margin")),
                        parse_float(_row_get(fr, "form price")),
                        _row_get(fr, "form time"),
                        _row_get(fr, "form other runners"),
                        _row_get(fr, "sectional"),
                        sec_time,
                        sec_dist,
                        _row_get(fr, "prizemoney"),
                        _row_get(fr, "prizemoney won"),
                    ),
                )
                form_n += 1

    conn.commit()
    return {
        "meeting_id": meeting_id,
        "races": races_n,
        "runners": runners_n,
        "form_runs": form_n,
    }
