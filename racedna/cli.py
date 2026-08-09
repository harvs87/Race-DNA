from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from racedna.db import connect, init_db
from racedna.import_meeting import import_meeting
from racedna.import_pf_api import (
    import_benchmarks_file,
    import_ratings_file,
    import_sectionals_file,
)
from racedna.import_results import import_results
from racedna.import_sectionals import import_sectional, import_sectionals_dir
from racedna.pf_api import (
    PfApiError,
    default_download_paths,
    fetch_meeting_benchmarks,
    fetch_meeting_ratings,
    fetch_meeting_sectionals,
    resolve_api_key,
    save_download,
)
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
    # Also pick up official PF API downloads under inbox/pf/
    pf_dir = inbox / "pf"
    all_paths = list(all_csvs)
    if pf_dir.exists():
        all_paths.extend(sorted(pf_dir.glob("*.csv")))
        all_paths.extend(sorted(pf_dir.glob("*.json")))

    meeting_paths = []
    results_paths = []
    pf_sectional_paths = []
    pf_benchmark_paths = []
    pf_ratings_paths = []
    for path in all_paths:
        name = path.name.lower()
        if "sectional" in name and path.suffix.lower() in {".json", ".csv"}:
            pf_sectional_paths.append(path)
            continue
        if "benchmark" in name and path.suffix.lower() in {".json", ".csv"}:
            pf_benchmark_paths.append(path)
            continue
        if "rating" in name and path.suffix.lower() in {".json", ".csv"}:
            pf_ratings_paths.append(path)
            continue
        if path.suffix.lower() != ".csv":
            continue
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
    for path in pf_ratings_paths:
        stats = import_ratings_file(conn, path)
        reports.append({"file": str(path), "type": "pf_ratings", **stats})
    for path in pf_sectional_paths:
        stats = import_sectionals_file(conn, path)
        reports.append({"file": str(path), "type": "pf_sectionals", **stats})
    for path in pf_benchmark_paths:
        stats = import_benchmarks_file(conn, path)
        reports.append({"file": str(path), "type": "pf_benchmarks", **stats})

    # Sectionals: scan inbox once (includes inbox/sectionals via recursive glob)
    if inbox.exists():
        for stats in import_sectionals_dir(conn, inbox):
            reports.append({"file": stats.get("source"), "type": "sectional", **stats})

    print(json.dumps({"ok": True, "imports": reports}, indent=2))
    return 0


def _resolve_external_meeting_id(conn, args: argparse.Namespace) -> int:
    if args.meeting_id is not None:
        return int(args.meeting_id)
    if args.track and args.date:
        row = conn.execute(
            """
            SELECT external_id FROM meetings
            WHERE lower(track) = lower(?) AND meeting_date = ?
            LIMIT 1
            """,
            (args.track, args.date),
        ).fetchone()
        if not row or not row["external_id"]:
            raise ValueError(
                "No meetings.external_id for that track/date. "
                "Pass --meeting-id (PF MeetingId) or import results/meeting with MeetingId first."
            )
        return int(row["external_id"])
    raise ValueError("Provide --meeting-id or both --track and --date")


def cmd_fetch_pf(args: argparse.Namespace) -> int:
    """Download PF MeetingRatings (Starter+) and optional Modeller sectionals/benchmarks."""
    conn = connect(args.db)
    init_db(conn)
    try:
        api_key = resolve_api_key(args.api_key)
        external_meeting_id = _resolve_external_meeting_id(conn, args)
    except (PfApiError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    explicit = args.ratings or args.sectionals or args.benchmarks
    want_ratings = bool(args.ratings) if explicit else True
    want_sec = bool(args.sectionals)
    want_bm = bool(args.benchmarks)

    paths = default_download_paths(external_meeting_id, args.out)
    report: dict = {
        "ok": True,
        "external_meeting_id": external_meeting_id,
        "downloads": [],
        "imports": [],
        "errors": [],
    }

    def _one(kind: str, fetch_fn, import_fn, json_key: str, csv_key: str) -> None:
        try:
            if args.csv:
                body = fetch_fn(external_meeting_id, api_key=api_key, as_csv=True)
                path = save_download(body, paths[csv_key], as_csv=True)
            else:
                payload = fetch_fn(external_meeting_id, api_key=api_key, as_csv=False)
                path = save_download(payload, paths[json_key], as_csv=False)
            report["downloads"].append(str(path))
            if args.do_import:
                stats = import_fn(conn, path)
                report["imports"].append({"type": kind, **stats})
        except PfApiError as exc:
            report["errors"].append({"type": kind, "error": str(exc)})

    if want_ratings:
        _one(
            "pf_ratings",
            fetch_meeting_ratings,
            import_ratings_file,
            "ratings_json",
            "ratings_csv",
        )
    if want_sec:
        _one(
            "pf_sectionals",
            fetch_meeting_sectionals,
            import_sectionals_file,
            "sectionals_json",
            "sectionals_csv",
        )
    if want_bm:
        _one(
            "pf_benchmarks",
            fetch_meeting_benchmarks,
            import_benchmarks_file,
            "benchmarks_json",
            "benchmarks_csv",
        )

    if not report["downloads"] and report["errors"]:
        print(json.dumps(report, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


def cmd_import_pf_sectionals(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    stats = import_sectionals_file(conn, args.path)
    print(json.dumps({"ok": True, "type": "pf_sectionals", **stats}, indent=2))
    return 0


def cmd_import_pf_benchmarks(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    stats = import_benchmarks_file(conn, args.path)
    print(json.dumps({"ok": True, "type": "pf_benchmarks", **stats}, indent=2))
    return 0


def cmd_import_pf_ratings(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    init_db(conn)
    stats = import_ratings_file(conn, args.path)
    print(json.dumps({"ok": True, "type": "pf_ratings", **stats}, indent=2))
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

    p_fetch = sub.add_parser(
        "fetch-pf",
        help="Download PF MeetingRatings (Starter+) and optional Modeller sectionals/benchmarks",
    )
    _add_db_arg(p_fetch)
    p_fetch.add_argument("--meeting-id", type=int, help="Punting Form MeetingId")
    p_fetch.add_argument("--track", help="Resolve MeetingId from local DB")
    p_fetch.add_argument("--date", help="Meeting date YYYY-MM-DD (with --track)")
    p_fetch.add_argument("--api-key", help="PF API key (else PUNTINGFORM_API_KEY)")
    p_fetch.add_argument("--out", default="data/inbox/pf", help="Download folder")
    p_fetch.add_argument(
        "--ratings",
        action="store_true",
        help="Fetch MeetingRatings (default when no kind flags set)",
    )
    p_fetch.add_argument(
        "--sectionals",
        action="store_true",
        help="Fetch MeetingSectionals (Modeller only)",
    )
    p_fetch.add_argument(
        "--benchmarks",
        action="store_true",
        help="Fetch MeetingBenchmarks (Modeller only)",
    )
    p_fetch.add_argument("--csv", action="store_true", help="Request CSV instead of JSON")
    p_fetch.add_argument(
        "--import",
        dest="do_import",
        action="store_true",
        help="Import downloaded files into the DB",
    )
    p_fetch.set_defaults(func=cmd_fetch_pf)

    p_ipr = sub.add_parser(
        "import-pf-ratings",
        help="Import PF MeetingRatings JSON/CSV (Starter+ sectional ranks)",
    )
    _add_db_arg(p_ipr)
    p_ipr.add_argument("path", help="Path to ratings JSON or CSV")
    p_ipr.set_defaults(func=cmd_import_pf_ratings)

    p_ips = sub.add_parser(
        "import-pf-sectionals",
        help="Import PF MeetingSectionals JSON/CSV (Modeller API export)",
    )
    _add_db_arg(p_ips)
    p_ips.add_argument("path", help="Path to sectionals JSON or CSV")
    p_ips.set_defaults(func=cmd_import_pf_sectionals)

    p_ipb = sub.add_parser(
        "import-pf-benchmarks",
        help="Import PF MeetingBenchmarks JSON/CSV (Modeller API export)",
    )
    _add_db_arg(p_ipb)
    p_ipb.add_argument("path", help="Path to benchmarks JSON or CSV")
    p_ipb.set_defaults(func=cmd_import_pf_benchmarks)

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
