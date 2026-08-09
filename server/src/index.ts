import cors from "cors";
import express from "express";
import { analyzeRace } from "./analysis/engine.js";
import {
  applyMeetingImport,
  applyOddsImport,
  applyResultsImport,
  getDashboard,
  getMeeting,
  getRace,
  initStore,
  listMeetingSummaries,
  listRaces,
  resetStore,
  resetStoreMessage,
} from "./data/store.js";

const app = express();
const port = Number(process.env.PORT ?? 4000);

app.use(cors());
app.use(express.json({ limit: "5mb" }));
app.use(express.text({ type: ["text/csv", "text/plain"], limit: "5mb" }));

initStore();

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", service: "race-dna-api", storage: "sqlite" });
});

app.get("/api/dashboard", (_req, res) => {
  res.json(getDashboard());
});

app.get("/api/meetings", (_req, res) => {
  res.json(listMeetingSummaries());
});

app.get("/api/meetings/:id", (req, res) => {
  const meeting = getMeeting(req.params.id);
  if (!meeting) {
    res.status(404).json({ error: `Meeting '${req.params.id}' not found` });
    return;
  }
  res.json(meeting);
});

app.get("/api/races", (_req, res) => {
  res.json(
    listRaces().map((race) => ({
      id: race.id,
      meetingId: race.meetingId,
      name: race.name,
      course: race.course,
      date: race.date,
      raceNumber: race.raceNumber,
      distanceFurlongs: race.distanceFurlongs,
      distanceMeters: race.distanceMeters,
      going: race.going,
      runnerCount: race.runners.length,
      hasOdds: race.runners.some((runner) => runner.winOdds !== undefined),
      hasResults: race.runners.some((runner) => runner.finishPosition !== undefined),
    })),
  );
});

app.get("/api/races/:id/analysis", (req, res) => {
  const race = getRace(req.params.id);
  if (!race) {
    res.status(404).json({ error: `Race '${req.params.id}' not found` });
    return;
  }
  res.json(analyzeRace(race));
});

function readCsvBody(req: express.Request): string {
  if (typeof req.body === "string") return req.body;
  if (req.body && typeof req.body.csv === "string") return req.body.csv;
  if (req.body && typeof req.body.content === "string") return req.body.content;
  return "";
}

app.post("/api/import/meeting", (req, res) => {
  const csv = readCsvBody(req);
  if (!csv.trim()) {
    res.status(400).json({ error: "CSV body required (text/csv or JSON { csv })" });
    return;
  }
  res.json(applyMeetingImport(csv));
});

app.post("/api/import/results", (req, res) => {
  const csv = readCsvBody(req);
  if (!csv.trim()) {
    res.status(400).json({ error: "CSV body required (text/csv or JSON { csv })" });
    return;
  }
  res.json(applyResultsImport(csv));
});

app.post("/api/import/odds", (req, res) => {
  const csv = readCsvBody(req);
  if (!csv.trim()) {
    res.status(400).json({ error: "CSV body required (text/csv or JSON { csv })" });
    return;
  }
  res.json(applyOddsImport(csv));
});

app.post("/api/reset", (_req, res) => {
  resetStore();
  res.json({ status: "ok", message: "SQLite store reset and reseeded." });
});

app.listen(port, () => {
  console.log(`RaceDNA API listening on http://localhost:${port}`);
});
