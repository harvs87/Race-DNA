# RaceDNA

Personal horse racing history database and trend tipper.

Upload your own **meeting CSV**, **results CSV**, and (later) sectional screenshots. RaceDNA stores the history locally and ranks runners from patterns in *your* data — not a third-party tip AI.

## Quick start

```bash
python3 -m pip install -e ".[dev]"

# Create DB + import sample Belmont files in data/inbox/
python3 -m racedna init-db
python3 -m racedna import-inbox

# Rank runners for the imported meeting
python3 -m racedna tip --track "Belmont Park" --date 2026-08-01

# Check top picks against imported official results
python3 -m racedna backtest --track "Belmont Park" --date 2026-08-01 --top 1
```

## Daily workflow

1. Drop new files into `data/inbox/`
   - Meeting form export (Punting Form style)
   - Results export (wide `RaceResults[n].Runners[m].*` CSV)
   - Optional: PF API sectionals/benchmarks into `data/inbox/pf/`
   - Optional: sectional screenshots into `data/inbox/sectionals/` (PNG/JPG)
2. Run `python3 -m racedna import-inbox`
3. Run `python3 -m racedna tip` for ranked shortlists with reasons
4. After the meeting, import results and run `python3 -m racedna backtest` to track strike rate / POT

### Official PF sectionals + benchmarks (preferred)

Do **not** scrape the website. Punting Form exposes official endpoints (Modeller / commercial):

- `GET https://api.puntingform.com.au/v2/Ratings/MeetingSectionals`
- `GET https://api.puntingform.com.au/v2/Ratings/MeetingBenchmarks`
- CSV variants: `.../MeetingSectionals/csv`, `.../MeetingBenchmarks/csv`

```bash
export PUNTINGFORM_API_KEY='your-modeller-key'
# After meeting CSV/results are imported (so MeetingId is known):
python3 -m racedna fetch-pf --meeting-id 241810 --import
# or resolve MeetingId from the local DB:
python3 -m racedna fetch-pf --track "Belmont Park" --date 2026-08-01 --import
```

Files land in `data/inbox/pf/` and are imported into `pf_sectionals` / `pf_benchmarks`. The tipper uses finish/L600/L200 benchmark lengths when present.

### Sectional screenshots (fallback)

```bash
python3 -m pip install -e ".[ocr]"   # needs system tesseract-ocr
python3 -m racedna import-sectionals data/inbox/sectionals/willingham.sectional.json
python3 -m racedna import-sectionals path/to/pf_screenshot.png
```

OCR is best-effort on dense PF tables. Prefer the Modeller API above when you have access.

## What the scorer looks at (v0.2)

Situational signals outweigh raw career win rate:

- Soft/heavy vs good going match + wet-specialist detection
- Same-track / track-distance records and recent local form
- Margin-aware recent form (close-ups count; short-price bombs penalised)
- Closing sectionals only when the horse finished competitively
- Freshness / spell handling (ideal 10–28d; first-up record after spells)
- Barrier model stronger on wet tracks (inside favoured, wide punished)
- Class drop/rise from form class text
- Race-relative normalisation so one fat career WR doesn’t dominate
- Optional `--going Soft` override when the card has no official condition yet
- Screenshot sectionals: run style / settle, closer patterns, L6/L2, fast-pace handling
- Official PF benchmarks: finish / L600 / L200 / class lengths when fetched via API

## Commands

| Command | Purpose |
|---|---|
| `racedna init-db` | Create SQLite schema |
| `racedna import-meeting PATH` | Import meeting/form CSV |
| `racedna import-results PATH` | Import results CSV |
| `racedna import-inbox` | Import CSVs + sectionals from `data/inbox` |
| `racedna fetch-pf` | Download PF sectionals + benchmarks (Modeller API) |
| `racedna import-pf-sectionals PATH` | Import official MeetingSectionals JSON/CSV |
| `racedna import-pf-benchmarks PATH` | Import official MeetingBenchmarks JSON/CSV |
| `racedna import-sectionals PATH` | Import screenshot / `.sectional.txt` / `.sectional.json` |
| `racedna tip` | Rank runners (`--top N`, `--json`) |
| `racedna backtest` | Evaluate tips vs results |

Database default path: `data/racedna.db`
