import { RunnerCard } from "../components/RunnerCard";
import type { RaceAnalysis, RaceSummary } from "../types";

interface Props {
  races: RaceSummary[];
  selectedId: string | null;
  analysis: RaceAnalysis | null;
  loading: boolean;
  error: string | null;
  onSelectRace: (id: string) => void;
}

export function RaceDnaView({
  races,
  selectedId,
  analysis,
  loading,
  error,
  onSelectRace,
}: Props) {
  const topPick = analysis?.runners.find((runner) => runner.rank === 1) ?? null;

  return (
    <div className="race-dna-layout">
      <aside className="races">
        <h2>Race card</h2>
        <ul>
          {races.map((race) => (
            <li key={race.id}>
              <button
                type="button"
                className={race.id === selectedId ? "race-btn active" : "race-btn"}
                onClick={() => onSelectRace(race.id)}
              >
                <span className="race-name">{race.name}</span>
                <span className="race-meta">
                  {race.course}
                  {race.raceNumber ? ` R${race.raceNumber}` : ""} ·{" "}
                  {race.distanceMeters
                    ? `${race.distanceMeters}m`
                    : `${race.distanceFurlongs}f`}{" "}
                  · {race.going} · {race.runnerCount} runners
                </span>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="analysis">
        {error && <div className="banner error">{error}</div>}
        {loading && <div className="banner">Crunching the numbers…</div>}

        {analysis && !loading && (
          <>
            <div className="analysis-head">
              <h2>{analysis.name}</h2>
              <p>
                {analysis.course}
                {analysis.raceNumber ? ` · R${analysis.raceNumber}` : ""} ·{" "}
                {analysis.distanceMeters
                  ? `${analysis.distanceMeters}m`
                  : `${analysis.distanceFurlongs}f`}{" "}
                · going: {analysis.going}
              </p>
              {topPick && (
                <div className="top-pick">
                  <span className="top-pick-label">Model top pick</span>
                  <span className="top-pick-name">
                    [{topPick.tabNumber}] {topPick.name}
                  </span>
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
      </section>
    </div>
  );
}
