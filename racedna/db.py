from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT,
    track TEXT NOT NULL,
    meeting_date TEXT NOT NULL,
    country TEXT,
    UNIQUE(track, meeting_date)
);

CREATE TABLE IF NOT EXISTS races (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    external_id TEXT,
    race_number INTEGER NOT NULL,
    name TEXT,
    start_time TEXT,
    distance INTEGER,
    class_text TEXT,
    age_restrictions TEXT,
    sex_restrictions TEXT,
    weight_type TEXT,
    weight_restrictions TEXT,
    prize_money TEXT,
    track_condition TEXT,
    track_condition_number INTEGER,
    official_time TEXT,
    sectional_distance INTEGER,
    official_sectional REAL,
    UNIQUE(meeting_id, race_number)
);

CREATE TABLE IF NOT EXISTS horses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,
    name TEXT NOT NULL,
    age INTEGER,
    sex TEXT,
    sire TEXT,
    dam TEXT,
    country TEXT,
    run_style TEXT,
    settle INTEGER
);

CREATE TABLE IF NOT EXISTS runners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    race_id INTEGER NOT NULL REFERENCES races(id) ON DELETE CASCADE,
    horse_id INTEGER NOT NULL REFERENCES horses(id),
    tab_no INTEGER,
    jockey TEXT,
    trainer TEXT,
    barrier INTEGER,
    weight REAL,
    claim REAL,
    last10 TEXT,
    record TEXT,
    record_distance TEXT,
    record_track TEXT,
    record_track_distance TEXT,
    record_firm TEXT,
    record_good TEXT,
    record_soft TEXT,
    record_heavy TEXT,
    record_synthetic TEXT,
    record_first_up TEXT,
    record_second_up TEXT,
    prize_money TEXT,
    UNIQUE(race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS form_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    runner_id INTEGER NOT NULL REFERENCES runners(id) ON DELETE CASCADE,
    form_date TEXT,
    track TEXT,
    race_name TEXT,
    class_text TEXT,
    distance INTEGER,
    condition TEXT,
    jockey TEXT,
    weight REAL,
    barrier INTEGER,
    position INTEGER,
    margin REAL,
    price REAL,
    race_time TEXT,
    other_runners TEXT,
    sectional_raw TEXT,
    sectional_time REAL,
    sectional_distance INTEGER,
    prize_money TEXT,
    prize_won TEXT
);

CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    runner_id INTEGER NOT NULL UNIQUE REFERENCES runners(id) ON DELETE CASCADE,
    position INTEGER,
    margin REAL,
    price REAL,
    flucs TEXT,
    in_run TEXT,
    gear_changes TEXT,
    stewards TEXT,
    jockey_claim REAL,
    original_barrier INTEGER
);

CREATE TABLE IF NOT EXISTS sectional_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    horse_name TEXT,
    run_style TEXT,
    settle INTEGER,
    ocr_text TEXT,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sectional_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER REFERENCES sectional_imports(id) ON DELETE CASCADE,
    horse_id INTEGER REFERENCES horses(id),
    form_run_id INTEGER REFERENCES form_runs(id),
    form_date TEXT,
    track TEXT,
    barrier INTEGER,
    rail TEXT,
    distance INTEGER,
    margin REAL,
    finish_pos INTEGER,
    finish_time TEXT,
    split_to6 INTEGER,
    split_12_10 INTEGER,
    split_10_8 INTEGER,
    split_8_6 INTEGER,
    split_6_4 INTEGER,
    split_4_2 INTEGER,
    split_2_f INTEGER,
    l12 REAL,
    l10 REAL,
    l8 REAL,
    l6 REAL,
    l4 REAL,
    l2 REAL,
    early_pace_runner TEXT,
    early_pace_race TEXT,
    bmark_runner_fin REAL,
    raw_line TEXT
);

CREATE INDEX IF NOT EXISTS idx_races_meeting ON races(meeting_id);
CREATE INDEX IF NOT EXISTS idx_runners_race ON runners(race_id);
CREATE INDEX IF NOT EXISTS idx_form_runner ON form_runs(runner_id);
CREATE INDEX IF NOT EXISTS idx_horses_name ON horses(name);
CREATE INDEX IF NOT EXISTS idx_meetings_track_date ON meetings(track, meeting_date);
CREATE INDEX IF NOT EXISTS idx_sectional_horse ON sectional_runs(horse_id);
CREATE INDEX IF NOT EXISTS idx_sectional_date ON sectional_runs(form_date);

CREATE TABLE IF NOT EXISTS pf_api_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    source_path TEXT,
    external_meeting_id TEXT,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pf_sectionals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER REFERENCES pf_api_imports(id) ON DELETE CASCADE,
    meeting_id INTEGER REFERENCES meetings(id),
    race_id INTEGER REFERENCES races(id),
    runner_id INTEGER REFERENCES runners(id),
    horse_id INTEGER REFERENCES horses(id),
    external_meeting_id TEXT,
    external_race_id TEXT,
    race_number INTEGER,
    tab_no INTEGER,
    horse_name TEXT,
    form_date TEXT,
    track TEXT,
    distance INTEGER,
    time_to_fin REAL,
    last1200 REAL,
    last1000 REAL,
    last800 REAL,
    last600 REAL,
    last400 REAL,
    last200 REAL,
    last100 REAL,
    split_12_10 REAL,
    split_10_8 REAL,
    split_8_6 REAL,
    split_6_4 REAL,
    split_4_2 REAL,
    split_2_1 REAL,
    pos_600 INTEGER,
    pos_400 INTEGER,
    pos_200 INTEGER,
    pos_fin INTEGER,
    marg_fin REAL,
    meeting_rank_6f INTEGER,
    meeting_rank_4f INTEGER,
    meeting_rank_2f INTEGER,
    early_200_avg REAL,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS pf_benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER REFERENCES pf_api_imports(id) ON DELETE CASCADE,
    meeting_id INTEGER REFERENCES meetings(id),
    race_id INTEGER REFERENCES races(id),
    runner_id INTEGER REFERENCES runners(id),
    horse_id INTEGER REFERENCES horses(id),
    external_meeting_id TEXT,
    external_race_id TEXT,
    race_number INTEGER,
    tab_no INTEGER,
    horse_name TEXT,
    external_horse_id TEXT,
    to600_all REAL,
    last600_all REAL,
    finish_all REAL,
    to600_class REAL,
    last600_class REAL,
    finish_class REAL,
    last400_all REAL,
    last200_all REAL,
    last100_all REAL,
    split64_all REAL,
    split42_all REAL,
    split21_all REAL,
    last400_class REAL,
    last200_class REAL,
    last100_class REAL,
    split64_class REAL,
    split42_class REAL,
    split21_class REAL,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_pf_sec_meeting ON pf_sectionals(meeting_id);
CREATE INDEX IF NOT EXISTS idx_pf_sec_runner ON pf_sectionals(runner_id);
CREATE INDEX IF NOT EXISTS idx_pf_sec_horse ON pf_sectionals(horse_id);
CREATE INDEX IF NOT EXISTS idx_pf_bmark_meeting ON pf_benchmarks(meeting_id);
CREATE INDEX IF NOT EXISTS idx_pf_bmark_runner ON pf_benchmarks(runner_id);
CREATE INDEX IF NOT EXISTS idx_pf_bmark_race_tab ON pf_benchmarks(race_id, tab_no);
"""

MIGRATIONS = [
    ("horses", "run_style", "ALTER TABLE horses ADD COLUMN run_style TEXT"),
    ("horses", "settle", "ALTER TABLE horses ADD COLUMN settle INTEGER"),
]


def default_db_path() -> Path:
    return Path("data/racedna.db")


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] if isinstance(r, sqlite3.Row) else r[1] for r in rows}


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for table, column, ddl in MIGRATIONS:
        cols = _existing_columns(conn, table)
        if column not in cols:
            conn.execute(ddl)
    conn.commit()
