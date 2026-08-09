import cors from "cors";
import express from "express";
import { analyzeRace } from "./analysis/engine.js";
import { getRaceById, races } from "./data/races.js";

const app = express();
const port = Number(process.env.PORT ?? 4000);

app.use(cors());
app.use(express.json());

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", service: "race-dna-api" });
});

app.get("/api/races", (_req, res) => {
  res.json(
    races.map((race) => ({
      id: race.id,
      name: race.name,
      course: race.course,
      distanceFurlongs: race.distanceFurlongs,
      going: race.going,
      runnerCount: race.runners.length,
    })),
  );
});

app.get("/api/races/:id/analysis", (req, res) => {
  const race = getRaceById(req.params.id);
  if (!race) {
    res.status(404).json({ error: `Race '${req.params.id}' not found` });
    return;
  }
  res.json(analyzeRace(race));
});

app.listen(port, () => {
  console.log(`RaceDNA API listening on http://localhost:${port}`);
});
