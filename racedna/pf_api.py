"""Punting Form official API client (sectionals + benchmarks).

Uses https://api.puntingform.com.au — Modeller / commercial subscriptions only.
Does not scrape the website UI.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

BASE_URL = "https://api.puntingform.com.au"
DEFAULT_KEY_PATHS = (
    Path("data/puntingform_api_key"),
    Path(".puntingform_api_key"),
    Path.home() / ".racedna" / "puntingform_api_key",
)


class PfApiError(RuntimeError):
    """Raised when the Punting Form API returns an error or unexpected payload."""


def resolve_api_key(explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    env = os.environ.get("PUNTINGFORM_API_KEY") or os.environ.get("PF_API_KEY")
    if env and env.strip():
        return env.strip()
    for path in DEFAULT_KEY_PATHS:
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text
    raise PfApiError(
        "Missing Punting Form API key. Set PUNTINGFORM_API_KEY, pass --api-key, "
        "or create data/puntingform_api_key. Sectionals/benchmarks require a "
        "Modeller or commercial subscription."
    )


def _http_get(
    url: str,
    *,
    accept: str = "application/json",
    opener: Callable[..., Any] | None = None,
) -> tuple[int, str, str]:
    """Return (status, body_text, content_type)."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": "RaceDNA/0.2 (+personal; official PF API client)",
        },
        method="GET",
    )
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            ctype = resp.headers.get_content_type() or accept
            return resp.status, raw.decode(charset, errors="replace"), ctype
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise PfApiError(f"PF API HTTP {exc.code} for {url}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise PfApiError(f"PF API network error for {url}: {exc.reason}") from exc


def _build_url(path: str, *, meeting_id: int, api_key: str) -> str:
    qs = urllib.parse.urlencode({"meetingId": int(meeting_id), "apiKey": api_key})
    return f"{BASE_URL}{path}?{qs}"


def _unwrap_payload(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    for key in ("payLoad", "payload", "Payload", "data", "Data"):
        if key in data and data[key] is not None:
            return data[key]
    # Some responses may already be the list/object
    if "statusCode" in data or "status" in data:
        err = data.get("error") or data.get("errors")
        if err:
            raise PfApiError(f"PF API error payload: {err}")
    return data


def fetch_json(
    path: str,
    *,
    meeting_id: int,
    api_key: str,
    opener: Callable[..., Any] | None = None,
) -> Any:
    url = _build_url(path, meeting_id=meeting_id, api_key=api_key)
    status, body, _ctype = _http_get(url, accept="application/json", opener=opener)
    if status != 200:
        raise PfApiError(f"PF API unexpected status {status} for {path}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise PfApiError(f"PF API returned non-JSON for {path}: {body[:200]}") from exc
    if isinstance(data, dict):
        err = data.get("error")
        status_code = data.get("statusCode")
        # PF uses statusCode 200 / status enum; treat explicit error strings as failures
        if err:
            raise PfApiError(f"PF API error for {path}: {err}")
        if status_code not in (None, 200, 0) and data.get("payLoad") is None and data.get("payload") is None:
            raise PfApiError(f"PF API statusCode={status_code} for {path}: {body[:300]}")
    return _unwrap_payload(data)


def fetch_csv(
    path: str,
    *,
    meeting_id: int,
    api_key: str,
    opener: Callable[..., Any] | None = None,
) -> str:
    url = _build_url(path, meeting_id=meeting_id, api_key=api_key)
    status, body, _ctype = _http_get(url, accept="text/plain", opener=opener)
    if status != 200:
        raise PfApiError(f"PF API unexpected status {status} for {path}")
    # JSON error wrapped as text
    stripped = body.lstrip()
    if stripped.startswith("{") and '"error"' in stripped[:400].lower():
        try:
            data = json.loads(body)
            if data.get("error"):
                raise PfApiError(f"PF API error for {path}: {data.get('error')}")
        except json.JSONDecodeError:
            pass
    return body


def fetch_meeting_sectionals(
    meeting_id: int,
    *,
    api_key: str | None = None,
    as_csv: bool = False,
    opener: Callable[..., Any] | None = None,
) -> Any:
    key = resolve_api_key(api_key)
    if as_csv:
        return fetch_csv(
            "/v2/Ratings/MeetingSectionals/csv",
            meeting_id=meeting_id,
            api_key=key,
            opener=opener,
        )
    return fetch_json(
        "/v2/Ratings/MeetingSectionals",
        meeting_id=meeting_id,
        api_key=key,
        opener=opener,
    )


def fetch_meeting_benchmarks(
    meeting_id: int,
    *,
    api_key: str | None = None,
    as_csv: bool = False,
    opener: Callable[..., Any] | None = None,
) -> Any:
    key = resolve_api_key(api_key)
    if as_csv:
        return fetch_csv(
            "/v2/Ratings/MeetingBenchmarks/csv",
            meeting_id=meeting_id,
            api_key=key,
            opener=opener,
        )
    return fetch_json(
        "/v2/Ratings/MeetingBenchmarks",
        meeting_id=meeting_id,
        api_key=key,
        opener=opener,
    )


def save_download(
    payload: Any,
    path: str | Path,
    *,
    as_csv: bool = False,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if as_csv:
        path.write_text(str(payload), encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def default_download_paths(meeting_id: int, out_dir: str | Path = "data/inbox/pf") -> dict[str, Path]:
    out = Path(out_dir)
    return {
        "sectionals_json": out / f"{meeting_id}_sectionals.json",
        "sectionals_csv": out / f"{meeting_id}_sectionals.csv",
        "benchmarks_json": out / f"{meeting_id}_benchmarks.json",
        "benchmarks_csv": out / f"{meeting_id}_benchmarks.csv",
    }
