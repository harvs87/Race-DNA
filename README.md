# RaceDNA

A **local SQLite database** for racing form.

That’s it. Upload a meeting. Upload results. For races you want to punt on, drop in screenshots (sectionals, bias, notes). Then ask for tips built from **past results + past form** in *your* DB.

No web app. No tip-service AI. Just your files → your DB → ranked runners.

## Install

```bash
python3 -m pip install -e .
```

## Daily flow

```bash
# 1) Upload meeting (form card CSV)
python3 -m racedna import-meeting path/to/meeting.csv

# 2) After the day / for history — upload results
python3 -m racedna import-results path/to/results.csv

# 3) For a race you’re interested in — attach screenshots / notes
python3 -m racedna add-asset bias.png \
  --track "Belmont Park" --date 2026-08-01 --race 3 \
  --kind bias --note "rails + leaders"

python3 -m racedna import-sectionals path/to/horse_sectionals.png
# (or .sectional.json / .sectional.txt next to the image)

# 4) Tip
python3 -m racedna tip --track "Belmont Park" --date 2026-08-01 --going Soft

# See what’s in the DB
python3 -m racedna list
```

Drop files in `data/inbox/` and run `python3 -m racedna import-inbox` if you prefer batch.

Sample Belmont CSVs are already under `data/inbox/`.

## What the tipper uses

- Past form lines on each runner (going, track, distance, class, freshness)
- Official results you’ve imported (for history + backtests)
- Sectional screenshots you’ve attached to horses
- Bias / notes screenshots you’ve attached to a race (`rails`, `leaders`, `closers`, `wide`, …)

```bash
python3 -m racedna backtest --track "Belmont Park" --date 2026-08-01 --top 1
```

Database file: `data/racedna.db`

## Optional: Punting Form API download

If you have an API key you can pull CSVs instead of saving them by hand:

```bash
export PUNTINGFORM_API_KEY="your-key"
python3 -m racedna download --date 2026-08-09 --track "Belmont Park" --import
```

Not required for the core workflow.

## OCR (optional)

Dense sectional screenshots work best with a `.sectional.json` / `.sectional.txt` sidecar.
Image OCR needs system Tesseract + `pip install -e ".[ocr]"`.
