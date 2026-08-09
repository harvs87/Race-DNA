import type { Horse, Race } from "../analysis/types.js";

export interface MatchKey {
  meeting: string;
  meetingDate?: string;
  puntingFormMeetingId?: string;
  raceNumber: number;
  tabNumber: number;
  horseName?: string;
}

export interface MatchResult {
  race: Race;
  horse: Horse;
  method: "tab";
}

/** Normalise meeting / course names for exact comparison. */
export function normaliseMeeting(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Normalise ISO-ish dates to YYYY-MM-DD when possible. */
export function normaliseDate(value?: string): string | undefined {
  if (!value) return undefined;
  const trimmed = value.trim();
  const iso = trimmed.match(/^(\d{4}-\d{2}-\d{2})/);
  if (iso) return iso[1];
  const dmy = trimmed.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
  if (dmy) {
    return `${dmy[3]}-${dmy[2].padStart(2, "0")}-${dmy[1].padStart(2, "0")}`;
  }
  const parsed = Date.parse(trimmed);
  if (!Number.isNaN(parsed)) return new Date(parsed).toISOString().slice(0, 10);
  return undefined;
}

/**
 * Exact TAB-number equality.
 *
 * IMPORTANT: Never match TAB numbers with string prefix/includes checks.
 * Those incorrectly treat "1" as a match for "10", "11", "12" or "13".
 */
export function tabNumbersEqual(a: number | string, b: number | string): boolean {
  const left = typeof a === "number" ? a : Number(String(a).trim());
  const right = typeof b === "number" ? b : Number(String(b).trim());
  if (!Number.isInteger(left) || !Number.isInteger(right)) return false;
  if (left <= 0 || right <= 0) return false;
  return left === right;
}

/** Exact race-number equality (no string/partial matching). */
export function raceNumbersEqual(a: number | string, b: number | string): boolean {
  const left = typeof a === "number" ? a : Number(String(a).trim());
  const right = typeof b === "number" ? b : Number(String(b).trim());
  if (!Number.isInteger(left) || !Number.isInteger(right)) return false;
  if (left <= 0 || right <= 0) return false;
  return left === right;
}

export function meetingsEqual(a: string, b: string): boolean {
  return normaliseMeeting(a) === normaliseMeeting(b);
}

export function raceMatchesMeeting(
  race: Race,
  meeting: string,
  raceNumber: number,
  meetingDate?: string,
  puntingFormMeetingId?: string,
): boolean {
  if (!raceNumbersEqual(race.raceNumber, raceNumber)) return false;

  if (puntingFormMeetingId && race.meetingId.includes(puntingFormMeetingId)) {
    // meetingId may be `pf-<id>` or the raw id; exact token match below is safer.
  }

  if (meetingDate) {
    const targetDate = normaliseDate(meetingDate);
    const raceDate = normaliseDate(race.date);
    if (targetDate && raceDate && targetDate !== raceDate) return false;
  }

  return meetingsEqual(race.course, meeting);
}

export function findRace(
  races: Race[],
  meeting: string,
  raceNumber: number,
  meetingDate?: string,
): Race | undefined {
  return races.find((race) => raceMatchesMeeting(race, meeting, raceNumber, meetingDate));
}

/**
 * Match a row to a runner using race number AND exact TAB number only.
 * Never uses partial string matching on TAB numbers or horse names.
 */
export function matchRunner(races: Race[], key: MatchKey): MatchResult | undefined {
  const race = findRace(races, key.meeting, key.raceNumber, key.meetingDate);
  if (!race) return undefined;

  const byTab = race.runners.find((runner) => tabNumbersEqual(runner.tabNumber, key.tabNumber));
  if (!byTab) return undefined;

  return { race, horse: byTab, method: "tab" };
}

export function slugify(...parts: Array<string | number | undefined>): string {
  return parts
    .filter((part) => part !== undefined && part !== "")
    .map((part) =>
      String(part)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, ""),
    )
    .filter(Boolean)
    .join("-");
}
