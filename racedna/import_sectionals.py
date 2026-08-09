from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from racedna.ocr import ocr_image
from racedna.sectional_parse import (
    SectionalHorsePage,
    parse_sectional_json,
    parse_sectional_text,
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
TEXT_SUFFIXES = {".txt", ".sectional.txt"}
JSON_SUFFIXES = {".json", ".sectional.json"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_sectional_page(path: str | Path) -> SectionalHorsePage:
    path = Path(path)
    suffix = path.suffix.lower()
    # double suffix like horse.sectional.json
    name_lower = path.name.lower()

    sidecar_json = path.with_suffix(path.suffix + ".json") if suffix in IMAGE_SUFFIXES else None
    alt_json = path.with_name(path.stem + ".sectional.json")
    alt_txt = path.with_name(path.stem + ".sectional.txt")

    if name_lower.endswith(".sectional.json") or suffix in JSON_SUFFIXES:
        return parse_sectional_json(path)
    if name_lower.endswith(".sectional.txt") or suffix in TEXT_SUFFIXES:
        text = path.read_text(encoding="utf-8")
        return parse_sectional_text(text, source=str(path))

    # Prefer structured sidecars when present next to a screenshot
    for candidate in (alt_json, sidecar_json):
        if candidate and candidate.exists():
            page = parse_sectional_json(candidate)
            page.source = str(path)
            return page
    if alt_txt.exists():
        page = parse_sectional_text(alt_txt.read_text(encoding="utf-8"), source=str(path))
        return page

    if suffix in IMAGE_SUFFIXES:
        text = ocr_image(path)
        page = parse_sectional_text(text, source=str(path))
        page.ocr_text = text
        return page

    # Generic text fallback
    text = path.read_text(encoding="utf-8", errors="ignore")
    return parse_sectional_text(text, source=str(path))


def _find_horse_id(conn: sqlite3.Connection, name: str | None) -> int | None:
    if not name:
        return None
    row = conn.execute(
        "SELECT id FROM horses WHERE lower(name) = lower(?) ORDER BY id LIMIT 1",
        (name,),
    ).fetchone()
    if row:
        return row["id"]
    # fuzzy: ignore spaces/apostrophes
    compact = "".join(ch for ch in name.lower() if ch.isalnum())
    rows = conn.execute("SELECT id, name FROM horses").fetchall()
    for r in rows:
        other = "".join(ch for ch in (r["name"] or "").lower() if ch.isalnum())
        if other == compact:
            return r["id"]
    return None


def _ensure_horse(conn: sqlite3.Connection, page: SectionalHorsePage) -> int | None:
    if not page.horse_name:
        return None
    horse_id = _find_horse_id(conn, page.horse_name)
    cur = conn.cursor()
    if horse_id is None:
        cur.execute(
            """
            INSERT INTO horses (name, age, sire, dam, run_style, settle)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (page.horse_name, page.age, page.sire, page.dam, page.run_style, page.settle),
        )
        horse_id = cur.lastrowid
    else:
        cur.execute(
            """
            UPDATE horses SET
                age = COALESCE(?, age),
                sire = COALESCE(?, sire),
                dam = COALESCE(?, dam),
                run_style = COALESCE(?, run_style),
                settle = COALESCE(?, settle)
            WHERE id = ?
            """,
            (page.age, page.sire, page.dam, page.run_style, page.settle, horse_id),
        )
    return horse_id


def _link_form_run(
    conn: sqlite3.Connection,
    horse_id: int | None,
    form_date: str | None,
    track: str | None,
    distance: int | None,
) -> int | None:
    if horse_id is None or form_date is None:
        return None
    sql = """
        SELECT form_runs.id
        FROM form_runs
        JOIN runners ON runners.id = form_runs.runner_id
        WHERE runners.horse_id = ? AND form_runs.form_date = ?
    """
    params: list = [horse_id, form_date]
    if track:
        sql += " AND form_runs.track IS NOT NULL AND lower(form_runs.track) LIKE ?"
        params.append(f"%{track.lower()[:6]}%")
    if distance:
        sql += " AND (form_runs.distance IS NULL OR ABS(form_runs.distance - ?) <= 50)"
        params.append(distance)
    sql += " ORDER BY form_runs.id DESC LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    return row["id"] if row else None


def import_sectional(conn: sqlite3.Connection, path: str | Path) -> dict:
    path = Path(path)
    page = load_sectional_page(path)
    horse_id = _ensure_horse(conn, page)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO sectional_imports (source_path, horse_name, run_style, settle, ocr_text, imported_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(path),
            page.horse_name,
            page.run_style,
            page.settle,
            page.ocr_text,
            _now(),
        ),
    )
    import_id = cur.lastrowid

    linked = 0
    for row in page.rows:
        form_run_id = _link_form_run(
            conn, horse_id, row.form_date, row.track, row.distance
        )
        if form_run_id:
            linked += 1
            # Enrich form_runs L600 if we have l6 and form sectional empty
            if row.l6:
                cur.execute(
                    """
                    UPDATE form_runs
                    SET sectional_time = COALESCE(sectional_time, ?),
                        sectional_distance = COALESCE(sectional_distance, 600)
                    WHERE id = ? AND (sectional_time IS NULL OR sectional_time = 0)
                    """,
                    (row.l6, form_run_id),
                )
        cur.execute(
            """
            INSERT INTO sectional_runs (
                import_id, horse_id, form_run_id, form_date, track, barrier, rail,
                distance, margin, finish_pos, finish_time,
                split_to6, split_12_10, split_10_8, split_8_6, split_6_4, split_4_2, split_2_f,
                l12, l10, l8, l6, l4, l2,
                early_pace_runner, early_pace_race, bmark_runner_fin, raw_line
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                import_id,
                horse_id,
                form_run_id,
                row.form_date,
                row.track,
                row.barrier,
                row.rail,
                row.distance,
                row.margin,
                row.finish_pos,
                row.finish_time,
                row.split_to6,
                row.split_12_10,
                row.split_10_8,
                row.split_8_6,
                row.split_6_4,
                row.split_4_2,
                row.split_2_f,
                row.l12,
                row.l10,
                row.l8,
                row.l6,
                row.l4,
                row.l2,
                row.early_pace_runner,
                row.early_pace_race,
                row.bmark_runner_fin,
                row.raw_line,
            ),
        )

    conn.commit()
    return {
        "source": str(path),
        "horse_name": page.horse_name,
        "horse_id": horse_id,
        "run_style": page.run_style,
        "settle": page.settle,
        "rows": len(page.rows),
        "linked_form_runs": linked,
        "import_id": import_id,
    }


def import_sectionals_dir(conn: sqlite3.Connection, folder: str | Path) -> list[dict]:
    folder = Path(folder)
    if not folder.exists():
        return []
    paths: list[Path] = []
    for pattern in (
        "*.png",
        "*.jpg",
        "*.jpeg",
        "*.webp",
        "*.sectional.txt",
        "*.sectional.json",
        "*.txt",
        "*.json",
    ):
        paths.extend(sorted(folder.rglob(pattern)))
    # De-dupe while preferring structured files over raw images with sidecars
    seen: set[str] = set()
    reports = []
    for path in sorted(paths, key=lambda p: str(p).lower()):
        key = str(path.resolve())
        if key in seen:
            continue
        # Skip generic json/txt that aren't sectional-named unless under a sectionals folder
        name = path.name.lower()
        under_sectionals = any(part.lower() == "sectionals" for part in path.parts)
        if path.suffix.lower() in {".txt", ".json"} and "sectional" not in name:
            if not under_sectionals:
                continue
        seen.add(key)
        # If image has sidecar structured file, import structured file only once
        if path.suffix.lower() in IMAGE_SUFFIXES:
            sidecar_json = path.with_name(path.stem + ".sectional.json")
            sidecar_txt = path.with_name(path.stem + ".sectional.txt")
            if sidecar_json.exists():
                key_s = str(sidecar_json.resolve())
                if key_s not in seen:
                    seen.add(key_s)
                    reports.append(import_sectional(conn, sidecar_json))
                continue
            if sidecar_txt.exists():
                key_s = str(sidecar_txt.resolve())
                if key_s not in seen:
                    seen.add(key_s)
                    reports.append(import_sectional(conn, sidecar_txt))
                continue
        reports.append(import_sectional(conn, path))
    return reports
