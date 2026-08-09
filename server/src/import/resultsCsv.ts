import type { ImportReport, Race } from "../analysis/types.js";
import { matchRunner, normaliseDate } from "../matching/matchHorses.js";
import { getField, parseCsv, parseNumber, parseTabNumber } from "./csv.js";

/**
 * Import race results and attach finish positions to matched runners.
 *
 * Matching rules (strict):
 * - meeting name (exact normalised) + optional date
 * - race number (exact integer)
 * - TAB / runner number (exact integer)
 *
 * Never uses partial string matching on TAB numbers.
 */
export function importResultsCsv(csvText: string, races: Race[]): {
  races: Race[];
  report: ImportReport;
  affectedMeetingIds: string[];
} {
  const { rows } = parseCsv(csvText);
  const next = races.map((race) => ({
    ...race,
    runners: race.runners.map((runner) => ({ ...runner })),
  }));

  let runnersMatched = 0;
  const unmatched: ImportReport["unmatched"] = [];
  const affected = new Set<string>();
  const meetingIds = new Set<string>();
  let rowsParsed = 0;

  for (const row of rows) {
    const meeting = getField(row, "Track", "TrackName", "Meeting", "Course", "Venue");
    const meetingDate = normaliseDate(
      getField(row, "MeetingDate", "Meeting Date", "Date", "meetingDate"),
    );
    const raceNumber = parseNumber(
      getField(row, "RaceNumber", "Race Number", "Race No", "RaceNo", "Number"),
    );
    const tabNumber = parseTabNumber(
      getField(
        row,
        "TabNo",
        "Tab No",
        "TABNo",
        "Tab Number",
        "TAB Number",
        "TAB",
        "Cloth",
        "RunnerNumber",
      ),
    );
    const horse = getField(row, "Runner", "RunnerName", "Horse", "Horse Name", "Name") || undefined;
    const finishPosition = parseNumber(
      getField(row, "Position", "Finish Position", "Finish", "FinPos", "Place", "FinishPos"),
    );

    if (!meeting || raceNumber === undefined || tabNumber === undefined || finishPosition === undefined) {
      continue;
    }
    rowsParsed += 1;

    const matched = matchRunner(next, {
      meeting,
      meetingDate,
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
        reason: "No runner matched for meeting + race number + exact TAB number",
      });
      continue;
    }

    matched.horse.finishPosition = finishPosition;
    runnersMatched += 1;
    affected.add(matched.race.id);
    meetingIds.add(matched.race.meetingId);
  }

  return {
    races: next,
    affectedMeetingIds: [...meetingIds],
    report: {
      kind: "results",
      meetingId: meetingIds.size === 1 ? [...meetingIds][0] : undefined,
      rowsParsed,
      racesAffected: affected.size,
      runnersMatched,
      runnersUnmatched: unmatched.length,
      runnersCreated: 0,
      unmatched,
      message: `Matched ${runnersMatched} result(s) by race number + exact TAB; ${unmatched.length} unmatched.`,
    },
  };
}
