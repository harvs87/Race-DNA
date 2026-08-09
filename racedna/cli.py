from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from racedna.db import connect, init_db
from racedna.import_meeting import import_meeting
from racedna.import_results import import_results
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


def cmd_import_inbox(args: argparse.Namespace) -> int:
    inbox = Path(args.inbox)
    conn = connect(args.db)
    init_db(conn)
    reports = []
    meeting_files = sorted(inbox.glob("*Park*.csv")) + sorted(inbox.glob("*meeting*.csv"))
    # Prefer known naming: longer denser files first as meeting form exports
    all_csvs = sorted(inbox.glob("*.csv"))
    meeting_paths = []
    results_paths = []
    for path in all_csvs:
        # Heuristic: results exports are wide and have MeetingId header
        text = path.read_text(encoding="utf-8-sig", errors="ignore")[:2000]
        if "MeetingId" in text and "RaceResults[" in text:
            results_paths.append(path)
        else:
            meeting_paths.append(path)

    for path in meeting_paths:
        stats = import_meeting(conn, path)
        reports.append({"file": str(path), "type": "meeting", **stats})
    for path in results_paths:
        stats = import_results(conn, path)
        reports.append({"file": str(path), "type": "results", **stats})
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
    # Also show picks vs results for races that have results
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

    p_inbox = sub.add_parser("import-inbox", help="Import all CSVs from an inbox folder")
    _add_db_arg(p_inbox)
    p_inbox.add_argument("--inbox", default="data/inbox", help="Folder of CSV uploads")
    p_inbox.set_defaults(func=cmd_import_inbox)

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
