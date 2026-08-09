# RaceDNA

Personal horse racing history database and trend tipper.

Upload your own **meeting CSV**, **results CSV**, and (later) sectional screenshots. RaceDNA stores the history locally and ranks runners from patterns in *your* data — not a third-party tip AI.

## Quick start

```bash
python3 -m pip install -e ".[dev]"

# 1) Put your Punting Form API key in the environment (or data/puntingform.key)
export PUNTINGFORM_API_KEY="your-key"

# 2) Download today's meetings (form + results) into data/inbox and import
python3 -m racedna download --date 2026-08-09 --import

# Or list meetings first
python3 -m racedna meetings --date 2026-08-09

# 3) Tip
python3 -m racedna tip --track "Belmont Park" --date 2026-08-09 --going Soft
```

Sample Belmont CSVs are already in `data/inbox/` if you want to try offline:

```bash
python3 -m racedna import-inbox
python3 -m racedna tip --track "Belmont Park" --date 2026-08-01
python3 -m racedna backtest --track "Belmont Park" --date 2026-08-01 --top 1
```

## Daily workflow

1. Set API key once:
   - `export PUNTINGFORM_API_KEY=...` or
   - save key to `data/puntingform.key`
2. Download + import:
   ```bash
   python3 -m racedna download --date YYYY-MM-DD --track "Belmont Park" --import
   ```
3. Tip: `python3 -m racedna tip --date YYYY-MM-DD --going Soft`
4. After races: download again (results fill in) and `python3 -m racedna backtest --date YYYY-MM-DD`

Optional extras on download: `--ratings`, `--sectionals` (Modeller), `--meeting-csv`.

Manual uploads still work: drop CSVs / sectional screenshots into `data/inbox/` then `import-inbox`.

### Sectional screenshots

```bash
python3 -m pip install -e ".[ocr]"   # needs system tesseract-ocr
python3 -m racedna import-sectionals data/inbox/sectionals/willingham.sectional.json
python3 -m racedna import-sectionals path/to/pf_screenshot.png
```

OCR is best-effort on dense PF tables. For important horses, drop a `.sectional.json` sidecar next to the image (same stem) — RaceDNA will prefer it.

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

## Commands

| Command | Purpose |
|---|---|
| `racedna init-db` | Create SQLite schema |
| `racedna import-meeting PATH` | Import meeting/form CSV |
| `racedna import-results PATH` | Import results CSV |
| `racedna meetings --date YYYY-MM-DD` | List PF meetings/ids for a day |
| `racedna download --date YYYY-MM-DD` | Download form/results CSVs via PF API |
| `racedna download ... --import` | Download then load into SQLite |
| `racedna import-inbox` | Import CSVs + sectionals from `data/inbox` |
| `racedna import-sectionals PATH` | Import screenshot / `.sectional.txt` / `.sectional.json` |
| `racedna tip` | Rank runners (`--top N`, `--json`) |
| `racedna backtest` | Evaluate tips vs results |

Database default path: `data/racedna.db`
