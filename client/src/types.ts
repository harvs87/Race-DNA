export type Going = "firm" | "good" | "soft" | "heavy";

export interface RaceSummary {
  id: string;
  name: string;
  course: string;
  distanceFurlongs: number;
  going: Going;
  runnerCount: number;
}

export interface FactorBreakdown {
  label: string;
  score: number;
  weight: number;
}

export interface HorseAnalysis {
  horseId: string;
  name: string;
  dnaScore: number;
  winProbability: number;
  rank: number;
  factors: FactorBreakdown[];
  verdict: string;
}

export interface RaceAnalysis {
  raceId: string;
  name: string;
  course: string;
  distanceFurlongs: number;
  going: Going;
  runners: HorseAnalysis[];
}
