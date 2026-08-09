import { useEffect, useMemo, useState } from "react";
import { fetchAnalysis, fetchRaces } from "./api";
import { RunnerCard } from "./components/RunnerCard";
import type { RaceAnalysis, RaceSummary } from "./types";

export function App() {
  const [races, setRaces] = useState<RaceSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<RaceAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRaces()
      .then((data) => {
        setRaces(data);
        setSelectedId(data[0]?.id ?? null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    setError(null);
    fetchAnalysis(selectedId)
      .then(setAnalysis)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedId]);

  const topPick = useMemo(
    () => analysis?.runners.find((runner) => runner.rank === 1) ?? null,
    [analysis],
  );

  return (
    <div className="app">
      <header className="masthead">
        <div className="brand">
          <span className="brand-mark">RaceDNA</span>
          <span className="brand-tag">Horse Racing Analysis</span>
        </div>
        <p className="masthead-sub">
          Model-driven form ratings, distance and going fit, and win probabilities.
        </p>
      </header>

      <div className="layout">
        <aside className="races">
          <h2>Race card</h2>
          <ul>
            {races.map((race) => (
              <li key={race.id}>
                <button
                  type="button"
                  className={race.id === selectedId ? "race-btn active" : "race-btn"}
                  onClick={() => setSelectedId(race.id)}
                >
                  <span className="race-name">{race.name}</span>
                  <span className="race-meta">
                    {race.course} · {race.distanceFurlongs}f · {race.going} · {race.runnerCount}{" "}
                    runners
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="analysis">
          {error && <div className="banner error">{error}</div>}
          {loading && <div className="banner">Crunching the numbers…</div>}

          {analysis && !loading && (
            <>
              <div className="analysis-head">
                <h2>{analysis.name}</h2>
                <p>
                  {analysis.course} · {analysis.distanceFurlongs}f · going: {analysis.going}
                </p>
                {topPick && (
                  <div className="top-pick">
                    <span className="top-pick-label">Model top pick</span>
                    <span className="top-pick-name">{topPick.name}</span>
                    <span className="top-pick-prob">
                      {Math.round(topPick.winProbability * 100)}% win chance
                    </span>
                  </div>
                )}
              </div>

              <ol className="runner-list">
                {analysis.runners.map((runner) => (
                  <RunnerCard key={runner.horseId} runner={runner} />
                ))}
              </ol>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
