import type { DashboardSummary, ImportReport, Race } from "../analysis/types.js";
import { analyzeRace } from "../analysis/engine.js";
import { importMeetingCsv } from "../import/meetingCsv.js";
import { importOddsCsv } from "../import/oddsCsv.js";
import { importResultsCsv } from "../import/resultsCsv.js";
import { seedRaces } from "./races.js";

let races: Race[] = structuredClone(seedRaces);

export function listRaces(): Race[] {
  return races;
}

export function getRace(id: string): Race | undefined {
  return races.find((race) => race.id === id);
}

export function resetStore(): void {
  races = structuredClone(seedRaces);
}

export function applyMeetingImport(csvText: string): ImportReport {
  const result = importMeetingCsv(csvText, races);
  races = result.races;
  return result.report;
}

export function applyResultsImport(csvText: string): ImportReport {
  const result = importResultsCsv(csvText, races);
  races = result.races;
  return result.report;
}

export function applyOddsImport(csvText: string): ImportReport {
  const result = importOddsCsv(csvText, races);
  races = result.races;
  return result.report;
}

export function getDashboard(): DashboardSummary {
  const meetings = new Map<
    string,
    { course: string; date?: string; raceCount: number; runnerCount: number }
  >();

  let resultsImported = 0;
  let oddsImported = 0;

  for (const race of races) {
    const key = `${race.course}::${race.date ?? ""}`;
    const existing = meetings.get(key) ?? {
      course: race.course,
      date: race.date,
      raceCount: 0,
      runnerCount: 0,
    };
    existing.raceCount += 1;
    existing.runnerCount += race.runners.length;
    meetings.set(key, existing);

    for (const runner of race.runners) {
      if (runner.finishPosition !== undefined) resultsImported += 1;
      if (runner.winOdds !== undefined) oddsImported += 1;
    }
  }

  const topPicks = races.map((race) => {
    const analysis = analyzeRace(race);
    const top = analysis.runners[0];
    return {
      raceId: race.id,
      raceName: race.name,
      course: race.course,
      horseName: top?.name ?? "—",
      tabNumber: top?.tabNumber ?? 0,
      dnaScore: top?.dnaScore ?? 0,
      winProbability: top?.winProbability ?? 0,
    };
  });

  return {
    meetingCount: meetings.size,
    raceCount: races.length,
    runnerCount: races.reduce((sum, race) => sum + race.runners.length, 0),
    resultsImported,
    oddsImported,
    meetings: [...meetings.values()],
    topPicks,
  };
}
