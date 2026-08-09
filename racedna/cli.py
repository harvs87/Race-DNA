from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from racedna.db import connect, init_db
from racedna.download import download_meetings, import_downloaded
from racedna.import_meeting import import_meeting
from racedna.import_results import import_results
from racedna.import_sectionals import import_sectional, import_sectionals_dir
from racedna.pf_api import PuntingFormClient
from racedna.scorer import backtest_summary, score_meeting, tips_by_race


def _add_db_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        default="data/racedna.db",
        help="SQLite database path (default: data/racedna.db)",
    )


def cmd_init(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    print(f"Initialized database at {args.db}")
    return 0


def cmd_import_meeting(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    stats = import_meeting(conn, args.path)
    print(json.dumps({"ok": True, "type": "meeting", **stats}, indent=2))
    return 0


def cmd_import_results(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    stats = import_results(conn, args.path)
    print(json.dumps({"ok": True, "type": "results", **stats}, indent=2))
    return 0


def cmd_import_sectionals(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    path = Path(args.path)
    if path.is_dir():
        reports = import_sectionals_dir(conn, path)
        print(json.dumps({"ok": True, "type": "sectionals", "imports": reports}, indent=2))
    else:
        stats = import_sectional(conn, path)
        print(json.dumps({"ok": True, "type": "sectional", **stats}, indent=2))
    return 0


def cmd_import_inbox(args: argparse.Namespace) -> int:
    inbox = Path(args.inbox)
    conn = connect(args.db)
    init_db(conn)
    reports = []
    all_csvs = sorted(inbox.glob("*.csv"))
    meeting_paths = []
    results_paths = []
    for path in all_csvs:
        name = path.name.lower()
        if name.endswith("_results.csv") or "_results_" in name:
            results_paths.append(path)
            continue
        if name.endswith("_form.csv") or name.endswith("_meeting.csv"):
            meeting_paths.append(path)
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore")[:2000]
        if "MeetingId" in text and "RaceResults[" in text:
            results_paths.append(path)
        elif name.endswith("_ratings.csv") or name.endswith("_sectionals.csv"):
            # kept on disk for later; not imported by v0.2 meeting/results importers
            continue
        else:
            meeting_paths.append(path)

    for path in meeting_paths:
        stats = import_meeting(conn, path)
        reports.append({"file": str(path), "type": "meeting", **stats})
    for path in results_paths:
        stats = import_results(conn, path)
        reports.append({"file": str(path), "type": "results", **stats})

    # Sectionals: scan inbox once (includes inbox/sectionals via recursive glob)
    if inbox.exists():
        for stats in import_sectionals_dir(conn, inbox):
            reports.append({"file": stats.get("source"), "type": "sectional", **stats})

    print(json.dumps({"ok": True, "imports": reports}, indent=2))
    return 0


def cmd_tip(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    tips = score_meeting(
        conn,
        track=args.track,
        meeting_date=args.date,
        meeting_id=args.meeting_id,
        going=args.going,
    )
    by_race = tips_by_race(tips, top_n=args.top)
    if args.json:
        payload = {
            rn: [
                {
                    "tab_no": t.tab_no,
                    "horse": t.horse,
                    "jockey": t.jockey,
                    "trainer": t.trainer,
                    "barrier": t.barrier,
                    "score": t.score,
                    "reasons": t.reasons,
                    "result_position": t.result_position,
                    "result_price": t.result_price,
                }
                for t in rows
            ]
            for rn, rows in by_race.items()
        }
        print(json.dumps(payload, indent=2))
        return 0

    for rn, rows in by_race.items():
        title = rows[0].race_name or ""
        print(f"\n=== Race {rn}: {title} ===")
        for i, tip in enumerate(rows, 1):
            result = ""
            if tip.result_position is not None:
                result = f" | result #{tip.result_position} @ {tip.result_price}"
            print(
                f"{i}. #{tip.tab_no or '-'} {tip.horse}  "
                f"score={tip.score:.1f}  bar={tip.barrier}  "
                f"{tip.jockey or ''}{result}"
            )
            for reason in tip.reasons[:4]:
                print(f"    - {reason}")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    tips = score_meeting(
        conn,
        track=args.track,
        meeting_date=args.date,
        meeting_id=args.meeting_id,
        going=args.going,
    )
    summary = backtest_summary(tips, top_n=args.top)
    print(json.dumps(summary, indent=2))
    by_race = tips_by_race(tips, top_n=args.top)
    print("\nPicks vs results:")
    for rn, rows in by_race.items():
        if all(t.result_position is None for t in rows):
            continue
        picks = ", ".join(
            f"#{t.tab_no} {t.horse} (#{t.result_position} @{t.result_price})" for t in rows
        )
        print(f"  R{rn}: {picks}")
    return 0


def cmd_meetings(args: argparse.Namespace) -> int:
    client = PuntingFormClient(api_key=args.api_key)
    meetings = client.meetings_list(
        args.date,
        stage=args.stage,
        include_barrier_trials=args.barrier_trials,
    )
    if args.track:
        needle = args.track.lower()
        meetings = [m for m in meetings if needle in m.track.lower()]
    payload = [
        {
            "meeting_id": m.meeting_id,
            "track": m.track,
            "meeting_date": m.meeting_date,
            "rail": m.rail,
            "expected_condition": m.expected_condition,
            "has_sectionals": m.has_sectionals,
            "stage": m.stage,
        }
        for m in meetings
    ]
    print(json.dumps({"ok": True, "date": args.date, "meetings": payload}, indent=2))
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    meeting_ids = args.meeting_id or None
    report = download_meetings(
        meeting_date=args.date,
        meeting_ids=meeting_ids,
        track=args.track,
        out_dir=args.out,
        api_key=args.api_key,
        include_form=not args.no_form,
        include_meeting=args.meeting_csv,
        include_results=not args.no_results,
        include_ratings=args.ratings,
        include_sectionals=args.sectionals,
        include_barrier_trials=args.barrier_trials,
        stage=args.stage,
    )
    payload = report.to_dict()
    if args.do_import:
        imported = import_downloaded(report, db_path=args.db)
        payload["imported"] = imported
    print(json.dumps({"ok": not report.errors or any(f.ok for f in report.files), **payload}, indent=2))
    return 1 if report.errors and not any(f.ok for f in report.files) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="racedna",
        description="RaceDNA — import form/results and tip races from your own history DB",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="Create SQLite schema")
    _add_db_arg(p_init)
    p_init.set_defaults(func=cmd_init)

    p_im = sub.add_parser("import-meeting", help="Import Punting Form style meeting CSV")
    _add_db_arg(p_im)
    p_im.add_argument("path", help="Path to meeting CSV")
    p_im.set_defaults(func=cmd_import_meeting)

    p_ir = sub.add_parser("import-results", help="Import wide results CSV")
    _add_db_arg(p_ir)
    p_ir.add_argument("path", help="Path to results CSV")
    p_ir.set_defaults(func=cmd_import_results)

    p_is = sub.add_parser(
        "import-sectionals",
        help="Import sectional screenshot / .sectional.txt / .sectional.json",
    )
    _add_db_arg(p_is)
    p_is.add_argument("path", help="Image/text/json file or folder")
    p_is.set_defaults(func=cmd_import_sectionals)

    p_inbox = sub.add_parser("import-inbox", help="Import CSVs + sectionals from inbox")
    _add_db_arg(p_inbox)
    p_inbox.add_argument("--inbox", default="data/inbox", help="Folder of uploads")
    p_inbox.set_defaults(func=cmd_import_inbox)

    p_meetings = sub.add_parser("meetings", help="List Punting Form meetings for a date")
    p_meetings.add_argument("--date", required=True, help="Meeting date YYYY-MM-DD")
    p_meetings.add_argument("--track", help="Filter track name contains")
    p_meetings.add_argument("--api-key", help="Punting Form API key (or env PUNTINGFORM_API_KEY)")
    p_meetings.add_argument("--stage", default="A", help="N/W/A stage (default A)")
    p_meetings.add_argument(
        "--barrier-trials",
        action="store_true",
        help="Include barrier trials",
    )
    p_meetings.set_defaults(func=cmd_meetings)

    p_dl = sub.add_parser(
        "download",
        help="Download meeting form/results CSVs from Punting Form API",
    )
    _add_db_arg(p_dl)
    p_dl.add_argument("--date", help="Meeting date YYYY-MM-DD")
    p_dl.add_argument(
        "--meeting-id",
        type=int,
        action="append",
        help="Meeting id (repeatable). Skips meetings-list when set",
    )
    p_dl.add_argument("--track", help="Only download tracks containing this name")
    p_dl.add_argument("--out", default="data/inbox", help="Output folder (default data/inbox)")
    p_dl.add_argument("--api-key", help="Punting Form API key (or env / data/puntingform.key)")
    p_dl.add_argument("--stage", default="A", help="N/W/A stage (default A)")
    p_dl.add_argument("--barrier-trials", action="store_true")
    p_dl.add_argument("--no-form", action="store_true", help="Skip form CSV")
    p_dl.add_argument("--no-results", action="store_true", help="Skip results CSV")
    p_dl.add_argument("--meeting-csv", action="store_true", help="Also download meeting fields CSV")
    p_dl.add_argument("--ratings", action="store_true", help="Also download ratings CSV")
    p_dl.add_argument(
        "--sectionals",
        action="store_true",
        help="Also download sectionals CSV (Modeller plan)",
    )
    p_dl.add_argument(
        "--import",
        dest="do_import",
        action="store_true",
        help="Import downloaded form/results into the DB",
    )
    p_dl.set_defaults(func=cmd_download)

    p_tip = sub.add_parser("tip", help="Rank runners for a meeting")
    _add_db_arg(p_tip)
    p_tip.add_argument("--track", help="Track name filter")
    p_tip.add_argument("--date", help="Meeting date YYYY-MM-DD")
    p_tip.add_argument("--meeting-id", type=int, help="Internal meeting id")
    p_tip.add_argument(
        "--going",
        help="Override meeting going (Firm/Good/Soft/Heavy/Synthetic)",
    )
    p_tip.add_argument("--top", type=int, default=3, help="Top N per race")
    p_tip.add_argument("--json", action="store_true", help="JSON output")
    p_tip.set_defaults(func=cmd_tip)

    p_bt = sub.add_parser("backtest", help="Score top picks against imported results")
    _add_db_arg(p_bt)
    p_bt.add_argument("--track", help="Track name filter")
    p_bt.add_argument("--date", help="Meeting date YYYY-MM-DD")
    p_bt.add_argument("--meeting-id", type=int)
    p_bt.add_argument(
        "--going",
        help="Override meeting going (Firm/Good/Soft/Heavy/Synthetic)",
    )
    p_bt.add_argument("--top", type=int, default=1, help="Top N selections per race")
    p_bt.set_defaults(func=cmd_backtest)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
