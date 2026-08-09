from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from racedna.pf_api import MeetingInfo, PuntingFormClient, PuntingFormError


@dataclass
class DownloadItem:
    kind: str
    meeting_id: int
    track: str
    path: str
    bytes: int
    ok: bool = True
    error: str | None = None


@dataclass
class DownloadReport:
    date: str | None
    out_dir: str
    meetings: list[dict] = field(default_factory=list)
    files: list[DownloadItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "out_dir": self.out_dir,
            "meetings": self.meetings,
            "files": [asdict(f) for f in self.files],
            "errors": self.errors,
        }


def _parse_date(value: str) -> str:
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d", "%d%m%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date: {value} (use YYYY-MM-DD)")


def _slug(track: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", track.strip()).strip("_")
    return cleaned or "Track"


def _date_stamp(iso_date: str | None) -> str:
    if not iso_date:
        return datetime.now().strftime("%y%m%d")
    try:
        return date.fromisoformat(iso_date[:10]).strftime("%y%m%d")
    except ValueError:
        return datetime.now().strftime("%y%m%d")


def _meeting_date_iso(info: MeetingInfo, fallback: str | None) -> str | None:
    if info.meeting_date:
        # PF often returns ISO datetime
        try:
            return datetime.fromisoformat(info.meeting_date.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            try:
                return _parse_date(info.meeting_date.split("T")[0])
            except ValueError:
                pass
    return fallback


def _write_text(path: Path, content: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content if content.endswith("\n") else content + "\n"
    path.write_text(data, encoding="utf-8")
    return len(data.encode("utf-8"))


def _save(
    report: DownloadReport,
    *,
    kind: str,
    meeting: MeetingInfo,
    out_dir: Path,
    stamp: str,
    content: str,
) -> Path:
    filename = f"{stamp}_{_slug(meeting.track)}_{meeting.meeting_id}_{kind}.csv"
    path = out_dir / filename
    size = _write_text(path, content)
    report.files.append(
        DownloadItem(
            kind=kind,
            meeting_id=meeting.meeting_id,
            track=meeting.track,
            path=str(path),
            bytes=size,
            ok=True,
        )
    )
    return path


def download_meetings(
    *,
    meeting_date: str | None = None,
    meeting_ids: list[int] | None = None,
    track: str | None = None,
    out_dir: str | Path = "data/inbox",
    api_key: str | None = None,
    include_form: bool = True,
    include_meeting: bool = False,
    include_results: bool = True,
    include_ratings: bool = False,
    include_sectionals: bool = False,
    include_barrier_trials: bool = False,
    stage: str = "A",
    client: PuntingFormClient | None = None,
) -> DownloadReport:
    """
    Download Punting Form CSVs into out_dir.

    Default set matches RaceDNA importers: form CSV + results CSV.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    client = client or PuntingFormClient(api_key=api_key)

    iso_date = _parse_date(meeting_date) if meeting_date else None
    report = DownloadReport(date=iso_date, out_dir=str(out))

    meetings: list[MeetingInfo] = []
    if meeting_ids:
        for mid in meeting_ids:
            meetings.append(MeetingInfo(meeting_id=mid, track=track or "Meeting", meeting_date=iso_date))
    else:
        if not iso_date:
            raise ValueError("Provide --date and/or --meeting-id")
        meetings = client.meetings_list(
            iso_date,
            stage=stage,
            include_barrier_trials=include_barrier_trials,
        )

    if track:
        needle = track.lower()
        meetings = [m for m in meetings if needle in m.track.lower()]

    if not meetings:
        report.errors.append("No meetings matched")
        return report

    for meeting in meetings:
        m_date = _meeting_date_iso(meeting, iso_date)
        stamp = _date_stamp(m_date)
        report.meetings.append(
            {
                "meeting_id": meeting.meeting_id,
                "track": meeting.track,
                "meeting_date": m_date,
                "rail": meeting.rail,
                "expected_condition": meeting.expected_condition,
                "has_sectionals": meeting.has_sectionals,
            }
        )

        jobs: list[tuple[str, Callable[[], str]]] = []
        if include_form:
            jobs.append(("form", lambda m=meeting: client.download_form_csv(m.meeting_id)))
        if include_meeting:
            jobs.append(("meeting", lambda m=meeting: client.download_meeting_csv(m.meeting_id, stage=stage)))
        if include_results:
            jobs.append(("results", lambda m=meeting: client.download_results_csv(m.meeting_id)))
        if include_ratings:
            jobs.append(("ratings", lambda m=meeting: client.download_ratings_csv(m.meeting_id)))
        if include_sectionals:
            jobs.append(("sectionals", lambda m=meeting: client.download_sectionals_csv(m.meeting_id)))

        for kind, fetcher in jobs:
            try:
                content = fetcher()
                if not content or not content.strip():
                    raise PuntingFormError(f"Empty {kind} response")
                # Results before jump-out can be empty-ish / error JSON
                if content.lstrip().startswith("{") and "error" in content.lower():
                    raise PuntingFormError(content[:240])
                _save(report, kind=kind, meeting=meeting, out_dir=out, stamp=stamp, content=content)
            except Exception as exc:  # noqa: BLE001 - collect per-file errors
                msg = f"{meeting.track} ({meeting.meeting_id}) {kind}: {exc}"
                report.errors.append(msg)
                report.files.append(
                    DownloadItem(
                        kind=kind,
                        meeting_id=meeting.meeting_id,
                        track=meeting.track,
                        path="",
                        bytes=0,
                        ok=False,
                        error=str(exc),
                    )
                )
    return report


def import_downloaded(report: DownloadReport, db_path: str = "data/racedna.db") -> list[dict]:
    """Import any successfully downloaded form/results files into the DB."""
    from racedna.db import connect, init_db
    from racedna.import_meeting import import_meeting
    from racedna.import_results import import_results

    conn = connect(db_path)
    init_db(conn)
    imported: list[dict] = []
    for item in report.files:
        if not item.ok or not item.path:
            continue
        path = Path(item.path)
        if item.kind in {"form", "meeting"}:
            stats = import_meeting(conn, path)
            imported.append({"file": item.path, "type": "meeting", **stats})
        elif item.kind == "results":
            stats = import_results(conn, path)
            imported.append({"file": item.path, "type": "results", **stats})
    return imported
