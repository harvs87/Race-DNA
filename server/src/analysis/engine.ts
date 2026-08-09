import type {
  FactorBreakdown,
  Horse,
  HorseAnalysis,
  Race,
  RaceAnalysis,
} from "./types.js";

const WEIGHTS = {
  form: 0.28,
  speed: 0.24,
  distance: 0.16,
  going: 0.12,
  class: 0.1,
  connections: 0.06,
  freshness: 0.04,
} as const;

const clamp = (value: number, min = 0, max = 100): number =>
  Math.max(min, Math.min(max, value));

/**
 * Convert recent finishing positions into a 0-100 form score. Wins and places
 * are rewarded and more recent runs are weighted more heavily.
 */
function formScore(recentForm: number[]): number {
  if (recentForm.length === 0) return 50;
  let weightedSum = 0;
  let weightTotal = 0;
  recentForm.forEach((position, index) => {
    const recencyWeight = 1 / (index + 1);
    const positionScore = clamp(105 - position * 15);
    weightedSum += positionScore * recencyWeight;
    weightTotal += recencyWeight;
  });
  return clamp(weightedSum / weightTotal);
}

/** Reward horses whose optimal trip is close to today's race distance. */
function distanceScore(optimal: number, raceDistance: number): number {
  const deltaFurlongs = Math.abs(optimal - raceDistance);
  return clamp(100 - deltaFurlongs * 18);
}

function goingScore(horse: Horse, race: Race): number {
  return horse.preferredGoing.includes(race.going) ? 100 : 45;
}

function connectionsScore(horse: Horse): number {
  return clamp(((horse.jockeyWinRate + horse.trainerWinRate) / 2) * 100 * 2.5);
}

/** Horses are sharpest a few weeks out; long layoffs and quick backups cost. */
function freshnessScore(daysSinceLastRun: number): number {
  const ideal = 21;
  const penalty = Math.abs(daysSinceLastRun - ideal) * 1.1;
  return clamp(100 - penalty);
}

function buildFactors(horse: Horse, race: Race): FactorBreakdown[] {
  return [
    { label: "Recent form", score: formScore(horse.recentForm), weight: WEIGHTS.form },
    { label: "Speed figure", score: clamp(horse.speedFigure * (100 / 120)), weight: WEIGHTS.speed },
    {
      label: "Distance fit",
      score: distanceScore(horse.optimalDistanceFurlongs, race.distanceFurlongs),
      weight: WEIGHTS.distance,
    },
    { label: "Going suitability", score: goingScore(horse, race), weight: WEIGHTS.going },
    { label: "Class rating", score: clamp(horse.classRating * (100 / 120)), weight: WEIGHTS.class },
    { label: "Connections", score: connectionsScore(horse), weight: WEIGHTS.connections },
    { label: "Freshness", score: freshnessScore(horse.daysSinceLastRun), weight: WEIGHTS.freshness },
  ];
}

function dnaScore(factors: FactorBreakdown[]): number {
  const total = factors.reduce((sum, f) => sum + f.score * f.weight, 0);
  return Math.round(total * 10) / 10;
}

/** Turn DNA scores into win probabilities with a temperature-scaled softmax. */
function winProbabilities(scores: number[]): number[] {
  const temperature = 8;
  const exps = scores.map((s) => Math.exp(s / temperature));
  const sum = exps.reduce((a, b) => a + b, 0);
  return exps.map((e) => e / sum);
}

function verdictFor(rank: number, probability: number): string {
  const pct = Math.round(probability * 100);
  if (rank === 1) return `Top pick on the numbers (${pct}% model win chance).`;
  if (rank === 2) return `Leading danger and each-way value (${pct}%).`;
  if (probability >= 0.1) return `Live outsider worth a look (${pct}%).`;
  return `Needs improvement to feature (${pct}%).`;
}

export function analyzeRace(race: Race): RaceAnalysis {
  const scored = race.runners.map((horse) => {
    const factors = buildFactors(horse, race);
    return { horse, factors, dna: dnaScore(factors) };
  });

  const probabilities = winProbabilities(scored.map((s) => s.dna));

  const runners: HorseAnalysis[] = scored
    .map((entry, index) => ({
      horseId: entry.horse.id,
      name: entry.horse.name,
      dnaScore: entry.dna,
      winProbability: probabilities[index],
      rank: 0,
      factors: entry.factors,
      verdict: "",
    }))
    .sort((a, b) => b.dnaScore - a.dnaScore)
    .map((runner, index) => ({
      ...runner,
      rank: index + 1,
      verdict: verdictFor(index + 1, runner.winProbability),
    }));

  return {
    raceId: race.id,
    name: race.name,
    course: race.course,
    distanceFurlongs: race.distanceFurlongs,
    going: race.going,
    runners,
  };
}
