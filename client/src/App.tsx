import { useEffect, useState } from "react";
import {
  fetchAnalysis,
  fetchDashboard,
  fetchMeeting,
  fetchMeetings,
  fetchRaces,
  importMeetingCsv,
  importOddsCsv,
  importResultsCsv,
} from "./api";
import { SidebarNav } from "./components/SidebarNav";
import type {
  AppView,
  DashboardSummary,
  MeetingDetail,
  MeetingSummary,
  RaceAnalysis,
  RaceSummary,
} from "./types";
import { DashboardView } from "./views/DashboardView";
import { ImportView } from "./views/ImportView";
import { MeetingArchiveView } from "./views/MeetingArchiveView";
import { MeetingView } from "./views/MeetingView";
import { RaceDnaView } from "./views/RaceDnaView";

export function App() {
  const [view, setView] = useState<AppView>("dashboard");
  const [races, setRaces] = useState<RaceSummary[]>([]);
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [selectedMeetingId, setSelectedMeetingId] = useState<string | null>(null);
  const [meetingDetail, setMeetingDetail] = useState<MeetingDetail | null>(null);
  const [selectedRaceId, setSelectedRaceId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<RaceAnalysis | null>(null);
  const [loadingLists, setLoadingLists] = useState(true);
  const [loadingMeeting, setLoadingMeeting] = useState(false);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshLists(preferredMeetingId?: string | null, preferredRaceId?: string | null) {
    setLoadingLists(true);
    setError(null);
    try {
      const [raceData, dashData, meetingData] = await Promise.all([
        fetchRaces(),
        fetchDashboard(),
        fetchMeetings(),
      ]);
      setRaces(raceData);
      setDashboard(dashData);
      setMeetings(meetingData);

      setSelectedMeetingId((current) => {
        if (preferredMeetingId && meetingData.some((meeting) => meeting.id === preferredMeetingId)) {
          return preferredMeetingId;
        }
        if (current && meetingData.some((meeting) => meeting.id === current)) return current;
        return meetingData[0]?.id ?? null;
      });

      setSelectedRaceId((current) => {
        if (preferredRaceId && raceData.some((race) => race.id === preferredRaceId)) {
          return preferredRaceId;
        }
        if (current && raceData.some((race) => race.id === current)) return current;
        return raceData[0]?.id ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoadingLists(false);
    }
  }

  useEffect(() => {
    void refreshLists();
  }, []);

  useEffect(() => {
    if (!selectedMeetingId) {
      setMeetingDetail(null);
      return;
    }
    if (view !== "meeting") return;

    setLoadingMeeting(true);
    fetchMeeting(selectedMeetingId)
      .then(setMeetingDetail)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoadingMeeting(false));
  }, [selectedMeetingId, view, meetings]);

  useEffect(() => {
    if (!selectedRaceId || view !== "race-dna") return;
    setLoadingAnalysis(true);
    setError(null);
    fetchAnalysis(selectedRaceId)
      .then(setAnalysis)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoadingAnalysis(false));
  }, [selectedRaceId, view, races]);

  function openRace(raceId: string) {
    const race = races.find((item) => item.id === raceId);
    if (race?.meetingId) setSelectedMeetingId(race.meetingId);
    setSelectedRaceId(raceId);
    setView("race-dna");
  }

  function openMeeting(meetingId: string) {
    setSelectedMeetingId(meetingId);
    setView("meeting");
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
              loading={loadingLists}
              onOpenRace={openRace}
              onOpenMeeting={openMeeting}
            />
          )}

          {view === "meeting" && (
            <MeetingView
              meeting={meetingDetail}
              loading={loadingMeeting || loadingLists}
              error={error}
              onOpenRace={openRace}
              onOpenArchive={() => setView("meeting-archive")}
            />
          )}

          {view === "meeting-archive" && (
            <MeetingArchiveView
              meetings={meetings}
              loading={loadingLists}
              selectedId={selectedMeetingId}
              onOpenMeeting={openMeeting}
            />
          )}

          {view === "race-dna" && (
            <RaceDnaView
              races={races}
              selectedId={selectedRaceId}
              analysis={analysis}
              loading={loadingAnalysis || loadingLists}
              error={error}
              onSelectRace={setSelectedRaceId}
            />
          )}

          {view === "import-meeting" && (
            <ImportView
              title="Import Meeting CSV"
              description="Upload a real Punting Form Meeting CSV (track, race number, horse number, horse name, …). Form-expanded rows are collapsed per horse. TAB/horse numbers are stored as exact integers."
              sampleHint="Real PF columns include: meeting date, track, race number, start time, distance, race name, horse name, horse number, horse jockey, horse barrier, horse trainer, horse last10, …"
              onImport={importMeetingCsv}
              onImported={(report) => {
                void refreshLists(report.meetingId ?? null).then(() => {
                  if (report.meetingId) {
                    setSelectedMeetingId(report.meetingId);
                    setView("meeting");
                  }
                });
              }}
            />
          )}

          {view === "import-results" && (
            <ImportView
              title="Import Results"
              description="Attach finishing positions using meeting + race number + exact TAB number. Partial TAB matching is never used."
              sampleHint="Sample: samples/results-punting-form.csv (Track/MeetingDate, RaceNumber, TabNo, Position)"
              onImport={importResultsCsv}
              onImported={(report) => {
                void refreshLists(report.meetingId ?? selectedMeetingId).then(() => {
                  if (report.meetingId) {
                    setSelectedMeetingId(report.meetingId);
                    setView("meeting");
                  }
                });
              }}
            />
          )}

          {view === "import-odds" && (
            <ImportView
              title="Import TAB / TABtouch Odds"
              description="Separate odds capture import (no live feed). Matches runners by race number and exact TAB number."
              sampleHint="Sample: samples/odds-tabtouch.csv (Meeting, Race Number, Tab Number, Win Odds, Place Odds, Source)"
              onImport={importOddsCsv}
              onImported={(report) => {
                void refreshLists(report.meetingId ?? selectedMeetingId);
              }}
            />
          )}
        </main>
      </div>
    </div>
  );
}
