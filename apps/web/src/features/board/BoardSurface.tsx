import type {
  BoardColumn,
  BoardItem,
  WorkPackage,
} from "../../lib/api/boardTypes";
import type { PlanningCockpit } from "../../lib/api/planningEvolutionTypes";
import {
  activeBoardColumns,
  archiveBoardColumns,
  boardLabel,
  daysInState,
  dueSignal,
  exceptionBoardColumns,
} from "./boardPresentation";

type Context = {
  packages?: WorkPackage[];
  planning?: PlanningCockpit;
};

export function BoardSurface({
  columnCounts,
  context,
  filteredColumns,
  items,
  mode,
  onInspect,
  showArchive,
  showExceptions,
  totalCount,
  wipLimits,
  onShowArchive,
  onShowExceptions,
}: {
  columnCounts: Partial<Record<BoardColumn, number>>;
  context: Context;
  filteredColumns: BoardColumn[];
  items: BoardItem[];
  mode: "board" | "table";
  onInspect: (item: BoardItem) => void;
  showArchive: boolean;
  showExceptions: boolean;
  totalCount: number;
  wipLimits: Record<string, number>;
  onShowArchive: () => void;
  onShowExceptions: () => void;
}) {
  if (mode === "table") {
    return <BoardTable items={items} onInspect={onInspect} totalCount={totalCount} />;
  }
  const selected = filteredColumns.length ? filteredColumns : activeBoardColumns;
  const customSelection = filteredColumns.length > 0;
  return (
    <div className="board-flow">
      <BoardColumns
        columnCounts={columnCounts}
        columns={selected}
        context={context}
        items={items}
        onInspect={onInspect}
        wipLimits={wipLimits}
      />
      {!customSelection ? (
        <div className="board-secondary-groups">
          <BoardGroupToggle
            columns={exceptionBoardColumns}
            columnCounts={columnCounts}
            label="Exceptions and downstream"
            onClick={onShowExceptions}
            open={showExceptions}
          />
          <BoardGroupToggle
            columns={archiveBoardColumns}
            columnCounts={columnCounts}
            label="Completed and cancelled"
            onClick={onShowArchive}
            open={showArchive}
          />
        </div>
      ) : null}
      {!customSelection && showExceptions ? <BoardColumns columnCounts={columnCounts} columns={exceptionBoardColumns} context={context} items={items} onInspect={onInspect} wipLimits={wipLimits} /> : null}
      {!customSelection && showArchive ? <BoardColumns columnCounts={columnCounts} columns={archiveBoardColumns} context={context} items={items} onInspect={onInspect} wipLimits={wipLimits} /> : null}
      <p className="board-result-note">Showing {items.length} of {totalCount} matching work items. Column totals cover the complete filtered result.</p>
    </div>
  );
}

function BoardColumns({
  columnCounts,
  columns,
  context,
  items,
  onInspect,
  wipLimits,
}: {
  columnCounts: Partial<Record<BoardColumn, number>>;
  columns: BoardColumn[];
  context: Context;
  items: BoardItem[];
  onInspect: (item: BoardItem) => void;
  wipLimits: Record<string, number>;
}) {
  return (
    <section aria-label="Team Kanban board" className="kanban">
      {columns.map((column) => {
        const cards = items.filter((item) => item.column === column);
        const count = columnCounts[column] ?? 0;
        const limit = wipLimits[column];
        const breached = Boolean(limit && count > limit);
        return (
          <section className={breached ? "kanban-column kanban-column--breached" : "kanban-column"} key={column}>
            <header><div><h3>{boardLabel(column)}</h3>{limit ? <small>Limit {limit}</small> : null}</div><span aria-label={`${count} total`}>{count}</span></header>
            {breached ? <p className="kanban-warning" role="status">WIP limit exceeded by {count - limit}</p> : null}
            {cards.map((item) => <BoardCard context={context} item={item} key={`${item.itemType}-${item.id}`} onInspect={onInspect} />)}
            {cards.length === 0 ? <p className="kanban-empty">No items on this page.</p> : null}
          </section>
        );
      })}
    </section>
  );
}

function BoardCard({ context, item, onInspect }: { context: Context; item: BoardItem; onInspect: (item: BoardItem) => void }) {
  const signal = dueSignal(item.dueOn);
  const lane = context.planning?.lanes.flatMap((value) => value.items).find((value) => value.id === item.id);
  const checklist = context.planning?.checklists.find((value) => value.packageId === item.id);
  const packageItem = context.packages?.find((value) => value.id === item.id);
  const reserved = packageItem?.reservations.filter((value) => value.status === "ACTIVE").reduce((total, value) => total + value.minutes, 0) ?? 0;
  const signals = [
    item.itemType === "SERVICE_REQUEST" && item.column === "BLOCKED" ? "Waiting for customer" : null,
    !item.ownerUserId ? "Unassigned" : null,
    lane?.blockerAgeDays !== null && lane?.blockerAgeDays !== undefined ? `${lane.blockerAgeDays} blocked days` : null,
    lane?.dependencyWarningCount ? `${lane.dependencyWarningCount} dependency warning${lane.dependencyWarningCount === 1 ? "" : "s"}` : null,
    checklist ? `${checklist.completedCount}/${checklist.totalCount} checklist` : null,
    reserved ? `${Math.round(reserved / 60 * 10) / 10}h reserved` : null,
  ].filter((value): value is string => Boolean(value));
  return (
    <article className={`board-card board-card--${signal.tone}`}>
      <button className="board-card__open" onClick={() => onInspect(item)} type="button">
        <span>{item.itemType === "SERVICE_REQUEST" ? "Service request" : "Work package"} · {item.reference}</span>
        <h4>{item.title}</h4>
        <div className="board-card__meta"><strong>{boardLabel(item.priority)}</strong><span>{signal.label}</span></div>
        <dl><div><dt>Owner</dt><dd>{item.ownerDisplayName ?? "Unassigned"}</dd></div><div><dt>Due</dt><dd>{item.dueOn}</dd></div></dl>
        <small>{daysInState(item.changedAt)}</small>
        {packageItem?.contributors.length ? <p>With {packageItem.contributors.map((value) => value.displayName).join(", ")}</p> : null}
        {signals.length ? <ul className="board-card__signals">{signals.map((value) => <li key={value}>{value}</li>)}</ul> : null}
        <em>Inspect work</em>
      </button>
    </article>
  );
}

function BoardGroupToggle({ columns, columnCounts, label, onClick, open }: { columns: BoardColumn[]; columnCounts: Partial<Record<BoardColumn, number>>; label: string; onClick: () => void; open: boolean }) {
  const count = columns.reduce((total, column) => total + (columnCounts[column] ?? 0), 0);
  return <button aria-expanded={open} onClick={onClick} type="button"><span>{label}</span><strong>{count}</strong><small>{open ? "Collapse" : "Show lanes"}</small></button>;
}

function BoardTable({ items, onInspect, totalCount }: { items: BoardItem[]; onInspect: (item: BoardItem) => void; totalCount: number }) {
  return <div className="team-table-wrap"><table className="team-table"><caption>Filtered team work, showing {items.length} of {totalCount}</caption><thead><tr><th>Reference</th><th>Title</th><th>Type</th><th>Status</th><th>Owner</th><th>Due</th><th>Age</th></tr></thead><tbody>{items.map((item) => <tr key={`${item.itemType}-${item.id}`}><th>{item.reference}</th><td><button className="table-link" onClick={() => onInspect(item)} type="button">{item.title}</button></td><td>{boardLabel(item.itemType)}</td><td>{boardLabel(item.column)}</td><td>{item.ownerDisplayName ?? "Unassigned"}</td><td>{item.dueOn}</td><td>{daysInState(item.changedAt)}</td></tr>)}</tbody></table></div>;
}
