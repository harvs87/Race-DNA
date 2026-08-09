import type { HorseAnalysis } from "../types";

interface Props {
  runner: HorseAnalysis;
}

export function RunnerCard({ runner }: Props) {
  return (
    <li className={runner.rank === 1 ? "runner top" : "runner"}>
      <div className="runner-top">
        <div className="runner-id">
          <span className="tab-number" title="TAB number">
            {runner.tabNumber}
          </span>
          <div>
            <span className="runner-name">
              <span className="rank-inline">#{runner.rank}</span> {runner.name}
            </span>
            <span className="runner-verdict">{runner.verdict}</span>
            <span className="runner-meta-line">
              {runner.winOdds !== undefined && (
                <span className="odds-chip">
                  Win {runner.winOdds.toFixed(2)}
                  {runner.placeOdds !== undefined ? ` / Plc ${runner.placeOdds.toFixed(2)}` : ""}
                </span>
              )}
              {runner.finishPosition !== undefined && (
                <span className="result-chip">Finished {runner.finishPosition}</span>
              )}
            </span>
          </div>
        </div>
        <div className="runner-scores">
          <div className="score-block">
            <span className="score-value">{runner.dnaScore.toFixed(1)}</span>
            <span className="score-label">DNA score</span>
          </div>
          <div className="score-block">
            <span className="score-value">{Math.round(runner.winProbability * 100)}%</span>
            <span className="score-label">win prob</span>
          </div>
        </div>
      </div>

      <div className="factors">
        {runner.factors.map((factor) => (
          <div className="factor" key={factor.label}>
            <div className="factor-head">
              <span>{factor.label}</span>
              <span className="factor-score">{Math.round(factor.score)}</span>
            </div>
            <div className="factor-bar">
              <div
                className="factor-fill"
                style={{ width: `${Math.max(2, Math.min(100, factor.score))}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </li>
  );
}
