from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from racedna.parsers import parse_date, parse_float, parse_int


PACE_WORDS = ("V.FAST", "VFAST", "FAST", "EVEN", "SLOW", "V.SLOW", "VSLOW")
RUN_STYLE_RE = re.compile(
    r"(?P<style>Leader|On[\s_-]?Pace(?:[_\s-]?Midfield)?|Midfield|Off[\s_-]?Pace|Back|"
    r"OnPace_Midfield|Settle)\s*(?:[\(-]\s*Settle\s*[-:]?\s*(?P<settle>\d+)\s*[\)]?)?",
    re.IGNORECASE,
)
HORSE_LINE_RE = re.compile(
    r"^(?:#?\d+\s+)?(?P<name>[A-Z][A-Za-z0-9'\- ]{1,40})$"
)
PEDIGREE_RE = re.compile(
    r"(?P<age>\d+)yo\b.*?\b(?:by\s+(?P<sire>[A-Za-z0-9'\- ]+?)\s*[-–]\s*(?P<dam>[A-Za-z0-9'\- ]+))?",
    re.IGNORECASE,
)


@dataclass
class SectionalRow:
    form_date: str | None = None
    track: str | None = None
    barrier: int | None = None
    rail: str | None = None
    distance: int | None = None
    margin: float | None = None
    finish_pos: int | None = None
    finish_time: str | None = None
    split_to6: int | None = None
    split_12_10: int | None = None
    split_10_8: int | None = None
    split_8_6: int | None = None
    split_6_4: int | None = None
    split_4_2: int | None = None
    split_2_f: int | None = None
    l12: float | None = None
    l10: float | None = None
    l8: float | None = None
    l6: float | None = None
    l4: float | None = None
    l2: float | None = None
    early_pace_runner: str | None = None
    early_pace_race: str | None = None
    bmark_runner_fin: float | None = None
    raw_line: str | None = None


@dataclass
class SectionalHorsePage:
    horse_name: str | None = None
    run_style: str | None = None
    settle: int | None = None
    age: int | None = None
    sire: str | None = None
    dam: str | None = None
    rows: list[SectionalRow] = field(default_factory=list)
    source: str | None = None
    ocr_text: str | None = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        return payload


def _norm_pace(token: str) -> str:
    t = token.upper().replace(" ", "")
    mapping = {
        "V.FAST": "V.Fast",
        "VFAST": "V.Fast",
        "FAST": "Fast",
        "EVEN": "Even",
        "SLOW": "Slow",
        "V.SLOW": "V.Slow",
        "VSLOW": "V.Slow",
    }
    return mapping.get(t, token.title())


def _extract_paces(line: str) -> tuple[str | None, str | None, str]:
    found: list[str] = []
    leftover = line
    for word in PACE_WORDS:
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        if pattern.search(leftover):
            found.append(_norm_pace(word))
            leftover = pattern.sub(" ", leftover, count=1)
    runner = found[0] if found else None
    race = found[1] if len(found) > 1 else None
    return runner, race, leftover


def parse_pipe_row(line: str) -> SectionalRow | None:
    """Canonical pipe format used by .sectional.txt fixtures."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 8:
        return None
    # date|track|bar|rail|dist|margin|to6|12-10|10-8|8-6|6-4|4-2|2-f|pos|time|l12|l10|l8|l6|l4|l2|pace_r|pace_race
    while len(parts) < 23:
        parts.append("")
    return SectionalRow(
        form_date=parse_date(parts[0]),
        track=parts[1] or None,
        barrier=parse_int(parts[2]),
        rail=parts[3] or None,
        distance=parse_int(parts[4]),
        margin=parse_float(parts[5]),
        split_to6=parse_int(parts[6]),
        split_12_10=parse_int(parts[7]),
        split_10_8=parse_int(parts[8]),
        split_8_6=parse_int(parts[9]),
        split_6_4=parse_int(parts[10]),
        split_4_2=parse_int(parts[11]),
        split_2_f=parse_int(parts[12]),
        finish_pos=parse_int(parts[13]),
        finish_time=parts[14] or None,
        l12=parse_float(parts[15]),
        l10=parse_float(parts[16]),
        l8=parse_float(parts[17]),
        l6=parse_float(parts[18]),
        l4=parse_float(parts[19]),
        l2=parse_float(parts[20]),
        early_pace_runner=parts[21] or None,
        early_pace_race=parts[22] or None,
        raw_line=line,
    )


def parse_ocr_row(line: str) -> SectionalRow | None:
    """Best-effort parse of a noisy OCR sectional table line."""
    raw = " ".join(line.strip().split())
    if not raw or len(raw) < 12:
        return None
    lower = raw.lower()
    if any(x in lower for x in ("sectional", "benchmark", "split rank", "early pace", "200m")):
        return None

    pace_runner, pace_race, cleaned = _extract_paces(raw)
    # Date at start: 26/07/26 or 2026-07-26
    date_m = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b", cleaned)
    if not date_m:
        return None
    form_date = parse_date(date_m.group(1))
    after_date = cleaned[date_m.end() :].strip()

    # Track token: letters / short code before first number cluster
    track_m = re.match(r"([A-Za-z][A-Za-z0-9&'./\- ]{1,30}?)(?=\s+\d)", after_date)
    track = track_m.group(1).strip() if track_m else None
    rest = after_date[track_m.end() :].strip() if track_m else after_date

    # Race time like 1:12.34 or 01:12.34
    time_m = re.search(r"\b(\d{1,2}:\d{2}\.\d{1,2})\b", rest)
    finish_time = time_m.group(1) if time_m else None
    if time_m:
        rest = (rest[: time_m.start()] + " " + rest[time_m.end() :]).strip()

    # Rail like +3, +6m, True
    rail = None
    rail_m = re.search(r"([Tt]rue|[Oo]ut|[Ii]n|[+-]\d+(?:\.\d+)?m?)", rest)
    if rail_m:
        rail = rail_m.group(1)
        rest = (rest[: rail_m.start()] + " " + rest[rail_m.end() :]).strip()

    numbers = re.findall(r"-?\d+(?:\.\d+)?", rest)
    if len(numbers) < 5:
        return None

    # Heuristic packing:
    # barrier, distance(~800-3600), margin, 7 split ranks, finish pos, then L sectionals floats
    barrier = parse_int(numbers[0])
    distance = None
    margin = None
    idx = 1
    for i, num in enumerate(numbers[1:4], start=1):
        val = float(num)
        if distance is None and 800 <= val <= 4000 and val.is_integer():
            distance = int(val)
            idx = i + 1
            break
    if distance is None and len(numbers) > 2:
        # sometimes OCR drops dist; leave none
        idx = 1

    if idx < len(numbers):
        # next is often margin
        maybe_margin = float(numbers[idx])
        if maybe_margin < 80:  # margins aren't huge usually
            margin = maybe_margin
            idx += 1

    split_vals: list[int | None] = []
    while idx < len(numbers) and len(split_vals) < 7:
        val = float(numbers[idx])
        if val.is_integer() and 1 <= int(val) <= 24:
            split_vals.append(int(val))
            idx += 1
        else:
            break
    while len(split_vals) < 7:
        split_vals.append(None)

    finish_pos = None
    if idx < len(numbers):
        val = float(numbers[idx])
        if val.is_integer() and 1 <= int(val) <= 24:
            finish_pos = int(val)
            idx += 1

    sectionals: list[float | None] = []
    while idx < len(numbers) and len(sectionals) < 6:
        val = float(numbers[idx])
        # sectional seconds typically 10-80
        if 9.0 <= val <= 90.0:
            sectionals.append(val)
            idx += 1
        else:
            idx += 1
            continue
    while len(sectionals) < 6:
        sectionals.append(None)

    # Prefer last float near end as bmark if leftover small magnitude
    bmark = None
    if idx < len(numbers):
        leftover = float(numbers[-1])
        if abs(leftover) <= 20:
            bmark = leftover

    # If finish pos still missing, use last split-like int already consumed? keep none.

    return SectionalRow(
        form_date=form_date,
        track=track,
        barrier=barrier,
        rail=rail,
        distance=distance,
        margin=margin,
        finish_pos=finish_pos,
        finish_time=finish_time,
        split_to6=split_vals[0],
        split_12_10=split_vals[1],
        split_10_8=split_vals[2],
        split_8_6=split_vals[3],
        split_6_4=split_vals[4],
        split_4_2=split_vals[5],
        split_2_f=split_vals[6],
        l12=sectionals[0],
        l10=sectionals[1],
        l8=sectionals[2],
        l6=sectionals[3],
        l4=sectionals[4],
        l2=sectionals[5],
        early_pace_runner=pace_runner,
        early_pace_race=pace_race,
        bmark_runner_fin=bmark,
        raw_line=raw,
    )


def parse_sectional_text(text: str, source: str | None = None) -> SectionalHorsePage:
    page = SectionalHorsePage(source=source, ocr_text=text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # Structured header keys
    for line in lines:
        if ":" in line:
            key, _, val = line.partition(":")
            key_u = key.strip().upper()
            val = val.strip()
            if key_u in {"HORSE", "HORSE_NAME", "NAME"} and val:
                page.horse_name = val
            elif key_u in {"RUN_STYLE", "RUN STYLE", "STYLE"} and val:
                page.run_style = val
                sm = re.search(r"Settle\s*[-:]?\s*(\d+)", val, re.I)
                if sm:
                    page.settle = int(sm.group(1))
            elif key_u == "SETTLE" and val:
                page.settle = parse_int(val)

    # Free-text header cues
    for line in lines[:25]:
        style_m = RUN_STYLE_RE.search(line)
        if style_m and not page.run_style:
            page.run_style = style_m.group(0).strip()
            if style_m.group("settle"):
                page.settle = int(style_m.group("settle"))
        ped = PEDIGREE_RE.search(line)
        if ped:
            page.age = parse_int(ped.group("age"))
            if ped.group("sire"):
                page.sire = ped.group("sire").strip()
            if ped.group("dam"):
                page.dam = ped.group("dam").strip()

    if not page.horse_name:
        # Prefer a titled name line near the top, skipping obvious labels
        skip = {
            "sectionals",
            "sectional analysis",
            "form guide",
            "punting form",
            "trainer",
            "jockey",
            "career",
        }
        for line in lines[:30]:
            if line.lower() in skip:
                continue
            if RUN_STYLE_RE.search(line) or PEDIGREE_RE.search(line):
                continue
            if re.search(r"\d", line) and "yo" not in line.lower():
                continue
            m = HORSE_LINE_RE.match(line)
            if m:
                name = m.group("name").strip()
                if name.lower() not in skip and len(name) >= 3:
                    page.horse_name = name
                    break

    for line in lines:
        if line.startswith("#") or line.upper().startswith("HORSE"):
            continue
        if "|" in line and re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}", line):
            row = parse_pipe_row(line)
        else:
            row = parse_ocr_row(line)
        if row and (row.form_date or row.distance or row.l6 or row.split_2_f):
            page.rows.append(row)

    return page


def parse_sectional_json(path: str | Path) -> SectionalHorsePage:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    page = SectionalHorsePage(
        horse_name=data.get("horse_name") or data.get("horse"),
        run_style=data.get("run_style"),
        settle=parse_int(data.get("settle")),
        age=parse_int(data.get("age")),
        sire=data.get("sire"),
        dam=data.get("dam"),
        source=str(path),
    )
    if page.run_style and page.settle is None:
        sm = re.search(r"Settle\s*[-:]?\s*(\d+)", page.run_style, re.I)
        if sm:
            page.settle = int(sm.group(1))
    for item in data.get("rows", []):
        if isinstance(item, str):
            row = parse_pipe_row(item) or parse_ocr_row(item)
        else:
            row = SectionalRow(
                form_date=parse_date(item.get("form_date") or item.get("date")),
                track=item.get("track"),
                barrier=parse_int(item.get("barrier")),
                rail=item.get("rail"),
                distance=parse_int(item.get("distance")),
                margin=parse_float(item.get("margin")),
                finish_pos=parse_int(item.get("finish_pos") or item.get("position")),
                finish_time=item.get("finish_time") or item.get("time"),
                split_to6=parse_int(item.get("split_to6") or item.get("to6")),
                split_12_10=parse_int(item.get("split_12_10")),
                split_10_8=parse_int(item.get("split_10_8")),
                split_8_6=parse_int(item.get("split_8_6")),
                split_6_4=parse_int(item.get("split_6_4")),
                split_4_2=parse_int(item.get("split_4_2")),
                split_2_f=parse_int(item.get("split_2_f")),
                l12=parse_float(item.get("l12")),
                l10=parse_float(item.get("l10")),
                l8=parse_float(item.get("l8")),
                l6=parse_float(item.get("l6")),
                l4=parse_float(item.get("l4")),
                l2=parse_float(item.get("l2")),
                early_pace_runner=item.get("early_pace_runner") or item.get("pace_runner"),
                early_pace_race=item.get("early_pace_race") or item.get("pace_race"),
                bmark_runner_fin=parse_float(item.get("bmark_runner_fin")),
                raw_line=json.dumps(item),
            )
        if row:
            page.rows.append(row)
    return page
