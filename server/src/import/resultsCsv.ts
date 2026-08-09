import type { ImportReport, Race } from "../analysis/types.js";
import { matchRunner } from "../matching/matchHorses.js";
import { getField, parseCsv, parseNumber, parseTabNumber } from "./csv.js";

/**
 * Import race results and attach finish positions to matched runners.
 * Matching uses exact TAB numbers within meeting + race number.
 */
export function importResultsCsv(csvText: string, races: Race[]): {
  races: Race[];
  report: ImportReport;
} {
  const { rows } = parseCsv(csvText);
  const next = races.map((race) => ({
    ...race,
    runners: race.runners.map((runner) => ({ ...runner })),
  }));

  let runnersMatched = 0;
  const unmatched: ImportReport["unmatched"] = [];
  const affected = new Set<string>();
  let rowsParsed = 0;

  for (const row of rows) {
    const meeting = getField(row, "Meeting", "Course", "Track");
    const raceNumber = parseNumber(getField(row, "Race Number", "Race", "Race No", "RaceNo"));
    const tabNumber = parseTabNumber(getField(row, "Tab Number", "TAB", "Tab", "Number", "No"));
    const horse = getField(row, "Horse", "Horse Name", "Runner") || undefined;
    const finishPosition = parseNumber(
      getField(row, "Finish Position", "Finish", "Position", "FinPos", "Place"),
    );

    if (!meeting || raceNumber === undefined || tabNumber === undefined || finishPosition === undefined) {
      continue;
    }
    rowsParsed += 1;

    const matched = matchRunner(next, {
      meeting,
      raceNumber,
      tabNumber,
      horseName: horse,
    });

    if (!matched) {
      unmatched.push({
        meeting,
        raceNumber,
        tabNumber,
        horse,
        reason: "No runner matched for meeting/race/TAB number",
      });
      continue;
    }

    matched.horse.finishPosition = finishPosition;
    runnersMatched += 1;
    affected.add(matched.race.id);
  }

  return {
    races: next,
    report: {
      kind: "results",
      rowsParsed,
      racesAffected: affected.size,
      runnersMatched,
      runnersUnmatched: unmatched.length,
      runnersCreated: 0,
      unmatched,
      message: `Matched ${runnersMatched} result(s); ${unmatched.length} unmatched.`,
    },
  };
}
