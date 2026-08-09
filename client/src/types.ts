export type Going = "firm" | "good" | "soft" | "heavy";

export type AppView =
  | "dashboard"
  | "meeting"
  | "meeting-archive"
  | "race-dna"
  | "import-meeting"
  | "import-results"
  | "import-odds";

export interface RaceSummary {
  id: string;
  meetingId?: string;
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

export interface RunnerDetail {
  id: string;
  tabNumber: number;
  name: string;
  barrier?: number;
  weightKg?: number;
  jockey?: string;
  trainer?: string;
  recentForm: number[];
  winOdds?: number;
  placeOdds?: number;
  finishPosition?: number;
  scratched?: boolean;
}

export interface RaceDetail {
  id: string;
  meetingId: string;
  name: string;
  course: string;
  date?: string;
  raceNumber: number;
  distanceFurlongs: number;
  distanceMeters?: number;
  going: Going;
  className?: string;
  runners: RunnerDetail[];
}

export interface MeetingSummary {
  id: string;
  course: string;
  date?: string;
  trackCondition?: string;
  source: string;
  puntingFormMeetingId?: string;
  raceCount: number;
  runnerCount: number;
  resultsCount: number;
  oddsCount: number;
  importedAt: string;
  updatedAt: string;
}

export interface MeetingDetail extends MeetingSummary {
  races: RaceDetail[];
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
  meetingId?: string;
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
  meetings: MeetingSummary[];
  topPicks: Array<{
    raceId: string;
    meetingId: string;
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
  meetingId?: string;
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
