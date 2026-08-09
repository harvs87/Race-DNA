import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import { closeDatabase } from "../db/database.js";
import {
  applyMeetingImport,
  applyOddsImport,
  applyResultsImport,
  getMeeting,
  resetStore,
} from "../data/store.js";
import { parseMeetingCsv } from "./meetingCsv.js";
import { importOddsCsv } from "./oddsCsv.js";
import { importResultsCsv } from "./resultsCsv.js";

const fixtures = join(dirname(fileURLToPath(import.meta.url)), "../../fixtures");
const testDb = join(tmpdir(), `racedna-import-test-${process.pid}.sqlite`);

before(() => {
  process.env.RACEDNA_DB_PATH = testDb;
  closeDatabase();
  resetStore();
});

after(() => {
  closeDatabase();
});

test("Punting Form meeting CSV preserves TAB 1/10/11/12/13 exactly", () => {
  const csv = readFileSync(join(fixtures, "meeting-punting-form.csv"), "utf8");
  const { meeting, format, report } = parseMeetingCsv(csv);
  assert.equal(format, "punting-form");
  assert.equal(report.racesAffected, 2);
  const race1 = meeting.races.find((race) => race.raceNumber === 1);
  assert.ok(race1);
  const tabs = race1.runners.map((runner) => runner.tabNumber).sort((a, b) => a - b);
  assert.deepEqual(tabs, [1, 10, 11, 12, 13]);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 1)?.name, "Fast Bolt");
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 10)?.name, "Steel Road");
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 11)?.name, "Copper Queen");
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 12)?.name, "Midnight Oil");
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 13)?.name, "Lucky Thirteen");
});

test("results import matches by race number + exact TAB for 1/10/11/12/13", () => {
  const meetingCsv = readFileSync(join(fixtures, "meeting-punting-form.csv"), "utf8");
  const resultsCsv = readFileSync(join(fixtures, "results-punting-form.csv"), "utf8");
  const { meeting } = parseMeetingCsv(meetingCsv);
  const { races, report } = importResultsCsv(resultsCsv, meeting.races);

  assert.equal(report.runnersMatched, 9);
  assert.equal(report.runnersUnmatched, 0);

  const race1 = races.find((race) => race.raceNumber === 1)!;
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 1)?.finishPosition, 3);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 10)?.finishPosition, 1);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 11)?.finishPosition, 4);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 12)?.finishPosition, 5);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 13)?.finishPosition, 2);
});

test("odds import never gives TAB 1 market to 10/11/12/13", () => {
  const meetingCsv = readFileSync(join(fixtures, "meeting-punting-form.csv"), "utf8");
  const oddsCsv = readFileSync(join(fixtures, "odds-tabtouch.csv"), "utf8");
  const { meeting } = parseMeetingCsv(meetingCsv);
  const { races, report } = importOddsCsv(oddsCsv, meeting.races);
  assert.equal(report.runnersUnmatched, 0);

  const race1 = races.find((race) => race.raceNumber === 1)!;
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 1)?.winOdds, 4.2);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 10)?.winOdds, 12);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 11)?.winOdds, 9.5);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 12)?.winOdds, 15);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 13)?.winOdds, 6.5);
});

test("SQLite persistence keeps imported meetings after reopen", () => {
  resetStore();
  const meetingCsv = readFileSync(join(fixtures, "meeting-punting-form.csv"), "utf8");
  const resultsCsv = readFileSync(join(fixtures, "results-punting-form.csv"), "utf8");
  const meetingReport = applyMeetingImport(meetingCsv);
  assert.ok(meetingReport.meetingId);

  applyResultsImport(resultsCsv);
  closeDatabase();

  const reopened = getMeeting(meetingReport.meetingId!);
  assert.ok(reopened);
  assert.equal(reopened.course, "Flemington");
  assert.equal(reopened.raceCount, 2);
  const race1 = reopened.races.find((race) => race.raceNumber === 1)!;
  const tabs = race1.runners.map((runner) => runner.tabNumber).sort((a, b) => a - b);
  assert.deepEqual(tabs, [1, 10, 11, 12, 13]);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 10)?.finishPosition, 1);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 13)?.finishPosition, 2);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 1)?.finishPosition, 3);
});

test("odds import persists through SQLite reopen", () => {
  resetStore();
  const meetingCsv = readFileSync(join(fixtures, "meeting-punting-form.csv"), "utf8");
  const oddsCsv = readFileSync(join(fixtures, "odds-tabtouch.csv"), "utf8");
  const meetingReport = applyMeetingImport(meetingCsv);
  applyOddsImport(oddsCsv);
  closeDatabase();

  const reopened = getMeeting(meetingReport.meetingId!);
  assert.ok(reopened);
  const race1 = reopened.races.find((race) => race.raceNumber === 1)!;
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 11)?.winOdds, 9.5);
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 12)?.winOdds, 15);
});
