import type { AppView } from "../types";

const items: Array<{ id: AppView; label: string; hint: string }> = [
  { id: "dashboard", label: "Dashboard", hint: "Meetings overview" },
  { id: "meeting", label: "Meeting", hint: "Races & runners" },
  { id: "meeting-archive", label: "Meeting Archive", hint: "Reopen imports" },
  { id: "race-dna", label: "Race DNA", hint: "Model analysis" },
  { id: "import-meeting", label: "Import Meeting CSV", hint: "Punting Form" },
  { id: "import-results", label: "Import Results", hint: "Finish positions" },
  { id: "import-odds", label: "Import TAB Odds", hint: "TAB / TABtouch" },
];

interface Props {
  active: AppView;
  onSelect: (view: AppView) => void;
}

export function SidebarNav({ active, onSelect }: Props) {
  return (
    <nav className="side-nav" aria-label="Primary">
      <h2>Navigate</h2>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className={item.id === active ? "nav-btn active" : "nav-btn"}
              onClick={() => onSelect(item.id)}
            >
              <span className="nav-label">{item.label}</span>
              <span className="nav-hint">{item.hint}</span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
