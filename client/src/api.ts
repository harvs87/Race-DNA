import type {
  DashboardSummary,
  ImportReport,
  RaceAnalysis,
  RaceSummary,
} from "./types";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

async function postCsv(url: string, csv: string): Promise<ImportReport> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "text/csv" },
    body: csv,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return (await response.json()) as ImportReport;
}

export function fetchDashboard(): Promise<DashboardSummary> {
  return getJson<DashboardSummary>("/api/dashboard");
}

export function fetchRaces(): Promise<RaceSummary[]> {
  return getJson<RaceSummary[]>("/api/races");
}

export function fetchAnalysis(raceId: string): Promise<RaceAnalysis> {
  return getJson<RaceAnalysis>(`/api/races/${raceId}/analysis`);
}

export function importMeetingCsv(csv: string): Promise<ImportReport> {
  return postCsv("/api/import/meeting", csv);
}

export function importResultsCsv(csv: string): Promise<ImportReport> {
  return postCsv("/api/import/results", csv);
}

export function importOddsCsv(csv: string): Promise<ImportReport> {
  return postCsv("/api/import/odds", csv);
}
