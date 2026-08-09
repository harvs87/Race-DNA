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
2. Run `racedna import-inbox`
3. Run `racedna tip` for ranked shortlists with reasons
4. After the meeting, import results and run `racedna backtest` to track strike rate / POT

## What the scorer looks at (v0.1)

- Career / track / distance / going win & place rates
- Recent form average position, wins/places
- Distance suitability from past runs
- Last-600 sectional times from the meeting CSV
- Mild barrier adjustment in larger fields
- First-up signal from `last10` + first-up record

Sectional **screenshot OCR** is planned next — CSVs are the source of truth for cards and results.

## Commands

| Command | Purpose |
|---|---|
| `racedna init-db` | Create SQLite schema |
| `racedna import-meeting PATH` | Import meeting/form CSV |
| `racedna import-results PATH` | Import results CSV |
| `racedna import-inbox` | Import all CSVs from `data/inbox` |
| `racedna tip` | Rank runners (`--top N`, `--json`) |
| `racedna backtest` | Evaluate tips vs results |

Database default path: `data/racedna.db`
