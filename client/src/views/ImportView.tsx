import { useState } from "react";
import type { ImportReport } from "../types";

interface Props {
  title: string;
  description: string;
  sampleHint: string;
  onImport: (csv: string) => Promise<ImportReport>;
  onImported?: (report: ImportReport) => void;
}

export function ImportView({ title, description, sampleHint, onImport, onImported }: Props) {
  const [csv, setCsv] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);

  async function runImport(text: string) {
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      const result = await onImport(text);
      setReport(result);
      onImported?.(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="import-view">
      <div className="analysis-head">
        <h2>{title}</h2>
        <p>{description}</p>
      </div>

      <div className="panel-block">
        <label className="file-label">
          <span>Choose CSV file</span>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              const text = await file.text();
              setCsv(text);
              await runImport(text);
            }}
          />
        </label>

        <p className="muted sample-hint">{sampleHint}</p>

        <label className="paste-label" htmlFor={`csv-${title}`}>
          Or paste CSV
        </label>
        <textarea
          id={`csv-${title}`}
          className="csv-input"
          rows={12}
          value={csv}
          onChange={(event) => setCsv(event.target.value)}
          placeholder="Paste CSV contents here…"
        />

        <div className="import-actions">
          <button
            type="button"
            className="primary-btn"
            disabled={busy || !csv.trim()}
            onClick={() => runImport(csv)}
          >
            {busy ? "Importing…" : "Import CSV"}
          </button>
        </div>
      </div>

      {error && <div className="banner error">{error}</div>}

      {report && (
        <div className="panel-block">
          <h3>Import report</h3>
          <p>{report.message}</p>
          <ul className="plain-list">
            <li>Rows parsed: {report.rowsParsed}</li>
            <li>Races affected: {report.racesAffected}</li>
            <li>Runners created: {report.runnersCreated}</li>
            <li>Runners matched: {report.runnersMatched}</li>
            <li>Runners unmatched: {report.runnersUnmatched}</li>
            {report.meetingId && <li>Meeting id: {report.meetingId}</li>}
          </ul>
          {report.unmatched.length > 0 && (
            <>
              <h4>Unmatched rows</h4>
              <ul className="plain-list">
                {report.unmatched.map((item, index) => (
                  <li key={`${item.meeting}-${item.raceNumber}-${item.tabNumber}-${index}`}>
                    {item.meeting} R{item.raceNumber}
                    {item.tabNumber !== undefined ? ` TAB ${item.tabNumber}` : ""}
                    {item.horse ? ` (${item.horse})` : ""} — {item.reason}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
