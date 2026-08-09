import type { Going, Horse, ImportReport, Race } from "../analysis/types.js";
import { findRace, normaliseMeeting, slugify } from "../matching/matchHorses.js";
import { getField, parseCsv, parseNumber, parseTabNumber } from "./csv.js";

interface MeetingRow {
  meeting: string;
  raceNumber: number;
  raceName: string;
  distance: number;
  date?: string;
  className?: string;
  going?: Going;
  tabNumber: number;
  horse: string;
  form: number[];
  barrier?: number;
  weightKg?: number;
  wrat?: number;
  trat?: number;
  daysSinceLastStart?: number;
  trainer?: string;
  jockey?: string;
  winPct?: number;
  starts?: number;
  wins?: number;
  scratched?: boolean;
}

function parseForm(row: Record<string, string>): number[] {
  const discrete = [
    getField(row, "Last Finish pos", "Last Finish Pos", "LastFinishPos"),
    getField(row, "Last-1 Finish pos", "Last-1 Finish Pos"),
    getField(row, "Last-2 Finish pos", "Last-2 Finish Pos"),
    getField(row, "Last-3 Finish pos", "Last-3 Finish Pos"),
  ]
    .map((value) => parseNumber(value))
    .filter((value): value is number => value !== undefined && value > 0);

  if (discrete.length > 0) return discrete;

  const raw = getField(row, "Form").replace(/^'/, "");
  return raw
    .split("")
    .map((ch) => Number(ch))
    .filter((n) => Number.isInteger(n) && n > 0);
}

function parseGoing(value: string): Going | undefined {
  const normalised = value.trim().toLowerCase();
  if (!normalised) return undefined;
  if (normalised.includes("heavy")) return "heavy";
  if (normalised.includes("soft") || normalised.includes("slow")) return "soft";
  if (normalised.includes("firm") || normalised.includes("good to firm")) return "firm";
  if (normalised.includes("good") || normalised.includes("dead")) return "good";
  return undefined;
}

function metersToFurlongs(meters: number): number {
  return Math.round((meters / 201.168) * 10) / 10;
}

function rowToMeeting(row: Record<string, string>): MeetingRow | null {
  const meeting = getField(row, "Meeting", "Course", "Track");
  const raceNumber = parseNumber(getField(row, "Race Number", "Race", "Race No", "RaceNo"));
  const tabNumber = parseTabNumber(getField(row, "Tab Number", "TAB", "Tab", "Number", "No"));
  const horse = getField(row, "Horse", "Horse Name", "Runner");
  if (!meeting || raceNumber === undefined || tabNumber === undefined || !horse) {
    return null;
  }

  const distanceRaw = parseNumber(getField(row, "Distance", "Dist")) ?? 1200;
  const starts = parseNumber(getField(row, "Starts"));
  const wins = parseNumber(getField(row, "Wins"));
  const winPct = parseNumber(getField(row, "win%", "Win%", "Win Percent"));
  const scratched = getField(row, "Scratched").toLowerCase() === "scratched";

  return {
    meeting,
    raceNumber,
    raceName: getField(row, "Race Name", "RaceName") || `Race ${raceNumber}`,
    distance: distanceRaw,
    date: getField(row, "Date") || undefined,
    className: getField(row, "Class") || undefined,
    going: parseGoing(getField(row, "Going", "Track Condition", "Condition")),
    tabNumber,
    horse,
    form: parseForm(row),
    barrier: parseNumber(getField(row, "BP", "Barrier", "Barrier Position")),
    weightKg: parseNumber(getField(row, "Weight")),
    wrat: parseNumber(getField(row, "Wrat", "WRAT")),
    trat: parseNumber(getField(row, "Trat", "TRAT")),
    daysSinceLastStart: parseNumber(
      getField(row, "Days Since Last Start", "Days Since Last Run", "DaysSinceLastStart"),
    ),
    trainer: getField(row, "Trainer") || undefined,
    jockey: getField(row, "Jockey") || undefined,
    winPct,
    starts,
    wins,
    scratched,
  };
}

function toHorse(row: MeetingRow, raceDistanceFurlongs: number): Horse {
  const winRate =
    row.winPct !== undefined
      ? row.winPct > 1
        ? row.winPct / 100
        : row.winPct
      : row.starts && row.wins !== undefined
        ? row.wins / Math.max(row.starts, 1)
        : 0.1;

  const speedFigure = row.wrat ?? 80;
  const classRating = row.trat ?? speedFigure;

  return {
    id: slugify(row.meeting, row.raceNumber, row.tabNumber, row.horse),
    tabNumber: row.tabNumber,
    name: row.horse,
    recentForm: row.form.length > 0 ? row.form : [5, 5, 5, 5],
    speedFigure,
    optimalDistanceFurlongs: raceDistanceFurlongs,
    preferredGoing: row.going ? [row.going] : ["good"],
    classRating,
    jockeyWinRate: Math.min(0.35, Math.max(0.05, winRate)),
    trainerWinRate: Math.min(0.35, Math.max(0.05, winRate * 0.9)),
    daysSinceLastRun: row.daysSinceLastStart ?? 21,
    barrier: row.barrier,
    weightKg: row.weightKg,
    jockey: row.jockey,
    trainer: row.trainer,
    scratched: row.scratched,
  };
}

/**
 * Import a Wizard-style meeting CSV into the race list.
 * Existing races for the same meeting + race number are replaced.
 */
export function importMeetingCsv(csvText: string, races: Race[]): {
  races: Race[];
  report: ImportReport;
} {
  const { rows } = parseCsv(csvText);
  const parsed = rows.map(rowToMeeting).filter((row): row is MeetingRow => row !== null);

  const next = [...races];
  const groups = new Map<string, MeetingRow[]>();

  for (const row of parsed) {
    const key = `${normaliseMeeting(row.meeting)}::${row.raceNumber}`;
    const list = groups.get(key) ?? [];
    list.push(row);
    groups.set(key, list);
  }

  let runnersCreated = 0;
  let racesAffected = 0;

  for (const group of groups.values()) {
    const sample = group[0];
    const distanceMeters = sample.distance > 40 ? sample.distance : sample.distance * 201.168;
    const distanceFurlongs =
      sample.distance > 40 ? metersToFurlongs(sample.distance) : sample.distance;

    const raceId = slugify(sample.meeting, sample.date ?? "meeting", `r${sample.raceNumber}`);
    const runners = group.map((row) => {
      runnersCreated += 1;
      return toHorse(row, distanceFurlongs);
    });

    // Deduplicate by exact TAB number (keeps last occurrence).
    const byTab = new Map<number, Horse>();
    for (const runner of runners) {
      byTab.set(runner.tabNumber, runner);
    }

    const race: Race = {
      id: raceId,
      name: sample.raceName,
      course: sample.meeting,
      date: sample.date,
      raceNumber: sample.raceNumber,
      distanceFurlongs,
      distanceMeters: Math.round(distanceMeters),
      going: sample.going ?? "good",
      className: sample.className,
      runners: [...byTab.values()].sort((a, b) => a.tabNumber - b.tabNumber),
    };

    const existingIndex = next.findIndex(
      (item) => findRace([item], sample.meeting, sample.raceNumber) !== undefined,
    );
    if (existingIndex >= 0) {
      // Preserve odds/results already imported onto matching TAB numbers.
      const previous = next[existingIndex];
      race.runners = race.runners.map((runner) => {
        const prior = previous.runners.find((item) => item.tabNumber === runner.tabNumber);
        if (!prior) return runner;
        return {
          ...runner,
          winOdds: prior.winOdds,
          placeOdds: prior.placeOdds,
          oddsSource: prior.oddsSource,
          finishPosition: prior.finishPosition,
        };
      });
      next[existingIndex] = race;
    } else {
      next.push(race);
    }
    racesAffected += 1;
  }

  return {
    races: next,
    report: {
      kind: "meeting",
      rowsParsed: parsed.length,
      racesAffected,
      runnersMatched: 0,
      runnersUnmatched: 0,
      runnersCreated,
      unmatched: [],
      message: `Imported ${runnersCreated} runners across ${racesAffected} race(s).`,
    },
  };
}
