from __future__ import annotations

import csv
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from racedna.parsers import clean, parse_date, parse_float, parse_int

RACE_FIELD_RE = re.compile(r"^RaceResults\[(\d+)\]\.(.+)$")
RUNNER_FIELD_RE = re.compile(r"^Runners\[(\d+)\]\.(.+)$")


def _load_wide_results(path: str | Path) -> tuple[dict[str, str], dict[int, dict]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))

    header: list[str] | None = None
    data: list[str] | None = None
    for i, row in enumerate(rows):
        if row and row[0] == "MeetingId":
            header = row
            if i + 1 < len(rows):
                data = rows[i + 1]
            break
    if not header or not data:
        raise ValueError(f"Could not find MeetingId header/data in {path}")

    # pad
    if len(data) < len(header):
        data = data + [""] * (len(header) - len(data))

    meeting_meta = {
        "MeetingId": clean(data[header.index("MeetingId")]) if "MeetingId" in header else None,
        "Track": clean(data[header.index("Track")]) if "Track" in header else None,
        "MeetingDate": clean(data[header.index("MeetingDate")]) if "MeetingDate" in header else None,
        "TrackId": clean(data[header.index("TrackId")]) if "TrackId" in header else None,
    }

    races: dict[int, dict] = defaultdict(lambda: {"fields": {}, "runners": defaultdict(dict)})
    for col, value in zip(header, data):
        m = RACE_FIELD_RE.match(col)
        if not m:
            continue
        race_idx = int(m.group(1))
        rest = m.group(2)
        rm = RUNNER_FIELD_RE.match(rest)
        if rm:
            runner_idx = int(rm.group(1))
            field = rm.group(2)
            races[race_idx]["runners"][runner_idx][field] = value
        else:
            races[race_idx]["fields"][rest] = value

    return meeting_meta, races


def import_results(conn: sqlite3.Connection, path: str | Path) -> dict[str, int]:
    meeting_meta, races = _load_wide_results(path)
    track = meeting_meta.get("Track")
    meeting_date = parse_date(meeting_meta.get("MeetingDate"))
    if not track or not meeting_date:
        raise ValueError("Results CSV missing Track / MeetingDate")

    cur = conn.cursor()
    meeting = cur.execute(
        "SELECT id FROM meetings WHERE track = ? AND meeting_date = ?",
        (track, meeting_date),
    ).fetchone()
    if not meeting:
        # try by external id
        ext = meeting_meta.get("MeetingId")
        if ext:
            meeting = cur.execute(
                "SELECT id FROM meetings WHERE external_id = ?", (ext,)
            ).fetchone()
    if not meeting:
        cur.execute(
            """
            INSERT INTO meetings (external_id, track, meeting_date)
            VALUES (?, ?, ?)
            """,
            (meeting_meta.get("MeetingId"), track, meeting_date),
        )
        meeting_id = cur.lastrowid
    else:
        meeting_id = meeting["id"]
        if meeting_meta.get("MeetingId"):
            cur.execute(
                "UPDATE meetings SET external_id = ? WHERE id = ?",
                (meeting_meta["MeetingId"], meeting_id),
            )

    races_updated = 0
    results_n = 0
    runners_linked = 0

    for _, race_blob in sorted(races.items()):
        fields = race_blob["fields"]
        race_number = parse_int(fields.get("RaceNumber"))
        if race_number is None:
            continue

        race_row = cur.execute(
            "SELECT id FROM races WHERE meeting_id = ? AND race_number = ?",
            (meeting_id, race_number),
        ).fetchone()
        if not race_row:
            cur.execute(
                """
                INSERT INTO races (
                    meeting_id, external_id, race_number, distance, class_text,
                    weight_type, weight_restrictions, track_condition,
                    track_condition_number, official_time, sectional_distance,
                    official_sectional
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meeting_id,
                    clean(fields.get("RaceId")),
                    race_number,
                    parse_int(fields.get("Distance")),
                    clean(fields.get("RaceClass")),
                    clean(fields.get("WeightType")),
                    clean(fields.get("LimitWeight")),
                    clean(fields.get("TrackConditionLabel") or fields.get("TrackCondition")),
                    parse_int(fields.get("TrackConditionNumber")),
                    clean(fields.get("OfficialRaceTimeString") or fields.get("OfficialRaceTime")),
                    parse_int(fields.get("SectionalDistance")),
                    parse_float(fields.get("OfficialSectionalTime")),
                ),
            )
            race_id = cur.lastrowid
        else:
            race_id = race_row["id"]
            cur.execute(
                """
                UPDATE races SET
                    external_id = COALESCE(?, external_id),
                    track_condition = COALESCE(?, track_condition),
                    track_condition_number = COALESCE(?, track_condition_number),
                    official_time = COALESCE(?, official_time),
                    sectional_distance = COALESCE(?, sectional_distance),
                    official_sectional = COALESCE(?, official_sectional),
                    distance = COALESCE(?, distance),
                    class_text = COALESCE(?, class_text)
                WHERE id = ?
                """,
                (
                    clean(fields.get("RaceId")),
                    clean(fields.get("TrackConditionLabel") or fields.get("TrackCondition")),
                    parse_int(fields.get("TrackConditionNumber")),
                    clean(fields.get("OfficialRaceTimeString") or fields.get("OfficialRaceTime")),
                    parse_int(fields.get("SectionalDistance")),
                    parse_float(fields.get("OfficialSectionalTime")),
                    parse_int(fields.get("Distance")),
                    clean(fields.get("RaceClass")),
                    race_id,
                ),
            )
        races_updated += 1

        for _, runner in sorted(race_blob["runners"].items()):
            name = clean(runner.get("Runner"))
            if not name:
                continue
            tab_no = parse_int(runner.get("TabNo"))
            runner_ext = clean(runner.get("RunnerId"))

            # Find or create horse + runner
            horse_id = None
            if runner_ext:
                h = cur.execute(
                    "SELECT id FROM horses WHERE external_id = ?", (runner_ext,)
                ).fetchone()
                if h:
                    horse_id = h["id"]
                else:
                    cur.execute(
                        "INSERT INTO horses (external_id, name) VALUES (?, ?)",
                        (runner_ext, name),
                    )
                    horse_id = cur.lastrowid
            if horse_id is None:
                # match by name within race
                existing_runner = cur.execute(
                    """
                    SELECT runners.id AS runner_id, horses.id AS horse_id
                    FROM runners
                    JOIN horses ON horses.id = runners.horse_id
                    WHERE runners.race_id = ? AND lower(horses.name) = lower(?)
                    """,
                    (race_id, name),
                ).fetchone()
                if existing_runner:
                    db_runner_id = existing_runner["runner_id"]
                    horse_id = existing_runner["horse_id"]
                else:
                    cur.execute("INSERT INTO horses (name) VALUES (?)", (name,))
                    horse_id = cur.lastrowid
                    cur.execute(
                        """
                        INSERT INTO runners (race_id, horse_id, tab_no, jockey, trainer, barrier, weight)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            race_id,
                            horse_id,
                            tab_no,
                            clean(runner.get("Jockey")),
                            clean(runner.get("Trainer")),
                            parse_int(runner.get("Barrier")),
                            parse_float(runner.get("Weight")),
                        ),
                    )
                    db_runner_id = cur.lastrowid
            else:
                existing_runner = cur.execute(
                    "SELECT id FROM runners WHERE race_id = ? AND horse_id = ?",
                    (race_id, horse_id),
                ).fetchone()
                if existing_runner:
                    db_runner_id = existing_runner["id"]
                else:
                    # maybe same horse name already linked differently
                    by_name = cur.execute(
                        """
                        SELECT runners.id AS runner_id
                        FROM runners
                        JOIN horses ON horses.id = runners.horse_id
                        WHERE runners.race_id = ? AND lower(horses.name) = lower(?)
                        """,
                        (race_id, name),
                    ).fetchone()
                    if by_name:
                        db_runner_id = by_name["runner_id"]
                    else:
                        cur.execute(
                            """
                            INSERT INTO runners (race_id, horse_id, tab_no, jockey, trainer, barrier, weight)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                race_id,
                                horse_id,
                                tab_no,
                                clean(runner.get("Jockey")),
                                clean(runner.get("Trainer")),
                                parse_int(runner.get("Barrier")),
                                parse_float(runner.get("Weight")),
                            ),
                        )
                        db_runner_id = cur.lastrowid

            # refresh identity fields from results
            cur.execute(
                """
                UPDATE runners SET
                    tab_no = COALESCE(?, tab_no),
                    jockey = COALESCE(?, jockey),
                    trainer = COALESCE(?, trainer),
                    barrier = COALESCE(?, barrier),
                    weight = COALESCE(?, weight)
                WHERE id = ?
                """,
                (
                    tab_no,
                    clean(runner.get("Jockey")),
                    clean(runner.get("Trainer")),
                    parse_int(runner.get("Barrier")),
                    parse_float(runner.get("Weight")),
                    db_runner_id,
                ),
            )
            runners_linked += 1

            stewards = " | ".join(
                x for x in [clean(runner.get("StewardsReports")), clean(runner.get("StewardsReportsExt"))] if x
            ) or None
            cur.execute(
                """
                INSERT INTO results (
                    runner_id, position, margin, price, flucs, in_run,
                    gear_changes, stewards, jockey_claim, original_barrier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(runner_id) DO UPDATE SET
                    position = excluded.position,
                    margin = excluded.margin,
                    price = excluded.price,
                    flucs = excluded.flucs,
                    in_run = excluded.in_run,
                    gear_changes = excluded.gear_changes,
                    stewards = excluded.stewards,
                    jockey_claim = excluded.jockey_claim,
                    original_barrier = excluded.original_barrier
                """,
                (
                    db_runner_id,
                    parse_int(runner.get("Position")),
                    parse_float(runner.get("Margin")),
                    parse_float(runner.get("Price")),
                    clean(runner.get("Flucs")),
                    clean(runner.get("InRun")),
                    clean(runner.get("GearChanges")),
                    stewards,
                    parse_float(runner.get("JockeyClaim")),
                    parse_int(runner.get("OriginalBarrier")),
                ),
            )
            results_n += 1

    conn.commit()
    return {
        "meeting_id": meeting_id,
        "races": races_updated,
        "runners_linked": runners_linked,
        "results": results_n,
    }
