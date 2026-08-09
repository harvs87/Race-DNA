# Race-DNA

RaceDNA Horse Racing Analysis — a model-driven web app that rates each runner in a
race, breaks down the contributing factors (form, speed, distance fit, going,
class, connections, freshness, and market odds when available), and turns those
ratings into win probabilities.

Imported meetings, results, and TAB/TABtouch odds are stored in a **local SQLite
database** so data survives restarts.

## Stack

- **Server** (`server/`) — Express + TypeScript API, analysis engine, CSV importers,
  exact TAB-number matching, SQLite persistence (`node:sqlite`).
- **Client** (`client/`) — React + Vite + TypeScript UI (Dashboard, Meeting,
  Meeting Archive, Race DNA, imports).

## Getting started

```bash
npm install
npm run dev
```

Open http://localhost:5173. API on :4000. Database file: `data/racedna.sqlite`.

## Daily workflow

1. **Import Meeting CSV** — Punting Form Meeting CSV (`Track`, `RaceNumber`,
   `TabNo`, `Runner`, …). Wizard-style CSVs still work.
2. **Meeting** — visually confirm every race and every runner (TAB numbers exact,
   including 10/11/12/13).
3. **Import Results** — match by meeting + race number + exact TAB number.
4. **Import TAB Odds** — optional separate TABtouch/TAB capture (no live feed).
5. **Race DNA** — model scores and factor breakdowns.
6. **Meeting Archive** — reopen any previously imported meeting from SQLite.

Sample files: `samples/meeting-punting-form.csv`, `samples/results-punting-form.csv`,
`samples/odds-tabtouch.csv`.

## Commands

| Command             | Description                              |
| ------------------- | ---------------------------------------- |
| `npm run dev`       | API + client                             |
| `npm run build`     | Production build                         |
| `npm test`          | Unit tests (incl. TAB 1/10/11/12/13)     |
| `npm run typecheck` | Type-check both packages                 |

## API

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/meetings` / `GET /api/meetings/:id`
- `GET /api/races` / `GET /api/races/:id/analysis`
- `POST /api/import/meeting|results|odds`
- `POST /api/reset` — wipe SQLite and reseed demo meetings
