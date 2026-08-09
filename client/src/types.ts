export type Going = "firm" | "good" | "soft" | "heavy";

export type AppView =
  | "dashboard"
  | "race-dna"
  | "import-meeting"
  | "import-results"
  | "import-odds";

export interface RaceSummary {
  id: string;
  name: string;
  course: string;
  date?: string;
  raceNumber?: number;
  distanceFurlongs: number;
  distanceMeters?: number;
  going: Going;
  runnerCount: number;
  hasOdds?: boolean;
  hasResults?: boolean;
}

export interface FactorBreakdown {
  label: string;
  score: number;
  weight: number;
}

export interface HorseAnalysis {
  horseId: string;
  tabNumber: number;
  name: string;
  dnaScore: number;
  winProbability: number;
  rank: number;
  factors: FactorBreakdown[];
  verdict: string;
  winOdds?: number;
  placeOdds?: number;
  finishPosition?: number;
  scratched?: boolean;
  matchStatus?: "matched" | "unmatched" | "seed";
}

export interface RaceAnalysis {
  raceId: string;
  name: string;
  course: string;
  date?: string;
  raceNumber?: number;
  distanceFurlongs: number;
  distanceMeters?: number;
  going: Going;
  runners: HorseAnalysis[];
}

export interface DashboardSummary {
  meetingCount: number;
  raceCount: number;
  runnerCount: number;
  resultsImported: number;
  oddsImported: number;
  meetings: Array<{
    course: string;
    date?: string;
    raceCount: number;
    runnerCount: number;
  }>;
  topPicks: Array<{
    raceId: string;
    raceName: string;
    course: string;
    horseName: string;
    tabNumber: number;
    dnaScore: number;
    winProbability: number;
  }>;
}

export interface ImportReport {
  kind: "meeting" | "results" | "odds";
  rowsParsed: number;
  racesAffected: number;
  runnersMatched: number;
  runnersUnmatched: number;
  runnersCreated: number;
  unmatched: Array<{
    meeting: string;
    raceNumber: number;
    tabNumber?: number;
    horse?: string;
    reason: string;
  }>;
  message: string;
}
