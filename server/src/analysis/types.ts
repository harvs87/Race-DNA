export type Going = "firm" | "good" | "soft" | "heavy";

export interface Horse {
  id: string;
  name: string;
  /** Recent finishing positions, most recent first (1 = win). */
  recentForm: number[];
  /** Peak speed figure on a 0-120 scale. */
  speedFigure: number;
  /** Distance in furlongs at which the horse performs best. */
  optimalDistanceFurlongs: number;
  /** Track surface conditions the horse handles well. */
  preferredGoing: Going[];
  /** Official class/handicap rating (0-120). */
  classRating: number;
  jockeyWinRate: number;
  trainerWinRate: number;
  /** Days since the horse last raced. */
  daysSinceLastRun: number;
}

export interface Race {
  id: string;
  name: string;
  course: string;
  distanceFurlongs: number;
  going: Going;
  runners: Horse[];
}

export interface FactorBreakdown {
  label: string;
  /** Normalised 0-100 contribution before weighting. */
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
