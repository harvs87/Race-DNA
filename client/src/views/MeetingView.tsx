import type { MeetingDetail } from "../types";

interface Props {
  meeting: MeetingDetail | null;
  loading: boolean;
  error: string | null;
  onOpenRace: (raceId: string) => void;
  onOpenArchive: () => void;
}

export function MeetingView({ meeting, loading, error, onOpenRace, onOpenArchive }: Props) {
  if (loading && !meeting) {
    return <div className="banner">Loading meeting…</div>;
  }

  if (error) {
    return <div className="banner error">{error}</div>;
  }

  if (!meeting) {
    return (
      <div className="panel-block">
        <h2>Meeting</h2>
        <p className="muted">
          No meeting selected. Import a Punting Form Meeting CSV or reopen one from the archive.
        </p>
        <button type="button" className="primary-btn" onClick={onOpenArchive}>
          Open Meeting Archive
        </button>
      </div>
    );
  }

  return (
    <div className="meeting-view">
      <div className="analysis-head">
        <h2>
          {meeting.course}
          {meeting.date ? ` · ${meeting.date}` : ""}
        </h2>
        <p>
          {meeting.raceCount} race{meeting.raceCount === 1 ? "" : "s"} · {meeting.runnerCount}{" "}
          runners · source: {meeting.source}
          {meeting.trackCondition ? ` · ${meeting.trackCondition}` : ""}
          {meeting.resultsCount ? ` · ${meeting.resultsCount} results` : ""}
          {meeting.oddsCount ? ` · ${meeting.oddsCount} odds` : ""}
        </p>
      </div>

      {meeting.races.map((race) => (
        <section className="panel-block" key={race.id}>
          <div className="meeting-race-head">
            <h3>
              R{race.raceNumber} · {race.name}
            </h3>
            <button type="button" className="link-btn" onClick={() => onOpenRace(race.id)}>
              Open in Race DNA →
            </button>
          </div>
          <p className="muted">
            {race.startTime ? `${race.startTime} · ` : ""}
            {race.distanceMeters ? `${race.distanceMeters}m` : `${race.distanceFurlongs}f`}
            {race.className ? ` · ${race.className}` : ""} · {race.going} · {race.runners.length}{" "}
            runners
          </p>

          <div className="runner-table-wrap">
            <table className="runner-table">
              <thead>
                <tr>
                  <th>TAB</th>
                  <th>Runner</th>
                  <th>Barrier</th>
                  <th>Weight</th>
                  <th>Jockey</th>
                  <th>Trainer</th>
                  <th>Form</th>
                  <th>Odds</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {race.runners.map((runner) => (
                  <tr key={runner.id} className={runner.scratched ? "scratched" : undefined}>
                    <td className="tab-cell">{runner.tabNumber}</td>
                    <td>{runner.name}</td>
                    <td>{runner.barrier ?? "—"}</td>
                    <td>{runner.weightKg ?? "—"}</td>
                    <td>{runner.jockey ?? "—"}</td>
                    <td>{runner.trainer ?? "—"}</td>
                    <td>{runner.recentForm.join("-") || "—"}</td>
                    <td>
                      {runner.winOdds !== undefined
                        ? `${runner.winOdds.toFixed(2)}${
                            runner.placeOdds !== undefined
                              ? ` / ${runner.placeOdds.toFixed(2)}`
                              : ""
                          }`
                        : "—"}
                    </td>
                    <td>{runner.finishPosition ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
