import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { parseMeetingCsv } from "./meetingCsv.js";

const candidates = [
  join(dirname(fileURLToPath(import.meta.url)), "../../fixtures/belmont-080826-real.csv"),
  "/home/ubuntu/Downloads/080826_882d.csv",
  "/home/ubuntu/.cursor/projects/workspace/uploads/080826_882d.csv",
];

function loadRealBelmont(): string {
  for (const path of candidates) {
    if (existsSync(path)) return readFileSync(path, "utf8");
  }
  throw new Error(`Real Belmont CSV not found. Looked in: ${candidates.join(", ")}`);
}

test("real Belmont Punting Form CSV imports all races and exact horse numbers", () => {
  const csv = loadRealBelmont();
  const { meeting, format, report } = parseMeetingCsv(csv);

  assert.equal(format, "punting-form");
  assert.equal(meeting.course, "Belmont Park");
  assert.equal(meeting.date, "2026-08-08");
  assert.equal(meeting.raceCount, 8);
  assert.equal(meeting.runnerCount, 96);
  assert.equal(report.runnersCreated, 96);
  assert.ok(report.rowsParsed > 90);

  assert.deepEqual(
    meeting.races.map((race) => [race.raceNumber, race.runners.length]),
    [
      [1, 9],
      [2, 12],
      [3, 12],
      [4, 12],
      [5, 12],
      [6, 14],
      [7, 13],
      [8, 12],
    ],
  );

  const race1 = meeting.races.find((race) => race.raceNumber === 1)!;
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 1)?.name, "Properata");
  assert.equal(race1.runners.find((runner) => runner.tabNumber === 10)?.name, "Aura Magna");
  assert.ok(race1.startTime);

  const race6 = meeting.races.find((race) => race.raceNumber === 6)!;
  assert.equal(race6.runners.find((runner) => runner.tabNumber === 1)?.name, "Fifth Essence");
  assert.equal(race6.runners.find((runner) => runner.tabNumber === 10)?.name, "Lucky Moon");
  assert.equal(race6.runners.find((runner) => runner.tabNumber === 13)?.name, "Get Out Mick");

  const race7 = meeting.races.find((race) => race.raceNumber === 7)!;
  assert.equal(race7.runners.find((runner) => runner.tabNumber === 13)?.name, "Twisted Steel");

  for (const race of meeting.races) {
    const tabs = race.runners.map((runner) => runner.tabNumber);
    assert.equal(new Set(tabs).size, tabs.length);
    for (const tab of tabs) {
      assert.equal(Number.isInteger(tab), true);
      assert.ok(tab > 0);
    }
  }

  const properata = race1.runners.find((runner) => runner.tabNumber === 1)!;
  assert.ok(properata.extras);
  assert.equal(properata.extras?.["horse number"], "1");
  assert.equal(properata.extras?.["horse name"], "Properata");
  assert.ok((properata.formHistory?.length ?? 0) >= 1);
  assert.ok(properata.last10);
  assert.ok(properata.jockey);
  assert.ok(properata.trainer);
});
