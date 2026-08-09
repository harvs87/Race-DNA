from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE_URL = "https://api.puntingform.com.au"

# Starter+ CSV endpoints
PATH_MEETINGS_LIST = "/v2/form/meetingslist"
PATH_MEETING_CSV = "/v2/form/meeting/csv"
PATH_FORM_CSV = "/v2/form/form/csv"
PATH_RESULTS_CSV = "/v2/form/results/csv"
PATH_RATINGS_CSV = "/v2/Ratings/MeetingRatings/csv"
PATH_SECTIONALS_CSV = "/v2/Ratings/MeetingSectionals/csv"
PATH_CONDITIONS = "/v2/form/conditions"


class PuntingFormError(RuntimeError):
    pass


@dataclass
class MeetingInfo:
    meeting_id: int
    track: str
    meeting_date: str | None = None
    rail: str | None = None
    stage: str | None = None
    expected_condition: str | None = None
    has_sectionals: bool | None = None
    tab_meeting: bool | None = None
    raw: dict[str, Any] | None = None


def resolve_api_key(explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    for env_name in ("PUNTINGFORM_API_KEY", "PF_API_KEY", "RACEDNA_PF_API_KEY"):
        val = os.environ.get(env_name, "").strip()
        if val:
            return val
    candidates = [
        Path("data/puntingform.key"),
        Path("data/api_key"),
        Path.home() / ".config" / "racedna" / "api_key",
        Path.home() / ".puntingform_api_key",
    ]
    for path in candidates:
        if path.is_file():
            key = path.read_text(encoding="utf-8").strip()
            if key:
                return key
    raise PuntingFormError(
        "No Punting Form API key found. Set PUNTINGFORM_API_KEY or write the key to "
        "data/puntingform.key (Starter subscription required)."
    )


def _track_name(blob: dict[str, Any]) -> str:
    track = blob.get("track")
    if isinstance(track, dict):
        return str(track.get("name") or track.get("track") or track.get("trackName") or "Unknown")
    if isinstance(track, str) and track.strip():
        return track.strip()
    for key in ("trackName", "Track", "venue"):
        if blob.get(key):
            return str(blob[key])
    return "Unknown"


def _as_meeting(blob: dict[str, Any]) -> MeetingInfo | None:
    mid = blob.get("meetingId") or blob.get("MeetingId") or blob.get("meeting_id")
    if mid is None:
        return None
    try:
        meeting_id = int(str(mid).strip())
    except ValueError:
        return None
    return MeetingInfo(
        meeting_id=meeting_id,
        track=_track_name(blob),
        meeting_date=str(blob.get("meetingDate") or blob.get("MeetingDate") or "") or None,
        rail=(blob.get("railPosition") or blob.get("RailPosition")),
        stage=str(blob.get("stage") or "") or None,
        expected_condition=(blob.get("expectedCondition") or blob.get("ExpectedCondition")),
        has_sectionals=blob.get("hasSectionals"),
        tab_meeting=blob.get("tabMeeting"),
        raw=blob,
    )


def _extract_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("payLoad", "payload", "Payload", "data", "Data", "meetings", "Meetings", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            nested = _extract_list(value)
            if nested:
                return nested
    # single meeting object
    if "meetingId" in payload or "MeetingId" in payload:
        return [payload]
    return []


class PuntingFormClient:
    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL, timeout: float = 60.0):
        self.api_key = resolve_api_key(api_key)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        accept: str = "application/json",
    ) -> tuple[int, str, dict[str, str]]:
        query = dict(params or {})
        query["apiKey"] = self.api_key
        # drop Nones
        query = {k: v for k, v in query.items() if v is not None}
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(query)}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": accept,
                "User-Agent": "RaceDNA/0.2 (+local; puntingform downloader)",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                headers = {k.lower(): v for k, v in resp.headers.items()}
                return resp.status, body, headers
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise PuntingFormError(
                f"Punting Form API HTTP {exc.code} for {path}: {detail[:300]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise PuntingFormError(f"Punting Form API network error for {path}: {exc}") from exc

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        _, body, _ = self._request(path, params=params, accept="application/json")
        if not body.strip():
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise PuntingFormError(f"Invalid JSON from {path}: {body[:200]}") from exc

    def get_csv(self, path: str, params: dict[str, Any] | None = None) -> str:
        _, body, _ = self._request(path, params=params, accept="text/plain")
        return body

    def meetings_list(
        self,
        meeting_date: str,
        stage: str | None = "A",
        include_barrier_trials: bool = False,
    ) -> list[MeetingInfo]:
        data = self.get_json(
            PATH_MEETINGS_LIST,
            {
                "meetingDate": meeting_date,
                "stage": stage,
                "includeBarrierTrials": str(include_barrier_trials).lower(),
            },
        )
        meetings = []
        for blob in _extract_list(data):
            info = _as_meeting(blob)
            if info:
                meetings.append(info)
        return meetings

    def download_form_csv(self, meeting_id: int, race_number: int = 0, runs: int = 10) -> str:
        return self.get_csv(
            PATH_FORM_CSV,
            {"meetingId": meeting_id, "raceNumber": race_number, "runs": runs},
        )

    def download_meeting_csv(self, meeting_id: int, stage: str = "A") -> str:
        return self.get_csv(PATH_MEETING_CSV, {"meetingId": meeting_id, "stage": stage})

    def download_results_csv(self, meeting_id: int, race_number: int = 0) -> str:
        return self.get_csv(
            PATH_RESULTS_CSV,
            {"meetingId": meeting_id, "raceNumber": race_number},
        )

    def download_ratings_csv(self, meeting_id: int) -> str:
        return self.get_csv(PATH_RATINGS_CSV, {"meetingId": meeting_id})

    def download_sectionals_csv(self, meeting_id: int) -> str:
        return self.get_csv(PATH_SECTIONALS_CSV, {"meetingId": meeting_id})
