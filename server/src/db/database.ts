import { mkdirSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";

let db: DatabaseSync | null = null;
let dbPath: string | null = null;

export function getDbPath(): string {
  if (process.env.RACEDNA_DB_PATH) {
    return resolve(process.env.RACEDNA_DB_PATH);
  }
  return resolve(process.cwd(), "data", "racedna.sqlite");
}

export function openDatabase(path = getDbPath()): DatabaseSync {
  if (db && dbPath === path) return db;

  if (db) {
    db.close();
    db = null;
  }

  if (path !== ":memory:") {
    mkdirSync(dirname(path), { recursive: true });
  }

  const next = new DatabaseSync(path);
  next.exec("PRAGMA foreign_keys = ON;");
  next.exec(`
    CREATE TABLE IF NOT EXISTS meetings (
      id TEXT PRIMARY KEY,
      course TEXT NOT NULL,
      date TEXT,
      track_condition TEXT,
      source TEXT NOT NULL DEFAULT 'import',
      punting_form_meeting_id TEXT,
      imported_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS races (
      id TEXT PRIMARY KEY,
      meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
      race_number INTEGER NOT NULL,
      name TEXT NOT NULL,
      distance_meters INTEGER,
      distance_furlongs REAL NOT NULL,
      going TEXT NOT NULL,
      class_name TEXT,
      UNIQUE(meeting_id, race_number)
    );

    CREATE TABLE IF NOT EXISTS runners (
      id TEXT PRIMARY KEY,
      race_id TEXT NOT NULL REFERENCES races(id) ON DELETE CASCADE,
      tab_number INTEGER NOT NULL,
      name TEXT NOT NULL,
      recent_form TEXT NOT NULL DEFAULT '[]',
      speed_figure REAL NOT NULL DEFAULT 80,
      optimal_distance_furlongs REAL NOT NULL DEFAULT 6,
      preferred_going TEXT NOT NULL DEFAULT '["good"]',
      class_rating REAL NOT NULL DEFAULT 80,
      jockey_win_rate REAL NOT NULL DEFAULT 0.1,
      trainer_win_rate REAL NOT NULL DEFAULT 0.1,
      days_since_last_run INTEGER NOT NULL DEFAULT 21,
      barrier INTEGER,
      weight_kg REAL,
      jockey TEXT,
      trainer TEXT,
      win_odds REAL,
      place_odds REAL,
      odds_source TEXT,
      finish_position INTEGER,
      scratched INTEGER NOT NULL DEFAULT 0,
      UNIQUE(race_id, tab_number)
    );

    CREATE INDEX IF NOT EXISTS idx_races_meeting ON races(meeting_id);
    CREATE INDEX IF NOT EXISTS idx_runners_race ON runners(race_id);
    CREATE INDEX IF NOT EXISTS idx_runners_tab ON runners(race_id, tab_number);
  `);

  db = next;
  dbPath = path;
  return next;
}

export function closeDatabase(): void {
  if (db) {
    db.close();
    db = null;
    dbPath = null;
  }
}

/** Wipe and recreate the database file (used by tests / reset endpoint). */
export function recreateDatabase(): DatabaseSync {
  const path = getDbPath();
  closeDatabase();
  if (path !== ":memory:") {
    rmSync(path, { force: true });
  }
  return openDatabase(path);
}
