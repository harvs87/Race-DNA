import type { DashboardSummary, RaceSummary } from "../types";

interface Props {
  dashboard: DashboardSummary | null;
  races: RaceSummary[];
  loading: boolean;
  onOpenRace: (raceId: string) => void;
}

export function DashboardView({ dashboard, races, loading, onOpenRace }: Props) {
  if (loading && !dashboard) {
    return <div className="banner">Loading dashboard…</div>;
  }

  if (!dashboard) {
    return <div className="banner error">Dashboard unavailable.</div>;
  }

  return (
    <div className="dashboard">
      <div className="analysis-head">
        <h2>Dashboard</h2>
        <p>Meetings loaded in RaceDNA, with model top picks ready for review.</p>
      </div>

      <div className="stat-row">
        <div className="stat">
          <span className="stat-value">{dashboard.meetingCount}</span>
          <span className="stat-label">Meetings</span>
        </div>
        <div className="stat">
          <span className="stat-value">{dashboard.raceCount}</span>
          <span className="stat-label">Races</span>
        </div>
        <div className="stat">
          <span className="stat-value">{dashboard.runnerCount}</span>
          <span className="stat-label">Runners</span>
        </div>
        <div className="stat">
          <span className="stat-value">{dashboard.oddsImported}</span>
          <span className="stat-label">Odds linked</span>
        </div>
        <div className="stat">
          <span className="stat-value">{dashboard.resultsImported}</span>
          <span className="stat-label">Results linked</span>
        </div>
      </div>

      <section className="panel-block">
        <h3>Meetings</h3>
        <ul className="plain-list">
          {dashboard.meetings.map((meeting) => (
            <li key={`${meeting.course}-${meeting.date ?? "na"}`}>
              <strong>{meeting.course}</strong>
              <span className="muted">
                {meeting.date ? ` · ${meeting.date}` : ""} · {meeting.raceCount} race
                {meeting.raceCount === 1 ? "" : "s"} · {meeting.runnerCount} runners
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel-block">
        <h3>Model top picks</h3>
        <ul className="plain-list">
          {dashboard.topPicks.map((pick) => (
            <li key={pick.raceId}>
              <button type="button" className="link-btn" onClick={() => onOpenRace(pick.raceId)}>
                <strong>
                  [{pick.tabNumber}] {pick.horseName}
                </strong>
                <span className="muted">
                  {" "}
                  · {pick.course} · {pick.raceName} · DNA {pick.dnaScore.toFixed(1)} ·{" "}
                  {Math.round(pick.winProbability * 100)}%
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="panel-block">
        <h3>Race card snapshot</h3>
        <ul className="plain-list">
          {races.map((race) => (
            <li key={race.id}>
              <button type="button" className="link-btn" onClick={() => onOpenRace(race.id)}>
                <strong>{race.name}</strong>
                <span className="muted">
                  {" "}
                  · {race.course}
                  {race.raceNumber ? ` R${race.raceNumber}` : ""} · {race.runnerCount} runners
                  {race.hasOdds ? " · odds" : ""}
                  {race.hasResults ? " · results" : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
