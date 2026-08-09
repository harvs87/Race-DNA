/** Minimal CSV parser that supports quoted fields and commas inside quotes. */
export function parseCsv(text: string): { headers: string[]; rows: Record<string, string>[] } {
  const lines = splitCsvLines(text.trim().replace(/^\uFEFF/, ""));
  if (lines.length === 0) {
    return { headers: [], rows: [] };
  }

  const headers = splitCsvRow(lines[0]).map((header) => header.trim());
  const rows = lines
    .slice(1)
    .filter((line) => line.trim().length > 0)
    .map((line) => {
      const cells = splitCsvRow(line);
      const row: Record<string, string> = {};
      headers.forEach((header, index) => {
        row[header] = (cells[index] ?? "").trim();
      });
      return row;
    });

  return { headers, rows };
}

function splitCsvLines(text: string): string[] {
  const lines: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (char === '"') {
      inQuotes = !inQuotes;
      current += char;
      continue;
    }
    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && text[i + 1] === "\n") i += 1;
      lines.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  if (current.length > 0) lines.push(current);
  return lines;
}

function splitCsvRow(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === "," && !inQuotes) {
      cells.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  cells.push(current);
  return cells;
}

export function getField(row: Record<string, string>, ...aliases: string[]): string {
  const keys = Object.keys(row);
  for (const alias of aliases) {
    const exact = keys.find((key) => key.toLowerCase() === alias.toLowerCase());
    if (exact && row[exact] !== undefined && row[exact] !== "") return row[exact];
  }
  return "";
}

export function parseNumber(value: string): number | undefined {
  if (!value) return undefined;
  const cleaned = value.replace(/^'/, "").replace(/%$/, "").replace(/,/g, "").trim();
  if (!cleaned) return undefined;
  const num = Number(cleaned);
  return Number.isFinite(num) ? num : undefined;
}

/**
 * Parse a TAB / saddlecloth number.
 * Rejects non-integers so "1.0" style junk and empty values cannot fuzzy-match.
 */
export function parseTabNumber(value: string): number | undefined {
  if (!value) return undefined;
  const cleaned = value.replace(/^'/, "").trim();
  if (!/^\d+$/.test(cleaned)) return undefined;
  const num = Number(cleaned);
  if (!Number.isInteger(num) || num <= 0) return undefined;
  return num;
}

export function detectMeetingCsvFormat(headers: string[]): "punting-form" | "wizard" | "unknown" {
  const lower = headers.map((header) => header.toLowerCase());
  if (lower.includes("tabno") || lower.includes("meetingid") || lower.includes("last10")) {
    return "punting-form";
  }
  if (lower.includes("tab number") || lower.includes("meeting")) {
    return "wizard";
  }
  return "unknown";
}
