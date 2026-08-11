import { useState } from "react";

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

type DragState = {
  dragging: BoardItem | null;
  onDragStart: (item: BoardItem) => void;
  onDragEnd: () => void;
  onDropColumn: (column: BoardColumn) => void;
};

export function BoardSurface({
  columnCounts,
  context,
  filteredColumns,
  items,
  mode,
  moving = false,
  onInspect,
  onMove,
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
  moving?: boolean;
  onInspect: (item: BoardItem) => void;
  onMove?: (item: BoardItem, target: BoardColumn, reason: string) => Promise<void>;
  showArchive: boolean;
  showExceptions: boolean;
  totalCount: number;
  wipLimits: Record<string, number>;
  onShowArchive: () => void;
  onShowExceptions: () => void;
}) {
  const [dragging, setDragging] = useState<BoardItem | null>(null);
  const [pending, setPending] = useState<{ item: BoardItem; target: BoardColumn } | null>(null);
  if (mode === "table") {
    return <BoardTable items={items} onInspect={onInspect} totalCount={totalCount} />;
  }
  const selected = filteredColumns.length ? filteredColumns : activeBoardColumns;
  const customSelection = filteredColumns.length > 0;
  const drag: DragState = {
    dragging,
    onDragStart: (item) => setDragging(item),
    onDragEnd: () => setDragging(null),
    onDropColumn: (column) => {
      if (dragging && onMove && dragging.column !== column && dragging.availableColumns.includes(column)) {
        setPending({ item: dragging, target: column });
      }
      setDragging(null);
    },
  };
  return (
    <div className="board-flow">
      <BoardColumns
        columnCounts={columnCounts}
        columns={selected}
        context={context}
        drag={drag}
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
      {!customSelection && showExceptions ? <BoardColumns columnCounts={columnCounts} columns={exceptionBoardColumns} context={context} drag={drag} items={items} onInspect={onInspect} wipLimits={wipLimits} /> : null}
      {!customSelection && showArchive ? <BoardColumns columnCounts={columnCounts} columns={archiveBoardColumns} context={context} drag={drag} items={items} onInspect={onInspect} wipLimits={wipLimits} /> : null}
      <p className="board-result-note">Showing {items.length} of {totalCount} matching work items. Column totals cover the complete filtered result. Drag a work-package card to move it; service requests change stage through their named workflow action.</p>
      {pending ? <PackageMoveDialog item={pending.item} moving={moving} onCancel={() => setPending(null)} onConfirm={async (reason) => { await onMove?.(pending.item, pending.target, reason); setPending(null); }} target={pending.target} /> : null}
    </div>
  );
}

function BoardColumns({
  columnCounts,
  columns,
  context,
  drag,
  items,
  onInspect,
  wipLimits,
}: {
  columnCounts: Partial<Record<BoardColumn, number>>;
  columns: BoardColumn[];
  context: Context;
  drag: DragState;
  items: BoardItem[];
  onInspect: (item: BoardItem) => void;
  wipLimits: Record<string, number>;
}) {
  const [over, setOver] = useState<BoardColumn | null>(null);
  const droppable = (column: BoardColumn) =>
    Boolean(drag.dragging && drag.dragging.column !== column && drag.dragging.availableColumns.includes(column));
  return (
    <section aria-label="Team Kanban board" className="kanban">
      {columns.map((column) => {
        const cards = items.filter((item) => item.column === column);
        const count = columnCounts[column] ?? 0;
        const limit = wipLimits[column];
        const breached = Boolean(limit && count > limit);
        const canDrop = droppable(column);
        const classes = ["kanban-column"];
        if (breached) classes.push("kanban-column--breached");
        if (canDrop) classes.push("kanban-column--droppable");
        if (over === column && canDrop) classes.push("kanban-column--over");
        return (
          <section
            className={classes.join(" ")}
            key={column}
            onDragLeave={() => setOver((value) => (value === column ? null : value))}
            onDragOver={(event) => { if (canDrop) { event.preventDefault(); setOver(column); } }}
            onDrop={(event) => { if (canDrop) { event.preventDefault(); drag.onDropColumn(column); } setOver(null); }}
          >
            <header><div><h3>{boardLabel(column)}</h3>{limit ? <small>Limit {limit}</small> : null}</div><span aria-label={`${count} total`}>{count}</span></header>
            {breached ? <p className="kanban-warning" role="status">WIP limit exceeded by {count - limit}</p> : null}
            {cards.map((item) => <BoardCard context={context} drag={drag} item={item} key={`${item.itemType}-${item.id}`} onInspect={onInspect} />)}
            {cards.length === 0 ? <p className="kanban-empty">{canDrop ? "Drop here to move" : "No items on this page."}</p> : null}
          </section>
        );
      })}
    </section>
  );
}

function BoardCard({ context, drag, item, onInspect }: { context: Context; drag: DragState; item: BoardItem; onInspect: (item: BoardItem) => void }) {
  const signal = dueSignal(item.dueOn);
  const lane = context.planning?.lanes.flatMap((value) => value.items).find((value) => value.id === item.id);
  const checklist = context.planning?.checklists.find((value) => value.packageId === item.id);
  const packageItem = context.packages?.find((value) => value.id === item.id);
  const reserved = packageItem?.reservations.filter((value) => value.status === "ACTIVE").reduce((total, value) => total + value.minutes, 0) ?? 0;
  const draggable = item.itemType === "WORK_PACKAGE" && item.availableColumns.length > 0;
  const signals = [
    item.itemType === "SERVICE_REQUEST" && item.column === "BLOCKED" ? "Waiting for customer" : null,
    !item.ownerUserId ? "Unassigned" : null,
    lane?.blockerAgeDays !== null && lane?.blockerAgeDays !== undefined ? `${lane.blockerAgeDays} blocked days` : null,
    lane?.dependencyWarningCount ? `${lane.dependencyWarningCount} dependency warning${lane.dependencyWarningCount === 1 ? "" : "s"}` : null,
    checklist ? `${checklist.completedCount}/${checklist.totalCount} checklist` : null,
    reserved ? `${Math.round(reserved / 60 * 10) / 10}h reserved` : null,
  ].filter((value): value is string => Boolean(value));
  const isDragging = drag.dragging?.id === item.id && drag.dragging.itemType === item.itemType;
  return (
    <article
      className={`board-card board-card--${signal.tone}${draggable ? " board-card--draggable" : ""}${isDragging ? " board-card--dragging" : ""}`}
      draggable={draggable}
      onDragEnd={draggable ? drag.onDragEnd : undefined}
      onDragStart={draggable ? (event) => { if (event.dataTransfer) event.dataTransfer.effectAllowed = "move"; drag.onDragStart(item); } : undefined}
    >
      {draggable ? <span aria-hidden="true" className="board-card__grip">⠿</span> : null}
      <button className="board-card__open" onClick={() => onInspect(item)} type="button">
        <span>{item.itemType === "SERVICE_REQUEST" ? "Service request" : "Work package"} · {item.reference}</span>
        <h4>{item.title}</h4>
        <div className="board-card__meta"><strong>{boardLabel(item.priority)}</strong><span>{signal.label}</span></div>
        <dl><div><dt>Owner</dt><dd>{item.ownerDisplayName ?? "Unassigned"}</dd></div><div><dt>Due</dt><dd>{item.dueOn}</dd></div></dl>
        <small>{daysInState(item.changedAt)}</small>
        {packageItem?.contributors.length ? <p>With {packageItem.contributors.map((value) => value.displayName).join(", ")}</p> : null}
        {signals.length ? <ul className="board-card__signals">{signals.map((value) => <li key={value}>{value}</li>)}</ul> : null}
        <em>{item.itemType === "WORK_PACKAGE" ? "Inspect or move" : "Inspect work"}</em>
      </button>
    </article>
  );
}

function PackageMoveDialog({ item, moving, onCancel, onConfirm, target }: { item: BoardItem; moving: boolean; onCancel: () => void; onConfirm: (reason: string) => Promise<void>; target: BoardColumn }) {
  const [reason, setReason] = useState("");
  const [failed, setFailed] = useState(false);
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setFailed(false);
    void onConfirm(reason).catch(() => setFailed(true));
  };
  return (
    <div aria-label="Confirm package move" className="board-move-dialog" role="dialog">
      <form className="board-move-dialog__card" onSubmit={submit}>
        <span>Move work package</span>
        <h3>{item.title}</h3>
        <p>Move to <strong>{boardLabel(target)}</strong>. Every package move is recorded with your reason.</p>
        <label className="form-field">Reason<span className="field-hint">Required, at least 10 characters</span><textarea autoFocus maxLength={500} minLength={10} onChange={(event) => setReason(event.target.value)} required rows={3} value={reason} /></label>
        {failed ? <p className="form-banner form-banner--error" role="alert">The move could not be saved. Your reason is kept; try again.</p> : null}
        <div className="board-move-dialog__actions">
          <button className="button button--quiet" onClick={onCancel} type="button">Cancel</button>
          <button className="button button--primary" disabled={moving || reason.trim().length < 10} type="submit">{moving ? "Moving…" : `Move to ${boardLabel(target)}`}</button>
        </div>
      </form>
    </div>
  );
}

function BoardGroupToggle({ columns, columnCounts, label, onClick, open }: { columns: BoardColumn[]; columnCounts: Partial<Record<BoardColumn, number>>; label: string; onClick: () => void; open: boolean }) {
  const count = columns.reduce((total, column) => total + (columnCounts[column] ?? 0), 0);
  return <button aria-expanded={open} onClick={onClick} type="button"><span>{label}</span><strong>{count}</strong><small>{open ? "Collapse" : "Show lanes"}</small></button>;
}

function BoardTable({ items, onInspect, totalCount }: { items: BoardItem[]; onInspect: (item: BoardItem) => void; totalCount: number }) {
  return <div className="team-table-wrap"><table className="team-table"><caption>Filtered team work, showing {items.length} of {totalCount}</caption><thead><tr><th>Reference</th><th>Title</th><th>Type</th><th>Status</th><th>Owner</th><th>Due</th><th>Age</th></tr></thead><tbody>{items.map((item) => <tr key={`${item.itemType}-${item.id}`}><th>{item.reference}</th><td><button className="table-link" onClick={() => onInspect(item)} type="button">{item.title}</button></td><td>{boardLabel(item.itemType)}</td><td>{boardLabel(item.column)}</td><td>{item.ownerDisplayName ?? "Unassigned"}</td><td>{item.dueOn}</td><td>{daysInState(item.changedAt)}</td></tr>)}</tbody></table></div>;
}
