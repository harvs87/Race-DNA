import assert from "node:assert/strict";
import { test } from "node:test";
import type { Race } from "../analysis/types.js";
import { matchRunner, tabNumbersEqual } from "./matchHorses.js";

const sampleRace: Race = {
  id: "flemington-r1",
  name: "Maiden Plate",
  course: "Flemington",
  raceNumber: 1,
  distanceFurlongs: 6,
  going: "good",
  runners: [
    {
      id: "one",
      tabNumber: 1,
      name: "Fast Bolt",
      recentForm: [1],
      speedFigure: 90,
      optimalDistanceFurlongs: 6,
      preferredGoing: ["good"],
      classRating: 90,
      jockeyWinRate: 0.1,
      trainerWinRate: 0.1,
      daysSinceLastRun: 20,
    },
    {
      id: "ten",
      tabNumber: 10,
      name: "Steel Road",
      recentForm: [4],
      speedFigure: 80,
      optimalDistanceFurlongs: 6,
      preferredGoing: ["good"],
      classRating: 80,
      jockeyWinRate: 0.1,
      trainerWinRate: 0.1,
      daysSinceLastRun: 20,
    },
    {
      id: "thirteen",
      tabNumber: 13,
      name: "Lucky Thirteen",
      recentForm: [2],
      speedFigure: 85,
      optimalDistanceFurlongs: 6,
      preferredGoing: ["good"],
      classRating: 85,
      jockeyWinRate: 0.1,
      trainerWinRate: 0.1,
      daysSinceLastRun: 20,
    },
  ],
};

test("tabNumbersEqual uses exact numeric equality", () => {
  assert.equal(tabNumbersEqual(1, 1), true);
  assert.equal(tabNumbersEqual("10", 10), true);
  assert.equal(tabNumbersEqual(1, 10), false);
  assert.equal(tabNumbersEqual(1, 13), false);
  assert.equal(tabNumbersEqual(10, 13), false);
  assert.equal(tabNumbersEqual("1", "10"), false);
  assert.equal(tabNumbersEqual("1", "13"), false);
});

test("matchRunner maps double-digit TAB numbers without colliding with 1", () => {
  const match1 = matchRunner([sampleRace], {
    meeting: "Flemington",
    raceNumber: 1,
    tabNumber: 1,
  });
  const match10 = matchRunner([sampleRace], {
    meeting: "Flemington",
    raceNumber: 1,
    tabNumber: 10,
  });
  const match13 = matchRunner([sampleRace], {
    meeting: "Flemington",
    raceNumber: 1,
    tabNumber: 13,
  });

  assert.equal(match1?.horse.name, "Fast Bolt");
  assert.equal(match10?.horse.name, "Steel Road");
  assert.equal(match13?.horse.name, "Lucky Thirteen");
  assert.notEqual(match10?.horse.id, match1?.horse.id);
  assert.notEqual(match13?.horse.id, match1?.horse.id);
});

test("matchRunner can fall back to horse name when TAB missing from field", () => {
  const match = matchRunner([sampleRace], {
    meeting: "Flemington",
    raceNumber: 1,
    tabNumber: 99,
    horseName: "Lucky Thirteen",
  });
  assert.equal(match?.method, "name");
  assert.equal(match?.horse.tabNumber, 13);
});
