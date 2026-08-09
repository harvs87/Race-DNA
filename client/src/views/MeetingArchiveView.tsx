import type { MeetingSummary } from "../types";

interface Props {
  meetings: MeetingSummary[];
  loading: boolean;
  selectedId: string | null;
  onOpenMeeting: (meetingId: string) => void;
}

export function MeetingArchiveView({ meetings, loading, selectedId, onOpenMeeting }: Props) {
  if (loading && meetings.length === 0) {
    return <div className="banner">Loading archive…</div>;
  }

  return (
    <div className="archive-view">
      <div className="analysis-head">
        <h2>Meeting Archive</h2>
        <p>Previously imported meetings stored in the local SQLite database. Reopen any meeting to review races and runners.</p>
      </div>

      {meetings.length === 0 ? (
        <div className="banner">No meetings stored yet. Import a Punting Form Meeting CSV to begin.</div>
      ) : (
        <ul className="plain-list archive-list">
          {meetings.map((meeting) => (
            <li key={meeting.id}>
              <button
                type="button"
                className={
                  meeting.id === selectedId ? "race-btn active" : "race-btn"
                }
                onClick={() => onOpenMeeting(meeting.id)}
              >
                <span className="race-name">
                  {meeting.course}
                  {meeting.date ? ` · ${meeting.date}` : ""}
                </span>
                <span className="race-meta">
                  {meeting.raceCount} races · {meeting.runnerCount} runners · {meeting.source}
                  {meeting.resultsCount ? ` · ${meeting.resultsCount} results` : ""}
                  {meeting.oddsCount ? ` · ${meeting.oddsCount} odds` : ""}
                  {" · updated "}
                  {new Date(meeting.updatedAt).toLocaleString()}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
