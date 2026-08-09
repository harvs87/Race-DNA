import { useEffect, useState } from "react";
import {
  fetchAnalysis,
  fetchDashboard,
  fetchRaces,
  importMeetingCsv,
  importOddsCsv,
  importResultsCsv,
} from "./api";
import { SidebarNav } from "./components/SidebarNav";
import type { AppView, DashboardSummary, RaceAnalysis, RaceSummary } from "./types";
import { DashboardView } from "./views/DashboardView";
import { ImportView } from "./views/ImportView";
import { RaceDnaView } from "./views/RaceDnaView";

export function App() {
  const [view, setView] = useState<AppView>("dashboard");
  const [races, setRaces] = useState<RaceSummary[]>([]);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<RaceAnalysis | null>(null);
  const [loadingRaces, setLoadingRaces] = useState(true);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshLists(preferredRaceId?: string | null) {
    setLoadingRaces(true);
    setError(null);
    try {
      const [raceData, dashData] = await Promise.all([fetchRaces(), fetchDashboard()]);
      setRaces(raceData);
      setDashboard(dashData);
      setSelectedId((current) => {
        if (preferredRaceId && raceData.some((race) => race.id === preferredRaceId)) {
          return preferredRaceId;
        }
        if (current && raceData.some((race) => race.id === current)) return current;
        return raceData[0]?.id ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load races");
    } finally {
      setLoadingRaces(false);
    }
  }

  useEffect(() => {
    void refreshLists();
  }, []);

  useEffect(() => {
    if (!selectedId || view !== "race-dna") return;
    setLoadingAnalysis(true);
    setError(null);
    fetchAnalysis(selectedId)
      .then(setAnalysis)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoadingAnalysis(false));
  }, [selectedId, view, races]);

  function openRace(raceId: string) {
    setSelectedId(raceId);
    setView("race-dna");
  }

  return (
    <div className="app">
      <header className="masthead">
        <div className="brand">
          <span className="brand-mark">RaceDNA</span>
          <span className="brand-tag">Horse Racing Analysis</span>
        </div>
        <p className="masthead-sub">
          Model-driven form ratings, distance and going fit, and win probabilities.
        </p>
      </header>

      <div className="shell">
        <SidebarNav active={view} onSelect={setView} />

        <main className="main-pane">
          {view === "dashboard" && (
            <DashboardView
              dashboard={dashboard}
              races={races}
              loading={loadingRaces}
              onOpenRace={openRace}
            />
          )}

          {view === "race-dna" && (
            <RaceDnaView
              races={races}
              selectedId={selectedId}
              analysis={analysis}
              loading={loadingAnalysis || loadingRaces}
              error={error}
              onSelectRace={setSelectedId}
            />
          )}

          {view === "import-meeting" && (
            <ImportView
              title="Import Meeting CSV"
              description="Upload a Wizard-style meeting CSV to load fields, form, and TAB numbers."
              sampleHint="Expected columns include Meeting, Race Number, Tab Number, Horse, Distance, Form / Last Finish pos. Sample: samples/meeting-flemington.csv"
              onImport={importMeetingCsv}
              onImported={() => {
                void refreshLists();
              }}
            />
          )}

          {view === "import-results" && (
            <ImportView
              title="Import Results"
              description="Attach finishing positions to runners matched by meeting, race number, and exact TAB number."
              sampleHint="Expected columns: Meeting, Race Number, Tab Number, Horse, Finish Position. Sample: samples/results-flemington.csv"
              onImport={importResultsCsv}
              onImported={() => {
                void refreshLists();
              }}
            />
          )}

          {view === "import-odds" && (
            <ImportView
              title="Import TAB / TABtouch Odds"
              description="Import win/place odds and match them to runners using exact TAB numbers (so 10 and 13 never collide with 1)."
              sampleHint="Expected columns: Meeting, Race Number, Tab Number, Horse, Win Odds, Place Odds, Source. Sample: samples/odds-tabtouch.csv"
              onImport={importOddsCsv}
              onImported={() => {
                void refreshLists();
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
}
