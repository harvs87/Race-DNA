import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { importMeetingCsv } from "./meetingCsv.js";
import { importOddsCsv } from "./oddsCsv.js";
import { importResultsCsv } from "./resultsCsv.js";

const fixtures = join(dirname(fileURLToPath(import.meta.url)), "../../fixtures");

test("meeting import creates races with double-digit TAB numbers", () => {
  const csv = readFileSync(join(fixtures, "meeting-flemington.csv"), "utf8");
  const { races, report } = importMeetingCsv(csv, []);
  assert.equal(report.racesAffected, 1);
  assert.equal(races[0].runners.length, 5);
  const tabs = races[0].runners.map((runner) => runner.tabNumber).sort((a, b) => a - b);
  assert.deepEqual(tabs, [1, 3, 7, 10, 13]);
});

test("odds import matches TAB 10 and 13 exactly, not runner 1", () => {
  const meeting = readFileSync(join(fixtures, "meeting-flemington.csv"), "utf8");
  const odds = readFileSync(join(fixtures, "odds-tabtouch.csv"), "utf8");
  const { races } = importMeetingCsv(meeting, []);
  const { races: withOdds, report } = importOddsCsv(odds, races);

  assert.equal(report.runnersMatched, 5);
  assert.equal(report.runnersUnmatched, 0);

  const one = withOdds[0].runners.find((runner) => runner.tabNumber === 1);
  const ten = withOdds[0].runners.find((runner) => runner.tabNumber === 10);
  const thirteen = withOdds[0].runners.find((runner) => runner.tabNumber === 13);

  assert.equal(one?.winOdds, 4.2);
  assert.equal(ten?.winOdds, 12);
  assert.equal(thirteen?.winOdds, 6.5);
  assert.equal(ten?.name, "Steel Road");
  assert.equal(thirteen?.name, "Lucky Thirteen");
});

test("results import attaches finish positions by exact TAB number", () => {
  const meeting = readFileSync(join(fixtures, "meeting-flemington.csv"), "utf8");
  const results = readFileSync(join(fixtures, "results-flemington.csv"), "utf8");
  const { races } = importMeetingCsv(meeting, []);
  const { races: withResults, report } = importResultsCsv(results, races);

  assert.equal(report.runnersMatched, 5);
  const ten = withResults[0].runners.find((runner) => runner.tabNumber === 10);
  const thirteen = withResults[0].runners.find((runner) => runner.tabNumber === 13);
  const one = withResults[0].runners.find((runner) => runner.tabNumber === 1);

  assert.equal(ten?.finishPosition, 1);
  assert.equal(thirteen?.finishPosition, 2);
  assert.equal(one?.finishPosition, 3);
});
