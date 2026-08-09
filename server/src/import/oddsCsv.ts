import type { ImportReport, Race } from "../analysis/types.js";
import { matchRunner } from "../matching/matchHorses.js";
import { getField, parseCsv, parseNumber, parseTabNumber } from "./csv.js";

/**
 * Import TAB / TABtouch odds and attach them to matched runners.
 * Matching uses exact TAB numbers so runner 1 never consumes odds for 10 or 13.
 */
export function importOddsCsv(csvText: string, races: Race[]): {
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
    const winOdds = parseNumber(getField(row, "Win Odds", "Win", "Fixed Win", "Odds"));
    const placeOdds = parseNumber(getField(row, "Place Odds", "Place", "Fixed Place"));
    const source =
      getField(row, "Source", "Bookmaker", "Agency") ||
      (getField(row, "TABtouch") ? "TABtouch" : "TAB");

    if (!meeting || raceNumber === undefined || tabNumber === undefined || winOdds === undefined) {
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

    matched.horse.winOdds = winOdds;
    if (placeOdds !== undefined) matched.horse.placeOdds = placeOdds;
    matched.horse.oddsSource = source;
    runnersMatched += 1;
    affected.add(matched.race.id);
  }

  return {
    races: next,
    report: {
      kind: "odds",
      rowsParsed,
      racesAffected: affected.size,
      runnersMatched,
      runnersUnmatched: unmatched.length,
      runnersCreated: 0,
      unmatched,
      message: `Matched ${runnersMatched} odds row(s); ${unmatched.length} unmatched.`,
    },
  };
}
