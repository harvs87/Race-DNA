# Race-DNA

RaceDNA Horse Racing Analysis — a model-driven web app that rates each runner in a
race, breaks down the contributing factors (form, speed, distance fit, going,
class, connections, freshness, and market odds when available), and turns those
ratings into win probabilities.

## Stack

- **Server** (`server/`) — Express + TypeScript API with the analysis engine,
  CSV importers, and exact TAB-number horse matching.
- **Client** (`client/`) — React + Vite + TypeScript dashboard with Race DNA
  analysis and import screens.

The project uses npm workspaces, so a single `npm install` at the root installs
both packages.

## Getting started

```bash
npm install        # install all workspace dependencies
npm run dev        # run the API (:4000) and the web app (:5173) together
```

Then open http://localhost:5173. The Vite dev server proxies `/api/*` to the API.

Run each side individually with `npm run dev:server` or `npm run dev:client`.

## App views

- **Dashboard** — meetings, runner counts, and model top picks.
- **Race DNA** — race switching with ranked DNA scores and factor breakdowns.
- **Import Meeting CSV** — Wizard-style fields/form import.
- **Import Results** — finish positions matched by meeting + race + TAB number.
- **Import TAB Odds** — TAB / TABtouch win/place odds with exact TAB matching
  (runners 10 and 13 never collide with runner 1).

Sample CSVs live in `samples/` and `server/fixtures/`.

## Useful commands

| Command             | Description                                  |
| ------------------- | -------------------------------------------- |
| `npm run dev`       | Run API + client together (development)      |
| `npm run build`     | Type-check and build both packages           |
| `npm test`          | Run server unit tests                        |
| `npm run typecheck` | Type-check both packages without emitting     |

## API

- `GET /api/health` — service health check.
- `GET /api/dashboard` — meetings overview and top picks.
- `GET /api/races` — list of races on the card.
- `GET /api/races/:id/analysis` — ranked runners with DNA scores, win
  probabilities, TAB numbers, odds/results when present, and per-factor
  breakdowns.
- `POST /api/import/meeting` — import meeting CSV (`text/csv` body or JSON `{ csv }`).
- `POST /api/import/results` — import results CSV.
- `POST /api/import/odds` — import TAB / TABtouch odds CSV.
- `POST /api/reset` — restore seed races (dev helper).
