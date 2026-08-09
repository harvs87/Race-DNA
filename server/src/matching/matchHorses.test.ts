import assert from "node:assert/strict";
import { test } from "node:test";
import type { Race } from "../analysis/types.js";
import { matchRunner, raceNumbersEqual, tabNumbersEqual } from "./matchHorses.js";

function raceWithTabs(tabs: number[]): Race {
  return {
    id: "flemington-r1",
    meetingId: "flemington",
    name: "Maiden Plate",
    course: "Flemington",
    date: "2026-08-09",
    raceNumber: 1,
    distanceFurlongs: 6,
    going: "good",
    runners: tabs.map((tabNumber) => ({
      id: `tab-${tabNumber}`,
      tabNumber,
      name: `Horse ${tabNumber}`,
      recentForm: [1],
      speedFigure: 80,
      optimalDistanceFurlongs: 6,
      preferredGoing: ["good"],
      classRating: 80,
      jockeyWinRate: 0.1,
      trainerWinRate: 0.1,
      daysSinceLastRun: 20,
    })),
  };
}

test("tabNumbersEqual never confuses 1 with 10/11/12/13", () => {
  assert.equal(tabNumbersEqual(1, 1), true);
  assert.equal(tabNumbersEqual("10", 10), true);
  assert.equal(tabNumbersEqual("11", 11), true);
  assert.equal(tabNumbersEqual("12", 12), true);
  assert.equal(tabNumbersEqual("13", 13), true);
  assert.equal(tabNumbersEqual(1, 10), false);
  assert.equal(tabNumbersEqual(1, 11), false);
  assert.equal(tabNumbersEqual(1, 12), false);
  assert.equal(tabNumbersEqual(1, 13), false);
  assert.equal(tabNumbersEqual("1", "10"), false);
  assert.equal(tabNumbersEqual("1", "11"), false);
  assert.equal(tabNumbersEqual("1", "12"), false);
  assert.equal(tabNumbersEqual("1", "13"), false);
  assert.equal(tabNumbersEqual(10, 11), false);
  assert.equal(tabNumbersEqual(10, 12), false);
  assert.equal(tabNumbersEqual(10, 13), false);
});

test("raceNumbersEqual is exact integer equality", () => {
  assert.equal(raceNumbersEqual(1, 1), true);
  assert.equal(raceNumbersEqual("2", 2), true);
  assert.equal(raceNumbersEqual(1, 11), false);
  assert.equal(raceNumbersEqual("1", "10"), false);
});

test("matchRunner maps TAB 1/10/11/12/13 without collision", () => {
  const race = raceWithTabs([1, 10, 11, 12, 13]);
  for (const tab of [1, 10, 11, 12, 13]) {
    const match = matchRunner([race], {
      meeting: "Flemington",
      raceNumber: 1,
      tabNumber: tab,
    });
    assert.ok(match);
    assert.equal(match.horse.tabNumber, tab);
    assert.equal(match.horse.name, `Horse ${tab}`);
    assert.equal(match.method, "tab");
  }
});

test("matchRunner does not fall back to partial name or TAB string matches", () => {
  const race = raceWithTabs([1, 10, 13]);
  const missing = matchRunner([race], {
    meeting: "Flemington",
    raceNumber: 1,
    tabNumber: 11,
    horseName: "Horse 1",
  });
  assert.equal(missing, undefined);
});
