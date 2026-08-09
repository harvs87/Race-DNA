from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime

from racedna.parsers import condition_bucket, parse_record, place_rate, win_rate


@dataclass
class Tip:
    race_number: int
    race_name: str | None
    tab_no: int | None
    horse: str
    jockey: str | None
    trainer: str | None
    barrier: int | None
    score: float
    reasons: list[str] = field(default_factory=list)
    result_position: int | None = None
    result_price: float | None = None


WET = {"Soft", "Heavy"}
DRY = {"Firm", "Good"}


def _parse_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _class_rank(text: str | None) -> int | None:
    """Higher = stronger class. Rough ladder for Aus metro/provincial."""
    if not text:
        return None
    t = text.lower()
    if "group 1" in t or re.search(r"\bg1\b", t):
        return 100
    if "group 2" in t or re.search(r"\bg2\b", t):
        return 90
    if "group 3" in t or re.search(r"\bg3\b", t):
        return 80
    if "listed" in t:
        return 70
    if "open" in t:
        return 65
    m = re.search(r"(?:benchmark|bench\.?|bm)\s*(\d+)", t)
    if m:
        return 40 + int(m.group(1)) // 2
    if "maiden" in t:
        return 10
    if "class 1" in t or "cl1" in t:
        return 25
    if "class 2" in t or "cl2" in t:
        return 30
    return 35


def infer_meeting_going(conn: sqlite3.Connection, meeting_id: int) -> str | None:
    rows = conn.execute(
        """
        SELECT track_condition, COUNT(*) AS c
        FROM races
        WHERE meeting_id = ? AND track_condition IS NOT NULL AND track_condition != ''
        GROUP BY track_condition
        ORDER BY c DESC
        """,
        (meeting_id,),
    ).fetchall()
    if not rows:
        return None
    return condition_bucket(rows[0]["track_condition"])


def _barrier_score(
    barrier: int | None,
    field_size: int,
    going: str | None,
    distance: int | None,
) -> tuple[float, str | None]:
    if barrier is None:
        return 0.0, None

    # Soft/rail-out style meetings historically punish wide runners more.
    wet = going in WET
    sprint = distance is not None and distance <= 1200
    pts = 0.0

    if barrier <= 3:
        pts = 2.2 if wet else 1.2
        if sprint:
            pts += 0.6
    elif barrier <= 7:
        pts = 0.8 if wet else 0.4
    elif barrier <= 11:
        pts = -2.0 if wet else -0.8
        if field_size >= 12:
            pts -= 0.8
    else:
        pts = -3.5 if wet else -1.8
        if field_size >= 12:
            pts -= 1.0

    label = f"barrier {barrier} on {going or 'unknown'} ({pts:+.1f})"
    return pts, label


def _freshness_score(
    form_rows: list[sqlite3.Row],
    meeting_date: str | None,
    runner: sqlite3.Row,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    pts = 0.0
    meet_dt = _parse_iso(meeting_date)
    last_dt = None
    for row in form_rows:
        last_dt = _parse_iso(row["form_date"])
        if last_dt:
            break
    if meet_dt and last_dt:
        days = (meet_dt - last_dt).days
        if days < 0:
            days = 0
        if days <= 6:
            pts -= 1.5
            reasons.append(f"quick backup {days}d (-1.5)")
        elif 10 <= days <= 28:
            pts += 2.0
            reasons.append(f"ideal spacing {days}d (+2.0)")
        elif 29 <= days <= 56:
            pts += 0.5
            reasons.append(f"spacing {days}d (+0.5)")
        elif days >= 60:
            first_up = parse_record(runner["record_first_up"])
            fu_wr = win_rate(first_up)
            fu_pr = place_rate(first_up)
            if fu_wr is not None and (first_up.get("starts") or 0) >= 2:
                bonus = fu_wr * 14
                pts += bonus
                reasons.append(f"spell {days}d first-up WR {fu_wr:.0%} (+{bonus:.1f})")
            elif fu_pr is not None:
                bonus = fu_pr * 6
                pts += bonus
                reasons.append(f"spell {days}d first-up PR {fu_pr:.0%} (+{bonus:.1f})")
            else:
                pts -= 1.0
                reasons.append(f"spell {days}d unknown first-up (-1.0)")
    else:
        last10 = (runner["last10"] or "").lower()
        if last10.startswith("x") or (len(last10) > 1 and last10[1] == "x"):
            first_up = parse_record(runner["record_first_up"])
            fu_wr = win_rate(first_up)
            if fu_wr is not None:
                bonus = fu_wr * 10
                pts += bonus
                reasons.append(f"first-up WR {fu_wr:.0%} (+{bonus:.1f})")
    return pts, reasons


def _going_form_score(
    form_rows: list[sqlite3.Row],
    runner: sqlite3.Row,
    going: str | None,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    pts = 0.0
    if not going:
        return pts, reasons

    # Career going record — situational, higher weight than raw career.
    key = {
        "Firm": "record_firm",
        "Good": "record_good",
        "Soft": "record_soft",
        "Heavy": "record_heavy",
        "Synthetic": "record_synthetic",
    }.get(going)
    if key and runner[key]:
        going_rec = parse_record(runner[key])
        starts = going_rec.get("starts") or 0
        gw = win_rate(going_rec)
        gp = place_rate(going_rec)
        if starts >= 2 and gw is not None:
            bonus = gw * 22
            pts += bonus
            reasons.append(f"{going} career WR {gw:.0%} ({starts}st) (+{bonus:.1f})")
        elif starts >= 2 and gp is not None:
            bonus = gp * 10
            pts += bonus
            reasons.append(f"{going} career PR {gp:.0%} ({starts}st) (+{bonus:.1f})")
        elif starts == 0 and going in WET:
            pts -= 1.5
            reasons.append(f"no {going} record (-1.5)")

    # Wet specialist: strong soft/heavy, weak dry.
    if going in WET:
        soft = parse_record(runner["record_soft"])
        heavy = parse_record(runner["record_heavy"])
        good = parse_record(runner["record_good"])
        wet_starts = (soft.get("starts") or 0) + (heavy.get("starts") or 0)
        wet_wins = (soft.get("wins") or 0) + (heavy.get("wins") or 0)
        good_wr = win_rate(good)
        if wet_starts >= 3:
            wet_wr = wet_wins / wet_starts
            if wet_wr >= 0.25 and (good_wr is None or wet_wr >= (good_wr + 0.08)):
                pts += 4.0
                reasons.append(f"wet specialist wetWR {wet_wr:.0%} (+4.0)")

    # Recent going-matched form lines
    matched = [
        r
        for r in form_rows
        if condition_bucket(r["condition"]) == going and r["position"] is not None
    ]
    if matched:
        recent = matched[:4]
        avg_pos = sum(r["position"] for r in recent) / len(recent)
        pos_pts = max(-2.0, min(8.0, 10.0 - avg_pos * 1.6))
        pts += pos_pts
        places = sum(1 for r in recent if r["position"] <= 3)
        pts += places * 1.8
        reasons.append(
            f"recent {going} form avg pos {avg_pos:.1f}, {places}p/{len(recent)} (+{pos_pts + places * 1.8:.1f})"
        )
    elif going in WET:
        # raced dry lately only
        dry_recent = [
            r
            for r in form_rows[:5]
            if condition_bucket(r["condition"]) in DRY and r["position"] is not None
        ]
        if len(dry_recent) >= 3:
            pts -= 1.0
            reasons.append("no recent wet form (-1.0)")

    return pts, reasons


def _track_distance_score(
    form_rows: list[sqlite3.Row],
    runner: sqlite3.Row,
    track: str,
    distance: int | None,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    pts = 0.0

    track_rec = parse_record(runner["record_track"])
    if (track_rec.get("starts") or 0) >= 2:
        tw = win_rate(track_rec) or 0.0
        tp = place_rate(track_rec) or 0.0
        bonus = tw * 16 + tp * 6
        pts += bonus
        reasons.append(
            f"{track} {track_rec['wins']}-{track_rec['seconds']}-{track_rec['thirds']}/"
            f"{track_rec['starts']} (+{bonus:.1f})"
        )
    elif (track_rec.get("starts") or 0) == 0:
        pts -= 0.8
        reasons.append(f"first look at {track} (-0.8)")

    td = parse_record(runner["record_track_distance"])
    if (td.get("starts") or 0) >= 2:
        tdw = win_rate(td) or 0.0
        bonus = tdw * 14
        pts += bonus
        reasons.append(f"track/dist WR {tdw:.0%} (+{bonus:.1f})")

    if distance:
        dist_rec = parse_record(runner["record_distance"])
        if (dist_rec.get("starts") or 0) >= 2:
            dw = win_rate(dist_rec) or 0.0
            bonus = dw * 10
            pts += bonus
            reasons.append(f"distance WR {dw:.0%} (+{bonus:.1f})")

        same_track = [
            r
            for r in form_rows
            if r["track"]
            and r["track"].lower() == track.lower()
            and r["position"] is not None
        ]
        if same_track:
            recent = same_track[:3]
            avg_pos = sum(r["position"] for r in recent) / len(recent)
            local_pts = max(-2.0, min(6.0, 8.0 - avg_pos * 1.5))
            pts += local_pts
            reasons.append(f"recent @ {track} avg pos {avg_pos:.1f} ({local_pts:+.1f})")

        near = [
            r
            for r in form_rows
            if r["distance"] is not None
            and abs(r["distance"] - distance) <= 100
            and r["position"] is not None
        ]
        if near:
            recent = near[:4]
            wins = sum(1 for r in recent if r["position"] == 1)
            places = sum(1 for r in recent if r["position"] <= 3)
            dist_pts = wins * 2.5 + places * 1.2
            pts += dist_pts
            reasons.append(f"dist±100 form {wins}w/{places}p (+{dist_pts:.1f})")

    return pts, reasons


def _recent_form_score(form_rows: list[sqlite3.Row], race_class: str | None) -> tuple[float, list[str]]:
    reasons: list[str] = []
    pts = 0.0
    if not form_rows:
        return -4.0, ["no form lines (-4.0)"]

    recent = [r for r in form_rows[:5] if r["position"] is not None]
    if not recent:
        return -3.0, ["form lines missing positions (-3.0)"]

    # Margin-aware competitiveness: close 4th better than beaten 10L 2nd? still reward places more.
    weighted = 0.0
    for i, r in enumerate(recent):
        decay = 1.0 - i * 0.12
        pos = r["position"]
        margin = r["margin"] if r["margin"] is not None else 3.0
        if pos == 1:
            piece = 5.0
        elif pos == 2:
            piece = 3.2 if margin <= 1.5 else 2.4
        elif pos == 3:
            piece = 2.2 if margin <= 2.0 else 1.6
        elif pos <= 5 and margin <= 2.5:
            piece = 1.4  # strong close-up
        elif pos <= 5:
            piece = 0.6
        else:
            piece = -0.8 if pos >= 9 else -0.3
        weighted += piece * decay
    pts += weighted
    avg_pos = sum(r["position"] for r in recent) / len(recent)
    reasons.append(f"recent competitive form avg pos {avg_pos:.1f} (+{weighted:.1f})")

    # Sectionals: only reward fast last-600 when horse finished competitively
    competitive = [r for r in recent if r["position"] <= 5]
    sectional_times = [
        r["sectional_time"]
        for r in competitive
        if r["sectional_time"] is not None and r["sectional_time"] > 0
    ]
    if sectional_times:
        avg_sec = sum(sectional_times) / len(sectional_times)
        sec_pts = max(-2.0, min(5.0, (35.2 - avg_sec) * 2.2))
        pts += sec_pts
        dist = competitive[0]["sectional_distance"] or 600
        reasons.append(f"closing L{dist} {avg_sec:.2f}s when competitive ({sec_pts:+.1f})")

    # Class move
    race_rank = _class_rank(race_class)
    form_ranks = [_class_rank(r["class_text"]) for r in recent if _class_rank(r["class_text"])]
    if race_rank is not None and form_ranks:
        avg_form_class = sum(form_ranks) / len(form_ranks)
        delta = avg_form_class - race_rank
        if delta >= 8:
            pts += 3.0
            reasons.append(f"class drop (+3.0)")
        elif delta <= -8:
            pts -= 2.0
            reasons.append(f"class rise (-2.0)")

    # Market honesty: shorties that bombed are a knock
    bombs = sum(
        1
        for r in recent
        if r["price"] is not None and r["price"] <= 3.5 and r["position"] is not None and r["position"] >= 7
    )
    if bombs:
        pts -= bombs * 2.0
        reasons.append(f"{bombs} short-price bomb(s) (-{bombs * 2.0:.1f})")

    return pts, reasons


def _career_base(runner: sqlite3.Row) -> tuple[float, list[str]]:
    """Light career prior — must not dominate situational signals."""
    reasons: list[str] = []
    career = parse_record(runner["record"])
    pts = 0.0
    wr = win_rate(career)
    pr = place_rate(career)
    starts = career.get("starts") or 0
    if wr is not None and starts >= 3:
        # shrink toward 10% with sample size
        shrink = starts / (starts + 8)
        adj = 0.10 + (wr - 0.10) * shrink
        bonus = adj * 10
        pts += bonus
        reasons.append(f"career prior WR~{adj:.0%} (+{bonus:.1f})")
    if pr is not None and starts >= 3:
        bonus = pr * 4
        pts += bonus
        reasons.append(f"career PR {pr:.0%} (+{bonus:.1f})")
    return pts, reasons


def _run_style_bucket(run_style: str | None, settle: int | None) -> str:
    text = (run_style or "").lower()
    if settle is not None:
        if settle <= 3:
            return "forward"
        if settle <= 7:
            return "mid"
        return "back"
    compact = text.replace(" ", "").replace("_", "").replace("-", "")
    if "leader" in compact or (compact.startswith("onpace") and "mid" not in compact):
        return "forward"
    if "onpacemid" in compact or "onpacemidfield" in compact:
        return "mid"
    if "back" in text or "off" in text:
        return "back"
    if "mid" in text:
        return "mid"
    return "unknown"


def _style_barrier_score(
    run_style: str | None,
    settle: int | None,
    barrier: int | None,
    going: str | None,
    field_size: int,
) -> tuple[float, list[str]]:
    style = _run_style_bucket(run_style, settle)
    if style == "unknown" or barrier is None:
        return 0.0, []
    pts = 0.0
    reasons: list[str] = []
    wet = going in WET
    if style == "forward" and barrier <= 4:
        pts += 2.5 if wet else 1.5
        reasons.append(f"forward map + inside gate ({pts:+.1f})")
    elif style == "forward" and barrier >= 10:
        pts -= 2.5 if wet else 1.5
        reasons.append(f"forward map from wide ({pts:+.1f})")
    elif style == "back" and barrier >= 10 and field_size >= 10:
        pts -= 1.2
        reasons.append("backmarker drawn wide (-1.2)")
    elif style == "mid" and 4 <= barrier <= 8:
        pts += 0.8
        reasons.append("midfield map + mid barrier (+0.8)")
    if settle is not None and run_style:
        reasons.insert(0, f"run style {run_style}")
    return pts, reasons


def _pf_ratings_score(rating: sqlite3.Row | None) -> tuple[float, list[str]]:
    """Score from MeetingRatings (Starter+): sectional time ranks + PF AI."""
    if rating is None:
        return 0.0, []
    reasons: list[str] = []
    pts = 0.0

    def _rank_pts(rank: int | None, label: str, weight: float) -> float:
        if rank is None or rank <= 0:
            return 0.0
        if rank == 1:
            bonus = 4.0 * weight
        elif rank == 2:
            bonus = 2.8 * weight
        elif rank == 3:
            bonus = 1.8 * weight
        elif rank <= 5:
            bonus = 0.8 * weight
        else:
            bonus = max(-1.5 * weight, (6 - rank) * 0.25 * weight)
        reasons.append(f"PF {label} rank #{rank} ({bonus:+.1f})")
        return bonus

    pts += _rank_pts(
        rating["last600_rank"] if "last600_rank" in rating.keys() else None,
        "L600",
        1.2,
    )
    pts += _rank_pts(
        rating["last200_rank"] if "last200_rank" in rating.keys() else None,
        "L200",
        1.0,
    )
    pts += _rank_pts(
        rating["last400_rank"] if "last400_rank" in rating.keys() else None,
        "L400",
        0.7,
    )
    pts += _rank_pts(
        rating["early_time_rank"] if "early_time_rank" in rating.keys() else None,
        "early",
        0.5,
    )
    pts += _rank_pts(
        rating["time_rank"] if "time_rank" in rating.keys() else None,
        "time",
        0.6,
    )

    pfai = rating["pfai_score"] if "pfai_score" in rating.keys() else None
    if pfai is not None and pfai > 0:
        # typical scores ~40-90; centre around 55
        ai_pts = max(-2.0, min(5.0, (float(pfai) - 55.0) / 6.0))
        pts += ai_pts
        reasons.append(f"PF AI score {float(pfai):.0f} ({ai_pts:+.1f})")

    style = rating["run_style"] if "run_style" in rating.keys() else None
    settle = rating["settle"] if "settle" in rating.keys() else None
    if style:
        reasons.append(f"PF run style {style}" + (f" settle {settle}" if settle else ""))

    return pts, reasons


def _pf_benchmark_score(bmark: sqlite3.Row | None) -> tuple[float, list[str]]:
    """Score from official PF MeetingBenchmarks (lengths vs par; higher = better)."""
    if bmark is None:
        return 0.0, []
    reasons: list[str] = []
    pts = 0.0

    finish = bmark["finish_all"] if "finish_all" in bmark.keys() else None
    last600 = bmark["last600_all"] if "last600_all" in bmark.keys() else None
    last200 = bmark["last200_all"] if "last200_all" in bmark.keys() else None
    finish_class = bmark["finish_class"] if "finish_class" in bmark.keys() else None

    # Benchmarks are in lengths; positive usually means faster than benchmark.
    if finish is not None:
        fin_pts = max(-4.0, min(8.0, float(finish) * 1.6))
        pts += fin_pts
        reasons.append(f"PF finish bmark {float(finish):+.2f}L ({fin_pts:+.1f})")
    if last600 is not None:
        l6_pts = max(-3.0, min(5.0, float(last600) * 1.3))
        pts += l6_pts
        reasons.append(f"PF L600 bmark {float(last600):+.2f}L ({l6_pts:+.1f})")
    if last200 is not None and float(last200) >= 0.3:
        pts += min(3.0, float(last200) * 1.1)
        reasons.append(f"PF L200 bmark {float(last200):+.2f}L")
    if finish_class is not None and float(finish_class) >= 0.5:
        pts += min(2.5, float(finish_class))
        reasons.append(f"PF class finish bmark {float(finish_class):+.2f}L")
    return pts, reasons


def _pf_meeting_sectional_score(sec: sqlite3.Row | None) -> tuple[float, list[str]]:
    """Light signal from prior meeting sectional ranks (post-race PF API rows)."""
    if sec is None:
        return 0.0, []
    reasons: list[str] = []
    pts = 0.0
    rank6 = sec["meeting_rank_6f"] if "meeting_rank_6f" in sec.keys() else None
    rank2 = sec["meeting_rank_2f"] if "meeting_rank_2f" in sec.keys() else None
    last600 = sec["last600"] if "last600" in sec.keys() else None
    if rank6 is not None and rank6 <= 3:
        pts += 2.0
        reasons.append(f"PF meeting L600 rank #{rank6}")
    if rank2 is not None and rank2 <= 3:
        pts += 1.5
        reasons.append(f"PF meeting L200 rank #{rank2}")
    if last600 is not None and last600 > 0:
        # Store as history enrichment only when competitive finish
        pos = sec["pos_fin"] if "pos_fin" in sec.keys() else None
        if pos is not None and pos <= 4 and last600 <= 34.8:
            pts += 1.2
            reasons.append(f"PF last sectional L600 {last600:.2f}s")
    return pts, reasons


def _sectional_screenshot_score(
    sectional_rows: list[sqlite3.Row],
    distance: int | None,
) -> tuple[float, list[str]]:
    if not sectional_rows:
        return 0.0, []
    reasons: list[str] = []
    pts = 0.0
    recent = sectional_rows[:4]

    # Closing pattern: improve rank from To6 / midrace into 2-F
    closes = 0
    for r in recent:
        early = r["split_to6"] if r["split_to6"] is not None else r["split_8_6"]
        late = r["split_2_f"] if r["split_2_f"] is not None else r["split_4_2"]
        if early is not None and late is not None and late + 2 <= early:
            closes += 1
    if closes:
        bonus = closes * 1.8
        pts += bonus
        reasons.append(f"sectional closer pattern {closes}/{len(recent)} (+{bonus:.1f})")

    # Peak late sectionals (L2/L4) when finishing in top 4
    l2s = [
        r["l2"]
        for r in recent
        if r["l2"] is not None and r["finish_pos"] is not None and r["finish_pos"] <= 4
    ]
    if l2s:
        avg_l2 = sum(l2s) / len(l2s)
        # Faster final 200 (~10.8-12.0) rewarded
        late_pts = max(-1.5, min(4.0, (11.8 - avg_l2) * 3.0))
        pts += late_pts
        reasons.append(f"avg L2 {avg_l2:.2f}s in competitive runs ({late_pts:+.1f})")

    l6s = [
        r["l6"]
        for r in recent
        if r["l6"] is not None and r["finish_pos"] is not None and r["finish_pos"] <= 5
    ]
    if l6s:
        avg_l6 = sum(l6s) / len(l6s)
        l6_pts = max(-2.0, min(4.5, (35.2 - avg_l6) * 2.0))
        pts += l6_pts
        reasons.append(f"screenshot L6 {avg_l6:.2f}s ({l6_pts:+.1f})")

    # Pace handling: placed when race pace was Fast/V.Fast
    fast_places = 0
    for r in recent:
        race_pace = (r["early_pace_race"] or "").lower()
        if "fast" in race_pace and r["finish_pos"] is not None and r["finish_pos"] <= 3:
            fast_places += 1
    if fast_places:
        pts += fast_places * 1.5
        reasons.append(f"handles fast pace ({fast_places}p) (+{fast_places * 1.5:.1f})")

    return pts, reasons


def _score_runner(
    runner: sqlite3.Row,
    form_rows: list[sqlite3.Row],
    sectional_rows: list[sqlite3.Row],
    *,
    track: str,
    meeting_date: str | None,
    going: str | None,
    distance: int | None,
    race_class: str | None,
    field_size: int,
    pf_benchmark: sqlite3.Row | None = None,
    pf_sectional: sqlite3.Row | None = None,
    pf_rating: sqlite3.Row | None = None,
) -> tuple[float, list[str]]:
    parts: list[tuple[float, list[str]]] = [
        _career_base(runner),
        _going_form_score(form_rows, runner, going),
        _track_distance_score(form_rows, runner, track, distance),
        _recent_form_score(form_rows, race_class),
        _freshness_score(form_rows, meeting_date, runner),
        _pf_ratings_score(pf_rating),
        _pf_benchmark_score(pf_benchmark),
        _pf_meeting_sectional_score(pf_sectional),
        _sectional_screenshot_score(sectional_rows, distance),
        _style_barrier_score(
            runner["run_style"] if "run_style" in runner.keys() else None,
            runner["settle"] if "settle" in runner.keys() else None,
            runner["barrier"],
            going,
            field_size,
        ),
    ]
    total = 0.0
    reasons: list[str] = []
    for pts, why in parts:
        total += pts
        reasons.extend(why)

    b_pts, b_why = _barrier_score(runner["barrier"], field_size, going, distance)
    total += b_pts
    if b_why:
        reasons.append(b_why)

    # Keep the most useful reasons, preferring situational ones.
    priority = (
        "soft",
        "heavy",
        "wet",
        "pf l600",
        "pf l200",
        "pf l400",
        "pf ai",
        "pf time",
        "pf early",
        "pf run style",
        "pf finish",
        "pf class",
        "pf meeting",
        "sectional",
        "l2",
        "l6",
        "run style",
        "forward",
        "barrier",
        "spell",
        "class",
        "track",
        "recent",
        "closing",
        "dist",
    )

    def _rank(text: str) -> int:
        low = text.lower()
        for i, key in enumerate(priority):
            if key in low:
                return i
        return len(priority)

    reasons = sorted(reasons, key=_rank)[:7]
    return total, reasons


def score_meeting(
    conn: sqlite3.Connection,
    track: str | None = None,
    meeting_date: str | None = None,
    meeting_id: int | None = None,
    going: str | None = None,
) -> list[Tip]:
    cur = conn.cursor()
    if meeting_id is None:
        if track and meeting_date:
            meeting = cur.execute(
                "SELECT * FROM meetings WHERE track = ? AND meeting_date = ?",
                (track, meeting_date),
            ).fetchone()
        else:
            meeting = cur.execute(
                "SELECT * FROM meetings ORDER BY meeting_date DESC, id DESC LIMIT 1"
            ).fetchone()
        if not meeting:
            raise ValueError("No meeting found in database")
        meeting_id = meeting["id"]
    else:
        meeting = cur.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not meeting:
            raise ValueError(f"Meeting {meeting_id} not found")

    meeting_going = condition_bucket(going) if going else infer_meeting_going(conn, meeting_id)

    races = cur.execute(
        "SELECT * FROM races WHERE meeting_id = ? ORDER BY race_number",
        (meeting_id,),
    ).fetchall()

    tips: list[Tip] = []
    for race in races:
        race_going = condition_bucket(race["track_condition"]) or meeting_going
        runners = cur.execute(
            """
            SELECT runners.*, horses.name AS horse_name,
                   horses.run_style AS run_style,
                   horses.settle AS settle,
                   results.position AS result_position,
                   results.price AS result_price
            FROM runners
            JOIN horses ON horses.id = runners.horse_id
            LEFT JOIN results ON results.runner_id = runners.id
            WHERE runners.race_id = ?
            ORDER BY runners.tab_no
            """,
            (race["id"],),
        ).fetchall()

        raw: list[tuple[float, list[str], sqlite3.Row]] = []
        for runner in runners:
            form_rows = cur.execute(
                """
                SELECT * FROM form_runs
                WHERE runner_id = ?
                ORDER BY form_date DESC, id DESC
                """,
                (runner["id"],),
            ).fetchall()
            sectional_rows = cur.execute(
                """
                SELECT * FROM sectional_runs
                WHERE horse_id = ?
                ORDER BY form_date DESC, id DESC
                """,
                (runner["horse_id"],),
            ).fetchall()
            pf_benchmark = cur.execute(
                """
                SELECT * FROM pf_benchmarks
                WHERE runner_id = ?
                   OR (race_id = ? AND tab_no = ?)
                ORDER BY
                    CASE WHEN runner_id = ? THEN 0 ELSE 1 END,
                    id DESC
                LIMIT 1
                """,
                (runner["id"], race["id"], runner["tab_no"], runner["id"]),
            ).fetchone()
            pf_rating = cur.execute(
                """
                SELECT * FROM pf_ratings
                WHERE runner_id = ?
                   OR (race_id = ? AND tab_no = ?)
                ORDER BY
                    CASE WHEN runner_id = ? THEN 0 ELSE 1 END,
                    id DESC
                LIMIT 1
                """,
                (runner["id"], race["id"], runner["tab_no"], runner["id"]),
            ).fetchone()
            # Prefer prior-meeting sectionals for this horse (not today's card)
            pf_sectional = cur.execute(
                """
                SELECT * FROM pf_sectionals
                WHERE horse_id = ?
                  AND (meeting_id IS NULL OR meeting_id != ?)
                ORDER BY form_date DESC, id DESC
                LIMIT 1
                """,
                (runner["horse_id"], meeting_id),
            ).fetchone()
            total, reasons = _score_runner(
                runner,
                form_rows,
                sectional_rows,
                track=meeting["track"],
                meeting_date=meeting["meeting_date"],
                going=race_going,
                distance=race["distance"],
                race_class=race["class_text"],
                field_size=len(runners),
                pf_benchmark=pf_benchmark,
                pf_sectional=pf_sectional,
                pf_rating=pf_rating,
            )
            raw.append((total, reasons, runner))

        # Race-relative: don't let absolute scale bury the ranking story.
        if raw:
            vals = [x[0] for x in raw]
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            std = var**0.5
            scored: list[Tip] = []
            for total, reasons, runner in raw:
                rel = (total - mean) / std if std > 1e-6 else 0.0
                # blend absolute + relative so strong absolute still matters a bit
                final = total + rel * 3.0
                scored.append(
                    Tip(
                        race_number=race["race_number"],
                        race_name=race["name"],
                        tab_no=runner["tab_no"],
                        horse=runner["horse_name"],
                        jockey=runner["jockey"],
                        trainer=runner["trainer"],
                        barrier=runner["barrier"],
                        score=round(final, 2),
                        reasons=reasons,
                        result_position=runner["result_position"],
                        result_price=runner["result_price"],
                    )
                )
            scored.sort(key=lambda t: t.score, reverse=True)
            tips.extend(scored)
    return tips


def tips_by_race(tips: list[Tip], top_n: int = 3) -> dict[int, list[Tip]]:
    by_race: dict[int, list[Tip]] = {}
    for tip in tips:
        by_race.setdefault(tip.race_number, []).append(tip)
    return {rn: rows[:top_n] for rn, rows in by_race.items()}


def backtest_summary(tips: list[Tip], top_n: int = 1) -> dict[str, float | int]:
    """Evaluate top-N picks where official results exist."""
    by_race = tips_by_race(tips, top_n=top_n)
    bets = 0
    wins = 0
    places = 0
    staked = 0.0
    returns = 0.0
    for _, ranked in by_race.items():
        # only score races that have at least one official result
        if not any(t.result_position is not None for t in ranked):
            # peek full tips list for that race via ranked alone — if top picks have no result,
            # still count only tips with results
            pass
        for tip in ranked:
            if tip.result_position is None:
                continue
            bets += 1
            staked += 1.0
            if tip.result_position == 1:
                wins += 1
                returns += tip.result_price or 0.0
            if tip.result_position <= 3:
                places += 1
    pot = ((returns - staked) / staked * 100.0) if staked else 0.0
    return {
        "bets": bets,
        "wins": wins,
        "places": places,
        "win_sr": (wins / bets * 100.0) if bets else 0.0,
        "place_sr": (places / bets * 100.0) if bets else 0.0,
        "pot_pct": pot,
    }
