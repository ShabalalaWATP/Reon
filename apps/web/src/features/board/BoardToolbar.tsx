import type {
  BoardColumn,
  BoardFilters,
  BoardItemType,
  SavedBoardView,
} from "../../lib/api/boardTypes";
import type { TeamMember } from "../../lib/api/teamTypes";
import {
  allBoardColumns,
  boardLabel,
  builtInBoardViews,
  filtersActive,
} from "./boardPresentation";

type Props = {
  filters: BoardFilters;
  mode: "board" | "table";
  people: TeamMember[];
  savedViews: SavedBoardView[];
  userId: string;
  viewName: string;
  canManage: boolean;
  saving: boolean;
  onChange: (filters: BoardFilters) => void;
  onDeleteView: (view: SavedBoardView) => void;
  onModeChange: (mode: "board" | "table") => void;
  onOpenSettings: () => void;
  onSaveView: () => void;
  onViewNameChange: (name: string) => void;
};

export function BoardToolbar(props: Props) {
  const activeCount = [
    props.filters.columns.length,
    props.filters.priorities.length,
    props.filters.ownerUserId ? 1 : 0,
    props.filters.itemTypes.length,
    props.filters.dueBefore ? 1 : 0,
  ].reduce((total, value) => total + value, 0);
  return (
    <section aria-label="Board controls" className="board-toolbar">
      <header className="board-toolbar__heading">
        <div>
          <span>Camunda-derived service work</span>
          <h2>Team delivery</h2>
          <p>Requests use named workflow actions. Internal work packages use explicit, audited planning moves.</p>
        </div>
        <div className="board-toolbar__actions">
          {props.canManage ? <button className="button button--quiet" onClick={props.onOpenSettings} type="button">Board settings</button> : null}
        </div>
      </header>

      <div className="board-command-row">
        <label className="form-field board-search">Search work
          <input
            onChange={(event) => props.onChange({ ...props.filters, search: event.target.value })}
            placeholder="Reference or title"
            type="search"
            value={props.filters.search}
          />
        </label>
        <div aria-label="Board presentation" className="board-mode">
          <button aria-pressed={props.mode === "board"} onClick={() => props.onModeChange("board")} type="button">Board</button>
          <button aria-pressed={props.mode === "table"} onClick={() => props.onModeChange("table")} type="button">Table</button>
        </div>
        {filtersActive(props.filters) ? <button className="button button--quiet" onClick={() => props.onChange({ search: "", columns: [], priorities: [], ownerUserId: null, itemTypes: [], dueBefore: null })} type="button">Clear view</button> : null}
      </div>

      <nav aria-label="Useful board views" className="board-presets">
        {builtInBoardViews(props.userId).map((view) => (
          <button key={view.name} onClick={() => props.onChange(view.filters)} type="button">{view.name}</button>
        ))}
      </nav>

      <div className="board-disclosure-row">
        <details className="board-disclosure">
          <summary>Filters{activeCount ? ` · ${activeCount} active` : ""}</summary>
          <div className="board-filter-grid">
            <SelectFilter
              emptyLabel="All item types"
              label="Item type"
              onChange={(value) => props.onChange({ ...props.filters, itemTypes: value ? [value as BoardItemType] : [] })}
              options={[["SERVICE_REQUEST", "Service requests"], ["WORK_PACKAGE", "Work packages"]]}
              value={props.filters.itemTypes[0] ?? ""}
            />
            <SelectFilter
              emptyLabel="All statuses"
              label="Status"
              onChange={(value) => props.onChange({ ...props.filters, columns: value ? [value as BoardColumn] : [] })}
              options={allBoardColumns.map((column) => [column, boardLabel(column)])}
              value={props.filters.columns[0] ?? ""}
            />
            <SelectFilter
              emptyLabel="All priorities"
              label="Priority"
              onChange={(value) => props.onChange({ ...props.filters, priorities: value ? [value] : [] })}
              options={["LOW", "MEDIUM", "HIGH", "URGENT"].map((value) => [value, boardLabel(value)])}
              value={props.filters.priorities[0] ?? ""}
            />
            <SelectFilter
              emptyLabel="All owners"
              label="Owner"
              onChange={(value) => props.onChange({ ...props.filters, ownerUserId: value || null })}
              options={props.people.filter((item) => item.state === "CURRENT").map((item) => [item.accountId, item.displayName])}
              value={props.filters.ownerUserId ?? ""}
            />
            <label className="form-field">Due by
              <input onChange={(event) => props.onChange({ ...props.filters, dueBefore: event.target.value || null })} type="date" value={props.filters.dueBefore ?? ""} />
            </label>
          </div>
        </details>

        <details className="board-disclosure">
          <summary>Saved views · {props.savedViews.length}</summary>
          <div className="saved-view-row">
            {props.savedViews.map((view) => <span className="saved-view" key={view.id}><button onClick={() => props.onChange(view.filters)} type="button">{view.name}</button><button aria-label={`Delete ${view.name}`} onClick={() => props.onDeleteView(view)} type="button">×</button></span>)}
            {props.savedViews.length === 0 ? <span className="inline-empty">No personal views saved.</span> : null}
            <label className="form-field">New saved view name<input minLength={3} onChange={(event) => props.onViewNameChange(event.target.value)} value={props.viewName} /></label>
            <button className="button" disabled={props.viewName.length < 3 || props.saving} onClick={props.onSaveView} type="button">Save current view</button>
          </div>
        </details>
      </div>
    </section>
  );
}

function SelectFilter({ emptyLabel, label, onChange, options, value }: { emptyLabel: string; label: string; onChange: (value: string) => void; options: string[][]; value: string }) {
  return <label className="form-field">{label}<select onChange={(event) => onChange(event.target.value)} value={value}><option value="">{emptyLabel}</option>{options.map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label>;
}
