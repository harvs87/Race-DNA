import type { Horse, Race } from "../analysis/types.js";

export interface MatchKey {
  meeting: string;
  raceNumber: number;
  tabNumber: number;
  horseName?: string;
}

export interface MatchResult {
  race: Race;
  horse: Horse;
  method: "tab" | "name";
}

/** Normalise meeting / course names for comparison. */
export function normaliseMeeting(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}

/** Normalise horse names for fallback matching. */
export function normaliseHorseName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[''`]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Exact TAB-number equality.
 *
 * IMPORTANT: Never match TAB numbers with string prefix/includes checks.
 * Those incorrectly treat "1" as a match for "10" or "13".
 */
export function tabNumbersEqual(a: number | string, b: number | string): boolean {
  const left = typeof a === "number" ? a : Number(String(a).trim());
  const right = typeof b === "number" ? b : Number(String(b).trim());
  if (!Number.isInteger(left) || !Number.isInteger(right)) return false;
  if (left <= 0 || right <= 0) return false;
  return left === right;
}

export function raceMatchesMeeting(race: Race, meeting: string, raceNumber: number): boolean {
  if (race.raceNumber !== raceNumber) return false;
  const target = normaliseMeeting(meeting);
  const course = normaliseMeeting(race.course);
  return course === target || course.includes(target) || target.includes(course);
}

export function findRace(
  races: Race[],
  meeting: string,
  raceNumber: number,
): Race | undefined {
  return races.find((race) => raceMatchesMeeting(race, meeting, raceNumber));
}

/**
 * Match a row to a runner. Prefers exact TAB number within the race,
 * then falls back to normalised horse name.
 */
export function matchRunner(
  races: Race[],
  key: MatchKey,
): MatchResult | undefined {
  const race = findRace(races, key.meeting, key.raceNumber);
  if (!race) return undefined;

  const byTab = race.runners.find((runner) => tabNumbersEqual(runner.tabNumber, key.tabNumber));
  if (byTab) {
    return { race, horse: byTab, method: "tab" };
  }

  if (key.horseName) {
    const target = normaliseHorseName(key.horseName);
    const byName = race.runners.find(
      (runner) => normaliseHorseName(runner.name) === target,
    );
    if (byName) {
      return { race, horse: byName, method: "name" };
    }
  }

  return undefined;
}

export function slugify(...parts: Array<string | number>): string {
  return parts
    .map((part) =>
      String(part)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, ""),
    )
    .filter(Boolean)
    .join("-");
}
