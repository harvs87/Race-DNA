import type {
  DashboardSummary,
  Going,
  Horse,
  ImportReport,
  MeetingDetail,
  MeetingSummary,
  Race,
} from "../analysis/types.js";
import { analyzeRace } from "../analysis/engine.js";
import { openDatabase, recreateDatabase } from "../db/database.js";
import { parseMeetingCsv } from "../import/meetingCsv.js";
import { importOddsCsv } from "../import/oddsCsv.js";
import { importResultsCsv } from "../import/resultsCsv.js";
import { seedRaces } from "./races.js";

function nowIso(): string {
  return new Date().toISOString();
}

function meetingStats(races: Race[]): Pick<
  MeetingSummary,
  "raceCount" | "runnerCount" | "resultsCount" | "oddsCount"
> {
  let runnerCount = 0;
  let resultsCount = 0;
  let oddsCount = 0;
  for (const race of races) {
    runnerCount += race.runners.length;
    for (const runner of race.runners) {
      if (runner.finishPosition !== undefined) resultsCount += 1;
      if (runner.winOdds !== undefined) oddsCount += 1;
    }
  }
  return {
    raceCount: races.length,
    runnerCount,
    resultsCount,
    oddsCount,
  };
}

function parseJson<T>(value: unknown, fallback: T): T {
  if (value === null || value === undefined || value === "") return fallback;
  try {
    return JSON.parse(String(value)) as T;
  } catch {
    return fallback;
  }
}

function rowToHorse(row: Record<string, unknown>): Horse {
  return {
    id: String(row.id),
    tabNumber: Number(row.tab_number),
    name: String(row.name),
    recentForm: parseJson<number[]>(row.recent_form, []),
    speedFigure: Number(row.speed_figure),
    optimalDistanceFurlongs: Number(row.optimal_distance_furlongs),
    preferredGoing: parseJson<Going[]>(row.preferred_going, ["good"]),
    classRating: Number(row.class_rating),
    jockeyWinRate: Number(row.jockey_win_rate),
    trainerWinRate: Number(row.trainer_win_rate),
    daysSinceLastRun: Number(row.days_since_last_run),
    barrier: row.barrier === null || row.barrier === undefined ? undefined : Number(row.barrier),
    weightKg: row.weight_kg === null || row.weight_kg === undefined ? undefined : Number(row.weight_kg),
    jockey: row.jockey ? String(row.jockey) : undefined,
    trainer: row.trainer ? String(row.trainer) : undefined,
    winOdds: row.win_odds === null || row.win_odds === undefined ? undefined : Number(row.win_odds),
    placeOdds:
      row.place_odds === null || row.place_odds === undefined ? undefined : Number(row.place_odds),
    oddsSource: row.odds_source ? String(row.odds_source) : undefined,
    finishPosition:
      row.finish_position === null || row.finish_position === undefined
        ? undefined
        : Number(row.finish_position),
    scratched: Number(row.scratched) === 1,
    age: row.age === null || row.age === undefined ? undefined : Number(row.age),
    sex: row.sex ? String(row.sex) : undefined,
    sire: row.sire ? String(row.sire) : undefined,
    dam: row.dam ? String(row.dam) : undefined,
    claim: row.claim === null || row.claim === undefined ? undefined : Number(row.claim),
    last10: row.last10 ? String(row.last10) : undefined,
    record: row.record ? String(row.record) : undefined,
    prizeMoney: row.prize_money ? String(row.prize_money) : undefined,
    puntingFormHorseId: row.punting_form_horse_id
      ? String(row.punting_form_horse_id)
      : undefined,
    formHistory: parseJson(row.form_history, undefined),
    extras: parseJson(row.extras, undefined),
  };
}

function loadRacesForMeeting(meetingId: string, course: string, date?: string): Race[] {
  const db = openDatabase();
  const raceRows = db
    .prepare(
      `SELECT * FROM races WHERE meeting_id = ? ORDER BY race_number ASC`,
    )
    .all(meetingId) as Array<Record<string, unknown>>;

  return raceRows.map((raceRow) => {
    const runners = (
      db
        .prepare(`SELECT * FROM runners WHERE race_id = ? ORDER BY tab_number ASC`)
        .all(String(raceRow.id)) as Array<Record<string, unknown>>
    ).map(rowToHorse);

    return {
      id: String(raceRow.id),
      meetingId,
      name: String(raceRow.name),
      course,
      date: date || undefined,
      raceNumber: Number(raceRow.race_number),
      startTime: raceRow.start_time ? String(raceRow.start_time) : undefined,
      distanceFurlongs: Number(raceRow.distance_furlongs),
      distanceMeters:
        raceRow.distance_meters === null || raceRow.distance_meters === undefined
          ? undefined
          : Number(raceRow.distance_meters),
      going: String(raceRow.going) as Going,
      className: raceRow.class_name ? String(raceRow.class_name) : undefined,
      extras: parseJson(raceRow.extras, undefined),
      runners,
    };
  });
}

function persistMeeting(meeting: MeetingDetail, preserveImportedAt?: string): void {
  const db = openDatabase();
  const importedAt = preserveImportedAt ?? meeting.importedAt ?? nowIso();
  const updatedAt = nowIso();
  const stats = meetingStats(meeting.races);

  db.exec("BEGIN");
  try {
    db.prepare(`DELETE FROM meetings WHERE id = ?`).run(meeting.id);

    db.prepare(
      `INSERT INTO meetings (
        id, course, date, track_condition, source, punting_form_meeting_id, imported_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      meeting.id,
      meeting.course,
      meeting.date ?? null,
      meeting.trackCondition ?? null,
      meeting.source,
      meeting.puntingFormMeetingId ?? null,
      importedAt,
      updatedAt,
    );

    const insertRace = db.prepare(
      `INSERT INTO races (
        id, meeting_id, race_number, name, distance_meters, distance_furlongs, going, class_name,
        start_time, extras
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    );
    const insertRunner = db.prepare(
      `INSERT INTO runners (
        id, race_id, tab_number, name, recent_form, speed_figure, optimal_distance_furlongs,
        preferred_going, class_rating, jockey_win_rate, trainer_win_rate, days_since_last_run,
        barrier, weight_kg, jockey, trainer, win_odds, place_odds, odds_source, finish_position, scratched,
        extras, form_history, age, sex, sire, dam, claim, last10, record, prize_money, punting_form_horse_id
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    );

    for (const race of meeting.races) {
      insertRace.run(
        race.id,
        meeting.id,
        race.raceNumber,
        race.name,
        race.distanceMeters ?? null,
        race.distanceFurlongs,
        race.going,
        race.className ?? null,
        race.startTime ?? null,
        race.extras ? JSON.stringify(race.extras) : null,
      );

      for (const runner of race.runners) {
        insertRunner.run(
          runner.id,
          race.id,
          runner.tabNumber,
          runner.name,
          JSON.stringify(runner.recentForm),
          runner.speedFigure,
          runner.optimalDistanceFurlongs,
          JSON.stringify(runner.preferredGoing),
          runner.classRating,
          runner.jockeyWinRate,
          runner.trainerWinRate,
          runner.daysSinceLastRun,
          runner.barrier ?? null,
          runner.weightKg ?? null,
          runner.jockey ?? null,
          runner.trainer ?? null,
          runner.winOdds ?? null,
          runner.placeOdds ?? null,
          runner.oddsSource ?? null,
          runner.finishPosition ?? null,
          runner.scratched ? 1 : 0,
          runner.extras ? JSON.stringify(runner.extras) : null,
          runner.formHistory ? JSON.stringify(runner.formHistory) : null,
          runner.age ?? null,
          runner.sex ?? null,
          runner.sire ?? null,
          runner.dam ?? null,
          runner.claim ?? null,
          runner.last10 ?? null,
          runner.record ?? null,
          runner.prizeMoney ?? null,
          runner.puntingFormHorseId ?? null,
        );
      }
    }

    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }

  // Keep summary fields in sync for callers.
  meeting.raceCount = stats.raceCount;
  meeting.runnerCount = stats.runnerCount;
  meeting.resultsCount = stats.resultsCount;
  meeting.oddsCount = stats.oddsCount;
  meeting.importedAt = importedAt;
  meeting.updatedAt = updatedAt;
}

function seedIfEmpty(): void {
  if (process.env.RACEDNA_SEED === "0") return;

  const db = openDatabase();
  const count = db.prepare(`SELECT COUNT(*) AS c FROM meetings`).get() as { c: number };
  if (Number(count.c) > 0) return;

  const byMeeting = new Map<string, Race[]>();
  for (const race of structuredClone(seedRaces)) {
    const meetingId = race.meetingId;
    const list = byMeeting.get(meetingId) ?? [];
    list.push(race);
    byMeeting.set(meetingId, list);
  }

  for (const [meetingId, races] of byMeeting) {
    const sample = races[0];
    const now = nowIso();
    persistMeeting({
      id: meetingId,
      course: sample.course,
      date: sample.date,
      trackCondition: sample.going,
      source: "seed",
      raceCount: races.length,
      runnerCount: races.reduce((sum, race) => sum + race.runners.length, 0),
      resultsCount: 0,
      oddsCount: 0,
      importedAt: now,
      updatedAt: now,
      races,
    });
  }
}

export function initStore(): void {
  openDatabase();
  seedIfEmpty();
}

export function listMeetingSummaries(): MeetingSummary[] {
  initStore();
  const db = openDatabase();
  const rows = db
    .prepare(`SELECT * FROM meetings ORDER BY date DESC, course ASC`)
    .all() as Array<Record<string, unknown>>;

  return rows.map((row) => {
    const races = loadRacesForMeeting(
      String(row.id),
      String(row.course),
      row.date ? String(row.date) : undefined,
    );
    const stats = meetingStats(races);
    return {
      id: String(row.id),
      course: String(row.course),
      date: row.date ? String(row.date) : undefined,
      trackCondition: row.track_condition ? String(row.track_condition) : undefined,
      source: String(row.source),
      puntingFormMeetingId: row.punting_form_meeting_id
        ? String(row.punting_form_meeting_id)
        : undefined,
      importedAt: String(row.imported_at),
      updatedAt: String(row.updated_at),
      ...stats,
    };
  });
}

export function getMeeting(id: string): MeetingDetail | undefined {
  initStore();
  const db = openDatabase();
  const row = db.prepare(`SELECT * FROM meetings WHERE id = ?`).get(id) as
    | Record<string, unknown>
    | undefined;
  if (!row) return undefined;

  const races = loadRacesForMeeting(
    String(row.id),
    String(row.course),
    row.date ? String(row.date) : undefined,
  );
  const stats = meetingStats(races);

  return {
    id: String(row.id),
    course: String(row.course),
    date: row.date ? String(row.date) : undefined,
    trackCondition: row.track_condition ? String(row.track_condition) : undefined,
    source: String(row.source),
    puntingFormMeetingId: row.punting_form_meeting_id
      ? String(row.punting_form_meeting_id)
      : undefined,
    importedAt: String(row.imported_at),
    updatedAt: String(row.updated_at),
    ...stats,
    races,
  };
}

export function listRaces(): Race[] {
  return listMeetingSummaries().flatMap((summary) => getMeeting(summary.id)?.races ?? []);
}

export function getRace(id: string): Race | undefined {
  return listRaces().find((race) => race.id === id);
}

export function resetStore(): void {
  recreateDatabase();
  seedIfEmpty();
}

export function applyMeetingImport(csvText: string): ImportReport {
  initStore();
  const parsed = parseMeetingCsv(csvText);
  if (parsed.meeting.races.length === 0) return parsed.report;

  const existing = getMeeting(parsed.meeting.id);
  if (existing) {
    // Preserve odds/results already stored for exact TAB numbers.
    const priorByRaceTab = new Map<string, Horse>();
    for (const race of existing.races) {
      for (const runner of race.runners) {
        priorByRaceTab.set(`${race.raceNumber}:${runner.tabNumber}`, runner);
      }
    }
    parsed.meeting.races = parsed.meeting.races.map((race) => ({
      ...race,
      runners: race.runners.map((runner) => {
        const prior = priorByRaceTab.get(`${race.raceNumber}:${runner.tabNumber}`);
        if (!prior) return runner;
        return {
          ...runner,
          winOdds: prior.winOdds,
          placeOdds: prior.placeOdds,
          oddsSource: prior.oddsSource,
          finishPosition: prior.finishPosition,
        };
      }),
    }));
    persistMeeting(parsed.meeting, existing.importedAt);
  } else {
    persistMeeting(parsed.meeting);
  }

  return parsed.report;
}

function persistUpdatedMeetings(updatedRaces: Race[], meetingIds: string[]): void {
  const raceMap = new Map(updatedRaces.map((race) => [race.id, race]));
  for (const meetingId of meetingIds) {
    const existing = getMeeting(meetingId);
    if (!existing) continue;
    existing.races = existing.races.map((race) => raceMap.get(race.id) ?? race);
    persistMeeting(existing, existing.importedAt);
  }
}

export function applyResultsImport(csvText: string): ImportReport {
  initStore();
  const result = importResultsCsv(csvText, listRaces());
  persistUpdatedMeetings(result.races, result.affectedMeetingIds);
  return result.report;
}

export function applyOddsImport(csvText: string): ImportReport {
  initStore();
  const result = importOddsCsv(csvText, listRaces());
  persistUpdatedMeetings(result.races, result.affectedMeetingIds);
  return result.report;
}

export function getDashboard(): DashboardSummary {
  const meetings = listMeetingSummaries();
  const races = listRaces();

  let resultsImported = 0;
  let oddsImported = 0;
  for (const meeting of meetings) {
    resultsImported += meeting.resultsCount;
    oddsImported += meeting.oddsCount;
  }

  const topPicks = races.map((race) => {
    const analysis = analyzeRace(race);
    const top = analysis.runners[0];
    return {
      raceId: race.id,
      meetingId: race.meetingId,
      raceName: race.name,
      course: race.course,
      horseName: top?.name ?? "—",
      tabNumber: top?.tabNumber ?? 0,
      dnaScore: top?.dnaScore ?? 0,
      winProbability: top?.winProbability ?? 0,
    };
  });

  return {
    meetingCount: meetings.length,
    raceCount: races.length,
    runnerCount: races.reduce((sum, race) => sum + race.runners.length, 0),
    resultsImported,
    oddsImported,
    meetings,
    topPicks,
  };
}
