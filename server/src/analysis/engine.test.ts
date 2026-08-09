import assert from "node:assert/strict";
import { test } from "node:test";
import { getRaceById } from "../data/races.js";
import { analyzeRace } from "./engine.js";

test("analysis ranks the strongest profile first", () => {
  const race = getRaceById("ascot-2026-08-09-r1");
  assert.ok(race);
  const analysis = analyzeRace(race);
  assert.equal(analysis.runners[0].rank, 1);
  assert.equal(analysis.runners[0].horseId, "midnight-runner");
});

test("win probabilities are normalised to ~1", () => {
  const race = getRaceById("york-2026-08-09-r2");
  assert.ok(race);
  const analysis = analyzeRace(race);
  const total = analysis.runners.reduce((sum, r) => sum + r.winProbability, 0);
  assert.ok(Math.abs(total - 1) < 1e-9);
});

test("ranks are strictly ordered by DNA score", () => {
  const race = getRaceById("ascot-2026-08-09-r1");
  assert.ok(race);
  const analysis = analyzeRace(race);
  for (let i = 1; i < analysis.runners.length; i += 1) {
    assert.ok(analysis.runners[i - 1].dnaScore >= analysis.runners[i].dnaScore);
    assert.equal(analysis.runners[i].rank, i + 1);
  }
});

test("analysis exposes TAB numbers including double digits", () => {
  const race = getRaceById("ascot-2026-08-09-r1");
  assert.ok(race);
  const analysis = analyzeRace(race);
  const tabs = analysis.runners.map((runner) => runner.tabNumber).sort((a, b) => a - b);
  assert.deepEqual(tabs, [1, 2, 3, 10, 13]);
});
