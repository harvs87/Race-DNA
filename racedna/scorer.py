from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

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


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _recent_form_score(form_rows: list[sqlite3.Row], race_distance: int | None) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if not form_rows:
        reasons.append("no form lines")
        return -5.0, reasons

    recent = form_rows[:5]
    positions = [r["position"] for r in recent if r["position"] is not None]
    if positions:
        avg_pos = sum(positions) / len(positions)
        # lower finishing position is better
        pos_points = max(0.0, 12.0 - avg_pos * 1.8)
        score += pos_points
        reasons.append(f"recent avg pos {avg_pos:.1f} (+{pos_points:.1f})")
        wins = sum(1 for p in positions if p == 1)
        places = sum(1 for p in positions if p <= 3)
        if wins:
            score += wins * 4
            reasons.append(f"{wins} win(s) in last {len(positions)}")
        elif places:
            score += places * 1.5
            reasons.append(f"{places} place(s) in last {len(positions)}")

    # distance suitability from form
    if race_distance:
        dist_rows = [
            r
            for r in form_rows
            if r["distance"] is not None and abs(r["distance"] - race_distance) <= 100
        ]
        if dist_rows:
            dist_wins = sum(1 for r in dist_rows if r["position"] == 1)
            dist_places = sum(1 for r in dist_rows if r["position"] is not None and r["position"] <= 3)
            dist_pts = dist_wins * 3 + dist_places * 1.2
            score += dist_pts
            reasons.append(
                f"dist±100m form {dist_wins}w/{dist_places}p from {len(dist_rows)} (+{dist_pts:.1f})"
            )

    # closing sectional proxy: faster last-600 is better when finishing close
    sectional_times = [
        r["sectional_time"]
        for r in recent
        if r["sectional_time"] is not None and r["sectional_time"] > 0
    ]
    if sectional_times:
        avg_sec = sum(sectional_times) / len(sectional_times)
        # typical 600m sectional ~33-36; reward faster
        sec_pts = max(-3.0, min(6.0, (35.5 - avg_sec) * 2.0))
        score += sec_pts
        reasons.append(f"avg L{recent[0]['sectional_distance'] or 600} {avg_sec:.2f}s (+{sec_pts:.1f})")

    # market respect vs outcome (value / underperformance)
    priced = [
        r
        for r in recent
        if r["price"] is not None and r["price"] > 1 and r["position"] is not None
    ]
    if priced:
        overlays = 0
        for r in priced:
            # short price that ran poorly is a negative; long price that placed is a positive
            if r["position"] <= 3 and r["price"] >= 8:
                overlays += 1
                score += 1.5
            if r["position"] >= 8 and r["price"] <= 4:
                score -= 1.5
        if overlays:
            reasons.append(f"{overlays} longshot place(s) in recent form")

    return score, reasons


def _career_score(runner: sqlite3.Row, going_bucket: str | None, track: str) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    career = parse_record(runner["record"])
    wr = win_rate(career)
    pr = place_rate(career)
    if wr is not None:
        pts = wr * 20
        score += pts
        reasons.append(f"career WR {wr:.0%} (+{pts:.1f})")
    if pr is not None:
        pts = pr * 8
        score += pts
        reasons.append(f"career PR {pr:.0%} (+{pts:.1f})")

    track_rec = parse_record(runner["record_track"])
    tw = win_rate(track_rec)
    if tw is not None and (track_rec.get("starts") or 0) >= 2:
        pts = tw * 18
        score += pts
        reasons.append(f"{track} WR {tw:.0%} from {track_rec['starts']} (+{pts:.1f})")

    dist_rec = parse_record(runner["record_distance"])
    dw = win_rate(dist_rec)
    if dw is not None and (dist_rec.get("starts") or 0) >= 2:
        pts = dw * 12
        score += pts
        reasons.append(f"distance WR {dw:.0%} (+{pts:.1f})")

    if going_bucket:
        key = {
            "Firm": "record_firm",
            "Good": "record_good",
            "Soft": "record_soft",
            "Heavy": "record_heavy",
            "Synthetic": "record_synthetic",
        }.get(going_bucket)
        if key and runner[key]:
            going_rec = parse_record(runner[key])
            gw = win_rate(going_rec)
            gp = place_rate(going_rec)
            if gw is not None and (going_rec.get("starts") or 0) >= 2:
                pts = gw * 16
                score += pts
                reasons.append(f"{going_bucket} WR {gw:.0%} (+{pts:.1f})")
            elif gp is not None and (going_rec.get("starts") or 0) >= 2:
                pts = gp * 6
                score += pts
                reasons.append(f"{going_bucket} PR {gp:.0%} (+{pts:.1f})")

    first_up = parse_record(runner["record_first_up"])
    # crude freshness signal from last10 containing x near start
    last10 = (runner["last10"] or "").lower()
    if last10.startswith("x") or "x" in last10[:2]:
        fu_wr = win_rate(first_up)
        if fu_wr is not None:
            pts = fu_wr * 10
            score += pts
            reasons.append(f"first-up WR {fu_wr:.0%} (+{pts:.1f})")

    return score, reasons


def score_meeting(
    conn: sqlite3.Connection,
    track: str | None = None,
    meeting_date: str | None = None,
    meeting_id: int | None = None,
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

    races = cur.execute(
        "SELECT * FROM races WHERE meeting_id = ? ORDER BY race_number",
        (meeting_id,),
    ).fetchall()

    tips: list[Tip] = []
    for race in races:
        going = condition_bucket(race["track_condition"])
        runners = cur.execute(
            """
            SELECT runners.*, horses.name AS horse_name,
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

        scored: list[Tip] = []
        for runner in runners:
            form_rows = cur.execute(
                """
                SELECT * FROM form_runs
                WHERE runner_id = ?
                ORDER BY form_date DESC, id DESC
                """,
                (runner["id"],),
            ).fetchall()

            career_pts, career_reasons = _career_score(runner, going, meeting["track"])
            form_pts, form_reasons = _recent_form_score(form_rows, race["distance"])

            # barrier mild penalty for wide gates in big fields
            barrier_pts = 0.0
            if runner["barrier"] is not None and len(runners) >= 10 and runner["barrier"] >= 12:
                barrier_pts = -1.5
            elif runner["barrier"] is not None and runner["barrier"] <= 3:
                barrier_pts = 1.0

            total = career_pts + form_pts + barrier_pts
            reasons = career_reasons + form_reasons
            if barrier_pts:
                reasons.append(f"barrier {runner['barrier']} ({barrier_pts:+.1f})")

            scored.append(
                Tip(
                    race_number=race["race_number"],
                    race_name=race["name"],
                    tab_no=runner["tab_no"],
                    horse=runner["horse_name"],
                    jockey=runner["jockey"],
                    trainer=runner["trainer"],
                    barrier=runner["barrier"],
                    score=round(total, 2),
                    reasons=reasons[:6],
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
