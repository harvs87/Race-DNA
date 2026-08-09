export type Going = "firm" | "good" | "soft" | "heavy";

export interface FormHistoryEntry {
  meetingDate?: string;
  track?: string;
  trackCondition?: string;
  raceName?: string;
  distance?: string;
  className?: string;
  position?: number;
  margin?: string;
  price?: string;
  jockey?: string;
  barrier?: string;
  weight?: string;
  time?: string;
  otherRunners?: string;
}

export interface Horse {
  id: string;
  /** Official TAB / saddlecloth number for the race. */
  tabNumber: number;
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
  barrier?: number;
  weightKg?: number;
  jockey?: string;
  trainer?: string;
  /** Market win odds from TAB / TABtouch when imported. */
  winOdds?: number;
  placeOdds?: number;
  oddsSource?: string;
  /** Official finishing position when results have been imported. */
  finishPosition?: number;
  scratched?: boolean;
  /** Extra Punting Form identity / form fields retained for later analysis. */
  age?: number;
  sex?: string;
  sire?: string;
  dam?: string;
  claim?: number;
  last10?: string;
  record?: string;
  prizeMoney?: string;
  puntingFormHorseId?: string;
  formHistory?: FormHistoryEntry[];
  /** Full source-row column map (and any importer-added keys). */
  extras?: Record<string, string>;
}

export interface Race {
  id: string;
  meetingId: string;
  name: string;
  course: string;
  /** Meeting date ISO (YYYY-MM-DD) when known. */
  date?: string;
  raceNumber: number;
  startTime?: string;
  distanceFurlongs: number;
  distanceMeters?: number;
  going: Going;
  className?: string;
  extras?: Record<string, string>;
  runners: Horse[];
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
  races: Race[];
}

export interface FactorBreakdown {
  label: string;
  /** Normalised 0-100 contribution before weighting. */
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
  meetingId: string;
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
