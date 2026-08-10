from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from racedna.db import connect, default_db_path, init_db
from racedna.import_assets import import_race_asset
from racedna.import_meeting import import_meeting
from racedna.import_results import import_results
from racedna.import_sectionals import import_sectional
from racedna.scorer import score_meeting, tips_by_race

ROOT = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(ROOT / "templates"))
UPLOAD_ROOT = Path("data/uploads")
ASSET_ROOT = Path("data/inbox/assets")


def get_db():
    conn = connect(default_db_path())
    init_db(conn)
    return conn


def create_app() -> FastAPI:
    app = FastAPI(title="RaceDNA", docs_url=None, redoc_url=None)
    static_dir = ROOT / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / "templates").mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        conn = get_db()
        meetings = conn.execute(
            """
            SELECT m.id, m.track, m.meeting_date,
                   COUNT(DISTINCT r.id) AS races,
                   COUNT(DISTINCT ru.id) AS runners,
                   COUNT(DISTINCT res.id) AS results,
                   COUNT(DISTINCT a.id) AS assets
            FROM meetings m
            LEFT JOIN races r ON r.meeting_id = m.id
            LEFT JOIN runners ru ON ru.race_id = r.id
            LEFT JOIN results res ON res.runner_id = ru.id
            LEFT JOIN race_assets a ON a.race_id = r.id
            GROUP BY m.id
            ORDER BY m.meeting_date DESC, m.id DESC
            """
        ).fetchall()
        flash = request.query_params.get("msg")
        return TEMPLATES.TemplateResponse(
            request,
            "home.html",
            {"meetings": meetings, "flash": flash},
        )

    @app.post("/upload/meeting")
    async def upload_meeting(file: UploadFile = File(...)):
        if not file.filename:
            raise HTTPException(400, "No file")
        dest = UPLOAD_ROOT / Path(file.filename).name
        with dest.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)
        conn = get_db()
        stats = import_meeting(conn, dest)
        return RedirectResponse(
            f"/?msg=Meeting+imported:+{stats.get('races', 0)}+races,+{stats.get('runners', 0)}+runners",
            status_code=303,
        )

    @app.post("/upload/results")
    async def upload_results(file: UploadFile = File(...)):
        if not file.filename:
            raise HTTPException(400, "No file")
        dest = UPLOAD_ROOT / Path(file.filename).name
        with dest.open("wb") as fh:
            shutil.copyfileobj(file.file, fh)
        conn = get_db()
        stats = import_results(conn, dest)
        return RedirectResponse(
            f"/?msg=Results+imported:+{stats.get('results', 0)}+runners+updated",
            status_code=303,
        )

    @app.get("/meetings/{meeting_id}", response_class=HTMLResponse)
    def meeting_detail(request: Request, meeting_id: int, going: str | None = None):
        conn = get_db()
        meeting = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not meeting:
            raise HTTPException(404, "Meeting not found")
        races = conn.execute(
            """
            SELECT r.*,
                   COUNT(DISTINCT ru.id) AS runners,
                   COUNT(DISTINCT res.id) AS results,
                   COUNT(DISTINCT a.id) AS assets
            FROM races r
            LEFT JOIN runners ru ON ru.race_id = r.id
            LEFT JOIN results res ON res.runner_id = ru.id
            LEFT JOIN race_assets a ON a.race_id = r.id
            WHERE r.meeting_id = ?
            GROUP BY r.id
            ORDER BY r.race_number
            """,
            (meeting_id,),
        ).fetchall()

        tips = tips_by_race(
            score_meeting(conn, meeting_id=meeting_id, going=going),
            top_n=3,
        )
        flash = request.query_params.get("msg")
        return TEMPLATES.TemplateResponse(
            request,
            "meeting.html",
            {
                "meeting": meeting,
                "races": races,
                "tips": tips,
                "going": going or "",
                "flash": flash,
            },
        )

    @app.get("/races/{race_id}", response_class=HTMLResponse)
    def race_detail(request: Request, race_id: int, going: str | None = None):
        conn = get_db()
        race = conn.execute(
            """
            SELECT r.*, m.track, m.meeting_date, m.id AS meeting_id
            FROM races r
            JOIN meetings m ON m.id = r.meeting_id
            WHERE r.id = ?
            """,
            (race_id,),
        ).fetchone()
        if not race:
            raise HTTPException(404, "Race not found")

        runners = conn.execute(
            """
            SELECT runners.*, horses.name AS horse_name,
                   horses.run_style, horses.settle,
                   results.position AS result_position,
                   results.price AS result_price,
                   results.margin AS result_margin
            FROM runners
            JOIN horses ON horses.id = runners.horse_id
            LEFT JOIN results ON results.runner_id = runners.id
            WHERE runners.race_id = ?
            ORDER BY runners.tab_no
            """,
            (race_id,),
        ).fetchall()
        assets = conn.execute(
            """
            SELECT * FROM race_assets
            WHERE race_id = ?
            ORDER BY id DESC
            """,
            (race_id,),
        ).fetchall()

        tips = [
            t
            for t in score_meeting(
                conn,
                meeting_id=race["meeting_id"],
                going=going or race["track_condition"],
            )
            if t.race_number == race["race_number"]
        ][:5]

        flash = request.query_params.get("msg")
        return TEMPLATES.TemplateResponse(
            request,
            "race.html",
            {
                "race": race,
                "runners": runners,
                "assets": assets,
                "tips": tips,
                "going": going or race["track_condition"] or "",
                "flash": flash,
            },
        )

    @app.post("/races/{race_id}/assets")
    async def race_asset(
        race_id: int,
        kind: str = Form("bias"),
        note: str = Form(""),
        file: UploadFile | None = File(None),
    ):
        conn = get_db()
        race = conn.execute("SELECT id FROM races WHERE id = ?", (race_id,)).fetchone()
        if not race:
            raise HTTPException(404, "Race not found")

        saved: Path | None = None
        if file and file.filename:
            dest = ASSET_ROOT / f"race{race_id}_{kind}_{Path(file.filename).name}"
            with dest.open("wb") as fh:
                shutil.copyfileobj(file.file, fh)
            saved = dest

        if not saved and not note.strip():
            raise HTTPException(400, "Provide a screenshot and/or a note")

        import_race_asset(
            conn,
            saved,
            kind=kind,
            note=note.strip() or None,
            race_id=race_id,
            copy_into=None,
        )
        return RedirectResponse(f"/races/{race_id}?msg=Asset+saved", status_code=303)

    @app.post("/races/{race_id}/sectionals")
    async def race_sectionals(
        race_id: int,
        file: UploadFile = File(...),
        horse_name: str = Form(""),
        run_style: str = Form(""),
        settle: str = Form(""),
    ):
        conn = get_db()
        race = conn.execute("SELECT id FROM races WHERE id = ?", (race_id,)).fetchone()
        if not race:
            raise HTTPException(404, "Race not found")
        if not file.filename:
            raise HTTPException(400, "No file")

        settle_val: int | None = None
        if settle.strip():
            try:
                settle_val = int(settle.strip())
            except ValueError as exc:
                raise HTTPException(400, "Settle must be a number") from exc

        suffix = Path(file.filename).suffix.lower() or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=UPLOAD_ROOT) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)

        keep = ASSET_ROOT / f"race{race_id}_sectionals_{Path(file.filename).name}"
        shutil.copy2(tmp_path, keep)

        try:
            stats = import_sectional(
                conn,
                keep,
                horse_name=horse_name.strip() or None,
                run_style=run_style.strip() or None,
                settle=settle_val,
            )
        except Exception as exc:  # noqa: BLE001
            # Still keep the raw screenshot attached so it isn't lost
            import_race_asset(
                conn,
                keep,
                kind="sectionals",
                note=f"screenshot saved (parse failed): {exc}",
                race_id=race_id,
                copy_into=None,
            )
            return RedirectResponse(
                f"/races/{race_id}?msg=Screenshot+saved+but+could+not+parse:+pick+the+horse+and+try+again",
                status_code=303,
            )

        note_bits = [f"sectional: {stats.get('horse_name') or file.filename}"]
        if stats.get("run_style"):
            note_bits.append(str(stats["run_style"]))
        if stats.get("manual"):
            note_bits.append("manual/screenshot")
        import_race_asset(
            conn,
            keep,
            kind="sectionals",
            note=" · ".join(note_bits),
            race_id=race_id,
            copy_into=None,
        )

        horse = stats.get("horse_name") or "horse"
        rows = stats.get("rows", 0)
        if rows:
            msg = f"Sectionals imported for {horse} ({rows} runs)"
        else:
            msg = (
                f"Screenshot saved for {horse}"
                + (f" · {stats.get('run_style')}" if stats.get("run_style") else "")
                + " (style saved; table OCR optional)"
            )
        return RedirectResponse(
            f"/races/{race_id}?msg=" + msg.replace(" ", "+"),
            status_code=303,
        )

    @app.get("/health")
    def health():
        return {"ok": True, "db": str(default_db_path())}

    return app


app = create_app()


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run("racedna.web:app", host=host, port=port, reload=False)
