import type { Going, Horse, ImportReport, MeetingDetail, Race } from "../analysis/types.js";
import { normaliseDate, normaliseMeeting, slugify } from "../matching/matchHorses.js";
import {
  detectMeetingCsvFormat,
  getField,
  parseCsv,
  parseNumber,
  parseTabNumber,
} from "./csv.js";

interface FormHistoryEntry {
  meetingDate?: string;
  track?: string;
  trackCondition?: string;
  raceName?: string;
  distance?: string;
  className?: string;
  position?: number;
  margin?: string;
  price?: string;
  jockey?: string;
  barrier?: string;
  weight?: string;
  time?: string;
  otherRunners?: string;
}

interface AggregatedRunner {
  tabNumber: number;
  name: string;
  raceNumber: number;
  raceName: string;
  distance: number;
  meeting: string;
  date?: string;
  startTime?: string;
  meetingId?: string;
  className?: string;
  going?: Going;
  barrier?: number;
  weightKg?: number;
  jockey?: string;
  trainer?: string;
  claim?: number;
  age?: number;
  sex?: string;
  sire?: string;
  dam?: string;
  last10?: string;
  record?: string;
  prizeMoney?: string;
  horseId?: string;
  formHistory: FormHistoryEntry[];
  /** All source columns from the first/primary row for this horse. */
  extras: Record<string, string>;
}

function parseGoing(value: string): Going | undefined {
  const normalised = value.trim().toLowerCase();
  if (!normalised) return undefined;
  if (normalised.includes("heavy")) return "heavy";
  if (normalised.includes("soft") || normalised.includes("slow")) return "soft";
  if (normalised.includes("firm") || normalised.includes("good to firm")) return "firm";
  if (
    normalised.includes("good") ||
    normalised.includes("dead") ||
    normalised.includes("synthetic") ||
    normalised.includes("poly")
  ) {
    return "good";
  }
  return undefined;
}

function metersToFurlongs(meters: number): number {
  return Math.round((meters / 201.168) * 10) / 10;
}

/** Parse Last10 style strings such as 26825x1 into finish positions. */
function parseLast10(value: string): number[] {
  if (!value) return [];
  const cleaned = value.replace(/^'/, "").trim();
  const positions: number[] = [];
  for (const ch of cleaned) {
    if (ch >= "1" && ch <= "9") positions.push(Number(ch));
    else if (ch === "0") positions.push(10);
  }
  return positions.slice(0, 10);
}

function parseCareerFromRecord(record: string): { starts?: number; wins?: number } {
  // Formats like "6:1-2-0" => starts:6 wins:1
  const match = record.match(/^(\d+)\s*:\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)/);
  if (!match) return {};
  return { starts: Number(match[1]), wins: Number(match[2]) };
}

function isRepeatedHeaderRow(row: Record<string, string>): boolean {
  const raceNumber = getField(row, "race number", "RaceNumber", "Race Number");
  const horseNumber = getField(row, "horse number", "TabNo", "Tab Number");
  const horseName = getField(row, "horse name", "Horse Name", "Runner");
  return (
    raceNumber.toLowerCase() === "race number" ||
    horseNumber.toLowerCase() === "horse number" ||
    horseName.toLowerCase() === "horse name" ||
    getField(row, "track").toLowerCase() === "track"
  );
}

function extractFormEntry(row: Record<string, string>): FormHistoryEntry | null {
  const position = parseNumber(getField(row, "form position"));
  const meetingDate = getField(row, "form meeting date") || undefined;
  const track = getField(row, "form track") || undefined;
  if (position === undefined && !meetingDate && !track) return null;
  return {
    meetingDate,
    track,
    trackCondition: getField(row, "form track condition") || undefined,
    raceName: getField(row, "form name") || undefined,
    distance: getField(row, "form distance") || undefined,
    className: getField(row, "form class") || undefined,
    position,
    margin: getField(row, "form margin") || undefined,
    price: getField(row, "form price") || undefined,
    jockey: getField(row, "form jockey") || undefined,
    barrier: getField(row, "form barrier") || undefined,
    weight: getField(row, "form weight") || undefined,
    time: getField(row, "form time") || undefined,
    otherRunners: getField(row, "form other runners") || undefined,
  };
}

function recentFormFor(runner: AggregatedRunner): number[] {
  const fromLast10 = parseLast10(runner.last10 ?? "");
  if (fromLast10.length > 0) return fromLast10;

  const fromHistory = runner.formHistory
    .map((entry) => entry.position)
    .filter((value): value is number => value !== undefined && value > 0);
  return fromHistory.length > 0 ? fromHistory.slice(0, 10) : [5, 5, 5, 5];
}

function daysSinceLastRun(runner: AggregatedRunner): number {
  const meetingDate = normaliseDate(runner.date);
  const formDates = runner.formHistory
    .map((entry) => normaliseDate(entry.meetingDate))
    .filter((value): value is string => Boolean(value))
    .sort()
    .reverse();
  if (!meetingDate || formDates.length === 0) return 21;
  const last = Date.parse(formDates[0]);
  const meet = Date.parse(meetingDate);
  if (Number.isNaN(last) || Number.isNaN(meet)) return 21;
  return Math.max(0, Math.round((meet - last) / (1000 * 60 * 60 * 24)));
}

function toHorse(runner: AggregatedRunner, raceDistanceFurlongs: number): Horse {
  const career = parseCareerFromRecord(runner.record ?? "");
  const winRate =
    career.starts && career.wins !== undefined
      ? career.wins / Math.max(career.starts, 1)
      : 0.1;

  return {
    id: slugify(runner.meeting, runner.date, runner.raceNumber, runner.tabNumber, runner.name),
    tabNumber: runner.tabNumber,
    name: runner.name,
    recentForm: recentFormFor(runner),
    speedFigure: 80,
    optimalDistanceFurlongs: raceDistanceFurlongs,
    preferredGoing: runner.going ? [runner.going] : ["good"],
    classRating: 80,
    jockeyWinRate: Math.min(0.35, Math.max(0.05, winRate)),
    trainerWinRate: Math.min(0.35, Math.max(0.05, winRate * 0.9)),
    daysSinceLastRun: daysSinceLastRun(runner),
    barrier: runner.barrier,
    weightKg: runner.weightKg,
    jockey: runner.jockey,
    trainer: runner.trainer,
    age: runner.age,
    sex: runner.sex,
    sire: runner.sire,
    dam: runner.dam,
    claim: runner.claim,
    last10: runner.last10,
    record: runner.record,
    prizeMoney: runner.prizeMoney,
    puntingFormHorseId: runner.horseId,
    formHistory: runner.formHistory,
    extras: runner.extras,
  };
}

function accumulateRow(
  groups: Map<string, AggregatedRunner>,
  row: Record<string, string>,
): "ok" | "skip" {
  if (isRepeatedHeaderRow(row)) return "skip";

  const meeting = getField(row, "track", "Track", "TrackName", "Meeting", "Course", "Venue");
  const raceNumber = parseNumber(
    getField(row, "race number", "RaceNumber", "Race Number", "Race No", "RaceNo"),
  );
  // Real Punting Form uses "horse number" as the TAB / saddlecloth number.
  const tabNumber = parseTabNumber(
    getField(
      row,
      "horse number",
      "Horse Number",
      "TabNo",
      "Tab No",
      "TABNo",
      "Tab Number",
      "TAB Number",
      "TAB",
      "Cloth",
      "Saddlecloth",
      "RunnerNumber",
      "Runner Number",
    ),
  );
  const horse = getField(
    row,
    "horse name",
    "Horse Name",
    "Runner",
    "RunnerName",
    "Horse",
    "HorseName",
  );

  if (!meeting || raceNumber === undefined || tabNumber === undefined || !horse) {
    return "skip";
  }

  const key = `${normaliseMeeting(meeting)}::${raceNumber}::${tabNumber}`;
  const existing = groups.get(key);
  const formEntry = extractFormEntry(row);

  if (existing) {
    if (formEntry) existing.formHistory.push(formEntry);
    // Fill any blanks from later rows without overwriting established identity fields.
    existing.jockey ||= getField(row, "horse jockey", "Jockey") || undefined;
    existing.trainer ||= getField(row, "horse trainer", "Trainer") || undefined;
    existing.barrier ??= parseNumber(getField(row, "horse barrier", "Barrier", "BP"));
    existing.weightKg ??= parseNumber(getField(row, "horse weight", "Weight"));
    existing.last10 ||= getField(row, "horse last10", "Last10", "Last 10") || undefined;
    return "ok";
  }

  const going =
    parseGoing(getField(row, "form track condition")) ??
    parseGoing(getField(row, "ExpectedCondition", "TrackCondition", "Going", "Condition"));

  const distanceRaw =
    parseNumber(getField(row, "distance", "Distance", "Dist", "RaceDistance")) ?? 1200;

  groups.set(key, {
    tabNumber,
    name: horse,
    raceNumber,
    raceName:
      getField(row, "race name", "RaceName", "Race Name", "Race") || `Race ${raceNumber}`,
    distance: distanceRaw,
    meeting,
    date:
      normaliseDate(
        getField(row, "meeting date", "MeetingDate", "Meeting Date", "Date", "meetingDate"),
      ) ?? undefined,
    startTime: getField(row, "start time", "Start Time", "StartTime") || undefined,
    meetingId: getField(row, "meeting id", "MeetingId", "Meeting ID") || undefined,
    className:
      getField(row, "class restrictions", "RaceClass", "Class", "raceClass") || undefined,
    going,
    barrier: parseNumber(getField(row, "horse barrier", "Barrier", "BP")),
    weightKg: parseNumber(getField(row, "horse weight", "Weight")),
    jockey: getField(row, "horse jockey", "Jockey") || undefined,
    trainer: getField(row, "horse trainer", "Trainer") || undefined,
    claim: parseNumber(getField(row, "horse claim")),
    age: parseNumber(getField(row, "horse age")),
    sex: getField(row, "horse sex") || undefined,
    sire: getField(row, "horse sire") || undefined,
    dam: getField(row, "horse dam") || undefined,
    last10: getField(row, "horse last10", "Last10", "Last 10") || undefined,
    record: getField(row, "horse record") || undefined,
    prizeMoney: getField(row, "horse prize money", "prizemoney") || undefined,
    horseId: getField(row, "horse id") || undefined,
    formHistory: formEntry ? [formEntry] : [],
    extras: { ...row },
  });
  return "ok";
}

export interface MeetingImportResult {
  meeting: MeetingDetail;
  report: ImportReport;
  format: "punting-form" | "wizard" | "unknown";
}

/**
 * Parse a real Punting Form Meeting CSV (or Wizard-style CSV) into a MeetingDetail.
 *
 * Real PF exports are form-expanded: many rows per horse. We collapse by
 * (track, race number, horse number) and keep exact integer TAB numbers.
 */
export function parseMeetingCsv(csvText: string): MeetingImportResult {
  const { headers, rows } = parseCsv(csvText);
  const format = detectMeetingCsvFormat(headers);
  const groups = new Map<string, AggregatedRunner>();
  let skippedRows = 0;
  let parsedRows = 0;

  for (const row of rows) {
    const outcome = accumulateRow(groups, row);
    if (outcome === "ok") parsedRows += 1;
    else skippedRows += 1;
  }

  const aggregated = [...groups.values()];
  if (aggregated.length === 0) {
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
        runnersUnmatched: skippedRows,
        runnersCreated: 0,
        unmatched: [],
        message:
          "No valid meeting rows found. Expected Punting Form columns such as track, race number, horse number, horse name.",
      },
    };
  }

  const sample = aggregated[0];
  const pfMeetingId = sample.meetingId;
  const date = sample.date;
  const meetingId = pfMeetingId
    ? slugify("pf", pfMeetingId)
    : slugify(sample.meeting, date ?? "meeting");

  // One meeting file — keep only the primary track.
  const primaryTrack = normaliseMeeting(sample.meeting);
  const filtered = aggregated.filter(
    (runner) => normaliseMeeting(runner.meeting) === primaryTrack,
  );

  const raceGroups = new Map<number, AggregatedRunner[]>();
  for (const runner of filtered) {
    const list = raceGroups.get(runner.raceNumber) ?? [];
    list.push(runner);
    raceGroups.set(runner.raceNumber, list);
  }

  const races: Race[] = [];
  let runnersCreated = 0;

  for (const raceNumber of [...raceGroups.keys()].sort((a, b) => a - b)) {
    const group = raceGroups.get(raceNumber)!;
    const raceSample = group[0];
    const distanceMeters =
      raceSample.distance > 40 ? raceSample.distance : Math.round(raceSample.distance * 201.168);
    const distanceFurlongs =
      raceSample.distance > 40 ? metersToFurlongs(raceSample.distance) : raceSample.distance;

    // Exact integer map — TAB 1/10/11/12/13 never collide.
    const byTab = new Map<number, Horse>();
    for (const runner of group) {
      runnersCreated += 1;
      byTab.set(runner.tabNumber, toHorse(runner, distanceFurlongs));
    }

    const raceExtras: Record<string, string> = {};
    for (const key of [
      "age restrictions",
      "class restrictions",
      "weight restrictions",
      "race prizemoney",
      "sex restrictions",
      "weight type",
      "jockeys can claim",
      "race id",
    ]) {
      const value = raceSample.extras[key];
      if (value) raceExtras[key] = value;
    }

    races.push({
      id: slugify(meetingId, `r${raceNumber}`),
      meetingId,
      name: raceSample.raceName,
      course: sample.meeting,
      date,
      raceNumber,
      startTime: raceSample.startTime,
      distanceFurlongs,
      distanceMeters: Math.round(distanceMeters),
      going: raceSample.going ?? "good",
      className: raceSample.className,
      extras: raceExtras,
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
      rowsParsed: parsedRows,
      racesAffected: races.length,
      runnersMatched: 0,
      runnersUnmatched: skippedRows,
      runnersCreated,
      unmatched: [],
      message: `Imported ${runnersCreated} runners across ${races.length} race(s) for ${sample.meeting}${date ? ` (${date})` : ""} [${format}]. Skipped ${skippedRows} non-runner row(s) (form repeats / header echoes).`,
    },
  };
}

/** @deprecated Prefer parseMeetingCsv + store.saveMeeting */
export function importMeetingCsv(csvText: string): {
  races: Race[];
  report: ImportReport;
} {
  const result = parseMeetingCsv(csvText);
  return { races: result.meeting.races, report: result.report };
}
