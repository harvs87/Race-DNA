from __future__ import annotations

import re
from datetime import datetime
from typing import Any


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_int(value: Any) -> int | None:
    text = clean(value)
    if text is None:
        return None
    try:
        return int(float(text.replace(",", "")))
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    text = clean(value)
    if text is None:
        return None
    text = text.replace("$", "").replace(",", "").replace(" ", "")
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(value: Any) -> str | None:
    text = clean(value)
    if text is None:
        return None
    # Strip time portion noise
    candidates = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%d-%b-%Y %H:%M",
        "%d-%b-%Y",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%d/%m/%y",
    ]
    for fmt in candidates:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    # last resort: first token dd/mm/yy
    token = text.split()[0]
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(token, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def parse_record(value: Any) -> dict[str, int | None]:
    """Parse strings like '33:6-5-6' into starts/wins/seconds/thirds."""
    text = clean(value)
    empty = {"starts": None, "wins": None, "seconds": None, "thirds": None}
    if not text:
        return empty
    m = re.match(r"(\d+)\s*:\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)", text)
    if not m:
        return empty
    return {
        "starts": int(m.group(1)),
        "wins": int(m.group(2)),
        "seconds": int(m.group(3)),
        "thirds": int(m.group(4)),
    }


def win_rate(record: dict[str, int | None]) -> float | None:
    starts = record.get("starts") or 0
    wins = record.get("wins") or 0
    if starts <= 0:
        return None
    return wins / starts


def place_rate(record: dict[str, int | None]) -> float | None:
    starts = record.get("starts") or 0
    if starts <= 0:
        return None
    placed = (record.get("wins") or 0) + (record.get("seconds") or 0) + (record.get("thirds") or 0)
    return placed / starts


SECTIONAL_RE = re.compile(
    r"(?P<time>\d+(?:\.\d+)?)\s*sec(?:onds?)?\s*(?P<dist>\d+)\s*m",
    re.IGNORECASE,
)


def parse_sectional(value: Any) -> tuple[float | None, int | None]:
    text = clean(value)
    if not text:
        return None, None
    m = SECTIONAL_RE.search(text)
    if not m:
        # bare number
        num = parse_float(text)
        return num, None
    seconds = float(m.group("time"))
    if seconds <= 0:
        return None, int(m.group("dist"))
    return seconds, int(m.group("dist"))


def condition_bucket(value: Any) -> str | None:
    text = clean(value)
    if not text:
        return None
    upper = text.upper()
    for key in ("FIRM", "GOOD", "SOFT", "HEAVY", "SYN"):
        if key in upper or (key == "SYN" and "SYNTHETIC" in upper):
            return "SYNTHETIC" if key == "SYN" else key.title()
    return text


def normalize_header(name: str) -> str:
    return name.strip().lower()
