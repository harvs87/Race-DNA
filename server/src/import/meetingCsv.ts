import type { Going, Horse, ImportReport, MeetingDetail, Race } from "../analysis/types.js";
import { normaliseDate, normaliseMeeting, slugify } from "../matching/matchHorses.js";
import {
  detectMeetingCsvFormat,
  getField,
  parseCsv,
  parseNumber,
  parseTabNumber,
} from "./csv.js";

interface MeetingRow {
  meetingId?: string;
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
  speedFigure?: number;
  classRating?: number;
  daysSinceLastStart?: number;
  trainer?: string;
  jockey?: string;
  careerStarts?: number;
  careerWins?: number;
  scratched?: boolean;
}

function parseGoing(value: string): Going | undefined {
  const normalised = value.trim().toLowerCase();
  if (!normalised) return undefined;
  if (normalised.includes("heavy")) return "heavy";
  if (normalised.includes("soft") || normalised.includes("slow")) return "soft";
  if (normalised.includes("firm") || normalised.includes("good to firm")) return "firm";
  if (normalised.includes("good") || normalised.includes("dead") || normalised.includes("synthetic")) {
    return "good";
  }
  return undefined;
}

function metersToFurlongs(meters: number): number {
  return Math.round((meters / 201.168) * 10) / 10;
}

/** Parse Last10 style strings such as 5x1149x21409 into finish positions. */
function parseLast10(value: string): number[] {
  if (!value) return [];
  const cleaned = value.replace(/^'/, "").trim();
  const positions: number[] = [];
  for (const ch of cleaned) {
    if (ch >= "1" && ch <= "9") positions.push(Number(ch));
    // 0 often means 10th+; keep as 10 for scoring softness.
    else if (ch === "0") positions.push(10);
  }
  return positions.slice(0, 8);
}

function parseForm(row: Record<string, string>): number[] {
  const last10 = parseLast10(getField(row, "Last10", "Last 10", "FormFigures"));
  if (last10.length > 0) return last10;

  const discrete = [
    getField(row, "Last Finish pos", "Last Finish Pos", "LastFinishPos", "Position"),
    getField(row, "Last-1 Finish pos", "Last-1 Finish Pos"),
    getField(row, "Last-2 Finish pos", "Last-2 Finish Pos"),
    getField(row, "Last-3 Finish pos", "Last-3 Finish Pos"),
  ]
    .map((value) => parseNumber(value))
    .filter((value): value is number => value !== undefined && value > 0);

  if (discrete.length > 0) return discrete;

  return parseLast10(getField(row, "Form"));
}

function parseRaceNumber(row: Record<string, string>): number | undefined {
  return parseNumber(
    getField(row, "RaceNumber", "Race Number", "Race No", "RaceNo", "raceNumber", "Number"),
  );
}

function parseTabFromRow(row: Record<string, string>): number | undefined {
  // Prefer explicit TAB columns. Never fall back to bare "Number" (race number in PF CSVs).
  return parseTabNumber(
    getField(
      row,
      "TabNo",
      "Tab No",
      "TABNo",
      "TAB No",
      "Tab Number",
      "TAB Number",
      "TAB",
      "Cloth",
      "Saddlecloth",
      "RunnerNumber",
      "Runner Number",
    ),
  );
}

function parseMeetingName(row: Record<string, string>): string {
  return (
    getField(row, "Track", "TrackName", "Track Name", "Meeting", "Course", "Venue") ||
    getField(row, "track.name")
  );
}

function parseHorseName(row: Record<string, string>): string {
  return getField(row, "Runner", "RunnerName", "Horse", "Horse Name", "Name", "HorseName");
}

function rowToMeeting(row: Record<string, string>): MeetingRow | null {
  const meeting = parseMeetingName(row);
  const raceNumber = parseRaceNumber(row);
  const tabNumber = parseTabFromRow(row);
  const horse = parseHorseName(row);
  if (!meeting || raceNumber === undefined || tabNumber === undefined || !horse) {
    return null;
  }

  // If Name was used for horse and equals race name column collision, require Runner/Horse.
  const raceName =
    getField(row, "RaceName", "Race Name", "Race") ||
    (getField(row, "Name") && getField(row, "Name") !== horse ? getField(row, "Name") : "") ||
    `Race ${raceNumber}`;

  const distanceRaw =
    parseNumber(getField(row, "Distance", "Dist", "RaceDistance", "Race Distance")) ?? 1200;
  const careerStarts = parseNumber(
    getField(row, "CareerStarts", "Career Starts", "Starts"),
  );
  const careerWins = parseNumber(getField(row, "CareerWins", "Career Wins", "Wins"));
  const scratchedRaw = getField(row, "Scratched", "IsScratched", "Emergency").toLowerCase();
  const scratched =
    scratchedRaw === "scratched" ||
    scratchedRaw === "true" ||
    scratchedRaw === "1" ||
    scratchedRaw === "yes";

  const date =
    normaliseDate(
      getField(row, "MeetingDate", "Meeting Date", "Date", "meetingDate", "RaceDate"),
    ) ?? undefined;

  const speedFigure =
    parseNumber(getField(row, "PFRating", "PfRating", "Rating", "Wrat", "WRAT", "SpeedFigure")) ??
    parseNumber(getField(row, "HandicapRating", "Handicap Rating"));

  const classRating =
    parseNumber(getField(row, "HandicapRating", "Handicap Rating", "Trat", "TRAT", "ClassRating")) ??
    speedFigure;

  return {
    meetingId: getField(row, "MeetingId", "Meeting ID", "meetingId") || undefined,
    meeting,
    raceNumber,
    raceName: raceName || `Race ${raceNumber}`,
    distance: distanceRaw,
    date,
    className: getField(row, "RaceClass", "Class", "raceClass") || undefined,
    going: parseGoing(
      getField(row, "ExpectedCondition", "TrackCondition", "Going", "Condition", "Track Condition"),
    ),
    tabNumber,
    horse,
    form: parseForm(row),
    barrier: parseNumber(getField(row, "Barrier", "BP", "Barrier Position")),
    weightKg: parseNumber(getField(row, "Weight")),
    speedFigure,
    classRating,
    daysSinceLastStart: parseNumber(
      getField(
        row,
        "DaysSinceLastRun",
        "Days Since Last Run",
        "Days Since Last Start",
        "DaysSinceLastStart",
      ),
    ),
    trainer: getField(row, "Trainer", "TrainerName", "trainer.name") || undefined,
    jockey: getField(row, "Jockey", "JockeyName", "jockey.name") || undefined,
    careerStarts,
    careerWins,
    scratched,
  };
}

function toHorse(row: MeetingRow, raceDistanceFurlongs: number): Horse {
  const winRate =
    row.careerStarts && row.careerWins !== undefined
      ? row.careerWins / Math.max(row.careerStarts, 1)
      : 0.1;

  const speedFigure = row.speedFigure ?? 80;
  const classRating = row.classRating ?? speedFigure;

  return {
    id: slugify(row.meeting, row.date, row.raceNumber, row.tabNumber, row.horse),
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

export interface MeetingImportResult {
  meeting: MeetingDetail;
  report: ImportReport;
  format: "punting-form" | "wizard" | "unknown";
}

/**
 * Parse a Punting Form Meeting CSV (preferred) or Wizard-style meeting CSV
 * into a MeetingDetail. TAB numbers are preserved exactly as integers.
 */
export function parseMeetingCsv(csvText: string): MeetingImportResult {
  const { headers, rows } = parseCsv(csvText);
  const format = detectMeetingCsvFormat(headers);
  const parsed = rows.map(rowToMeeting).filter((row): row is MeetingRow => row !== null);

  if (parsed.length === 0) {
    const emptyId = "empty-meeting";
    return {
      format,
      meeting: {
        id: emptyId,
        course: "Unknown",
        source: format,
        raceCount: 0,
        runnerCount: 0,
        resultsCount: 0,
        oddsCount: 0,
        importedAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        races: [],
      },
      report: {
        kind: "meeting",
        rowsParsed: 0,
        racesAffected: 0,
        runnersMatched: 0,
        runnersUnmatched: 0,
        runnersCreated: 0,
        unmatched: [],
        message: "No valid meeting rows found. Expected Punting Form columns such as Track, RaceNumber, TabNo, Runner.",
      },
    };
  }

  const sample = parsed[0];
  const pfMeetingId = sample.meetingId;
  const date = sample.date;
  const meetingId = pfMeetingId
    ? slugify("pf", pfMeetingId)
    : slugify(sample.meeting, date ?? "meeting");

  const groups = new Map<number, MeetingRow[]>();
  for (const row of parsed) {
    // One CSV file = one meeting. Guard against accidental multi-track mixes
    // by only accepting rows for the same normalised meeting name.
    if (normaliseMeeting(row.meeting) !== normaliseMeeting(sample.meeting)) continue;
    const list = groups.get(row.raceNumber) ?? [];
    list.push(row);
    groups.set(row.raceNumber, list);
  }

  let runnersCreated = 0;
  const races: Race[] = [];

  for (const [raceNumber, group] of [...groups.entries()].sort((a, b) => a[0] - b[0])) {
    const raceSample = group[0];
    const distanceMeters =
      raceSample.distance > 40 ? raceSample.distance : Math.round(raceSample.distance * 201.168);
    const distanceFurlongs =
      raceSample.distance > 40 ? metersToFurlongs(raceSample.distance) : raceSample.distance;

    const byTab = new Map<number, Horse>();
    for (const row of group) {
      runnersCreated += 1;
      // Exact integer map key — 1, 10, 11, 12, 13 are distinct.
      byTab.set(row.tabNumber, toHorse(row, distanceFurlongs));
    }

    races.push({
      id: slugify(meetingId, `r${raceNumber}`),
      meetingId,
      name: raceSample.raceName,
      course: sample.meeting,
      date,
      raceNumber,
      distanceFurlongs,
      distanceMeters: Math.round(distanceMeters),
      going: raceSample.going ?? sample.going ?? "good",
      className: raceSample.className,
      runners: [...byTab.values()].sort((a, b) => a.tabNumber - b.tabNumber),
    });
  }

  const now = new Date().toISOString();
  const meeting: MeetingDetail = {
    id: meetingId,
    course: sample.meeting,
    date,
    trackCondition: sample.going,
    source: format === "unknown" ? "import" : format,
    puntingFormMeetingId: pfMeetingId,
    raceCount: races.length,
    runnerCount: runnersCreated,
    resultsCount: 0,
    oddsCount: 0,
    importedAt: now,
    updatedAt: now,
    races,
  };

  return {
    format,
    meeting,
    report: {
      kind: "meeting",
      meetingId,
      rowsParsed: parsed.length,
      racesAffected: races.length,
      runnersMatched: 0,
      runnersUnmatched: 0,
      runnersCreated,
      unmatched: [],
      message: `Imported ${runnersCreated} runners across ${races.length} race(s) for ${sample.meeting}${date ? ` (${date})` : ""} [${format}].`,
    },
  };
}

/** @deprecated Prefer parseMeetingCsv + store.saveMeeting */
export function importMeetingCsv(csvText: string, _races: Race[] = []): {
  races: Race[];
  report: ImportReport;
} {
  const result = parseMeetingCsv(csvText);
  return { races: result.meeting.races, report: result.report };
}
