# RaceDNA

A simple local database for racing.

Upload the meeting. Upload the results. For races you want to punt on, attach sectional / bias screenshots. Tip from **past results + past form** in your own DB.

## Run the app

```bash
python3 -m pip install -e .
python3 -m racedna serve
```

Open **http://localhost:8000**

1. Upload meeting CSV  
2. Upload results CSV  
3. Open a race → attach bias screenshot / note, import horse sectionals  
4. Read the tips

## CLI (same DB)

```bash
python3 -m racedna import-meeting path/to/meeting.csv
python3 -m racedna import-results path/to/results.csv
python3 -m racedna add-asset bias.png --track "Belmont Park" --date 2026-08-01 --race 3 --kind bias --note "rails + leaders"
python3 -m racedna import-sectionals path/to/horse_sectionals.json
python3 -m racedna tip --track "Belmont Park" --date 2026-08-01 --going Soft
python3 -m racedna list
```

Sample Belmont files are in `data/inbox/`.

Database: `data/racedna.db` (override with `--db` or `RACEDNA_DB`).

## What tips use

- Form lines (going, track, distance, class, freshness)
- Imported official results
- Horse sectional screenshots / JSON
- Race bias notes (`rails`, `leaders`, `closers`, `wide`, …)

```bash
python3 -m racedna backtest --track "Belmont Park" --date 2026-08-01 --top 1
```

## Screenshot sectionals

In the race page: upload the screenshot, **pick the horse**, and set run style / settle if you know it.

OCR is optional. Without Tesseract the screenshot still saves and the horse’s run style is used in tips.

```bash
# optional — better table reading from screenshots
brew install tesseract          # Mac
python3 -m pip install -e ".[ocr]"
```

## Optional

- Punting Form API download: `python3 -m racedna download --date YYYY-MM-DD --import`
