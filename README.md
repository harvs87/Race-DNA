# Race-DNA

RaceDNA Horse Racing Analysis — a model-driven web app that rates each runner in a
race, breaks down the contributing factors (form, speed, distance fit, going,
class, connections, freshness), and turns those ratings into win probabilities.

## Stack

- **Server** (`server/`) — Express + TypeScript API with the analysis engine.
- **Client** (`client/`) — React + Vite + TypeScript dashboard.

The project uses npm workspaces, so a single `npm install` at the root installs
both packages.

## Getting started

```bash
npm install        # install all workspace dependencies
npm run dev        # run the API (:4000) and the web app (:5173) together
```

Then open http://localhost:5173. The Vite dev server proxies `/api/*` to the API.

Run each side individually with `npm run dev:server` or `npm run dev:client`.

## Useful commands

| Command             | Description                                  |
| ------------------- | -------------------------------------------- |
| `npm run dev`       | Run API + client together (development)      |
| `npm run build`     | Type-check and build both packages           |
| `npm test`          | Run the analysis engine unit tests           |
| `npm run typecheck` | Type-check both packages without emitting     |

## API

- `GET /api/health` — service health check.
- `GET /api/races` — list of races on the card.
- `GET /api/races/:id/analysis` — ranked runners with DNA scores, win
  probabilities, and per-factor breakdowns.
