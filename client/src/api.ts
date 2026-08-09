import type { RaceAnalysis, RaceSummary } from "./types";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export function fetchRaces(): Promise<RaceSummary[]> {
  return getJson<RaceSummary[]>("/api/races");
}

export function fetchAnalysis(raceId: string): Promise<RaceAnalysis> {
  return getJson<RaceAnalysis>(`/api/races/${raceId}/analysis`);
}
