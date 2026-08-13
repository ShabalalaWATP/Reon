import { useState } from "react";

import type {
  BoardColumn,
  BoardItem,
  Iteration,
  WorkPackage,
} from "../../lib/api/boardTypes";
import { formatDate } from "../../lib/status";
import {
  activeBoardColumns,
  archiveBoardColumns,
  boardLabel,
  daysInState,
  dueSignal,
  exceptionBoardColumns,
  stateAgeDays,
} from "./boardPresentation";

const STALE_AFTER_DAYS = 5;

type Context = {
  packages?: WorkPackage[];
  iterations?: Iteration[];
};

type MenuMove = (item: BoardItem, target: BoardColumn) => void;

type DragState = {
  dragging: BoardItem | null;
  onDragStart: (item: BoardItem) => void;
  onDragEnd: () => void;
  onDropColumn: (column: BoardColumn) => void;
};

export function BoardSurface({
  activeColumns = activeBoardColumns,
  ariaLabel = "Team Kanban board",
  columnCounts = {},
  columnDescriptions = {},
  columnFilterActive = false,
  context,
  exceptionColumns = exceptionBoardColumns,
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
  archiveColumns = archiveBoardColumns,
  resultNote = "Drag a work-package card to move it; service requests change stage through their named workflow action.",
}: {
  activeColumns?: BoardColumn[];
  ariaLabel?: string;
  columnCounts: Partial<Record<BoardColumn, number>>;
  columnDescriptions?: Partial<Record<BoardColumn, string>>;
  columnFilterActive?: boolean;
  context: Context;
  exceptionColumns?: BoardColumn[];
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
  archiveColumns?: BoardColumn[];
  resultNote?: string;
}) {
  const [dragging, setDragging] = useState<BoardItem | null>(null);
  const [pending, setPending] = useState<{ item: BoardItem; target: BoardColumn } | null>(null);
  if (mode === "table") {
    return <BoardTable ariaLabel={ariaLabel} items={items} onInspect={onInspect} totalCount={totalCount} />;
  }
  const customSelection = columnFilterActive || filteredColumns.length > 0;
  const selected = customSelection ? filteredColumns : activeColumns;
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
  const menuMove: MenuMove | undefined = onMove
    ? (item, target) => setPending({ item, target })
    : undefined;
  return (
    <div className="board-flow">
      <BoardColumns
        ariaLabel={ariaLabel}
        columnCounts={columnCounts}
        columnDescriptions={columnDescriptions}
        columns={selected}
        context={context}
        drag={drag}
        items={items}
        onInspect={onInspect}
        onMenuMove={menuMove}
        wipLimits={wipLimits}
      />
      {!customSelection ? (
        <div className="board-secondary-groups">
          {exceptionColumns.length ? <BoardGroupToggle
            columns={exceptionColumns}
            columnCounts={columnCounts}
            label="Exceptions and downstream"
            onClick={onShowExceptions}
            open={showExceptions}
          /> : null}
          {archiveColumns.length ? <BoardGroupToggle
            columns={archiveColumns}
            columnCounts={columnCounts}
            label="Completed and cancelled"
            onClick={onShowArchive}
            open={showArchive}
          /> : null}
        </div>
      ) : null}
      {!customSelection && showExceptions && exceptionColumns.length ? <BoardColumns ariaLabel={`${ariaLabel}, exceptions`} columnCounts={columnCounts} columnDescriptions={columnDescriptions} columns={exceptionColumns} context={context} drag={drag} items={items} onInspect={onInspect} onMenuMove={menuMove} wipLimits={wipLimits} /> : null}
      {!customSelection && showArchive && archiveColumns.length ? <BoardColumns ariaLabel={`${ariaLabel}, archive`} columnCounts={columnCounts} columnDescriptions={columnDescriptions} columns={archiveColumns} context={context} drag={drag} items={items} onInspect={onInspect} onMenuMove={menuMove} wipLimits={wipLimits} /> : null}
      <p className="board-result-note">Showing {items.length} of {totalCount} matching work items. Column totals cover the complete filtered result. {resultNote}</p>
      {pending ? <PackageMoveDialog item={pending.item} moving={moving} onCancel={() => setPending(null)} onConfirm={async (reason) => { await onMove?.(pending.item, pending.target, reason); setPending(null); }} target={pending.target} /> : null}
    </div>
  );
}

function BoardColumns({
  ariaLabel,
  columnCounts,
  columnDescriptions,
  columns,
  context,
  drag,
  items,
  onInspect,
  onMenuMove,
  wipLimits,
}: {
  ariaLabel: string;
  columnCounts: Partial<Record<BoardColumn, number>>;
  columnDescriptions: Partial<Record<BoardColumn, string>>;
  columns: BoardColumn[];
  context: Context;
  drag: DragState;
  items: BoardItem[];
  onInspect: (item: BoardItem) => void;
  onMenuMove?: MenuMove;
  wipLimits: Record<string, number>;
}) {
  const [over, setOver] = useState<BoardColumn | null>(null);
  const droppable = (column: BoardColumn) =>
    Boolean(drag.dragging && drag.dragging.column !== column && drag.dragging.availableColumns.includes(column));
  return (
    <section aria-label={ariaLabel} className="kanban">
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
        if (drag.dragging && !canDrop && drag.dragging.column !== column) classes.push("kanban-column--dimmed");
        return (
          <section
            className={classes.join(" ")}
            key={column}
            onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOver((value) => (value === column ? null : value)); }}
            onDragOver={(event) => { if (canDrop) { event.preventDefault(); setOver(column); } }}
            onDrop={(event) => { if (canDrop) { event.preventDefault(); drag.onDropColumn(column); } setOver(null); }}
          >
            <header><div><h3>{boardLabel(column)}</h3>{columnDescriptions[column] ? <p className="kanban-column__meaning">({columnDescriptions[column]})</p> : null}{limit ? <small>Limit {limit}</small> : null}</div><span aria-label={`${count} total`}>{count}</span></header>
            {limit ? <span aria-hidden="true" className="kanban-column__meter"><i style={{ width: `${Math.min(100, Math.round((count / limit) * 100))}%` }} /></span> : null}
            {breached ? <p className="kanban-warning" role="status">WIP limit exceeded by {count - limit}</p> : null}
            {cards.map((item) => <BoardCard context={context} drag={drag} item={item} key={`${item.itemType}-${item.id}`} onInspect={onInspect} onMenuMove={onMenuMove} />)}
            {cards.length === 0 ? <p className="kanban-empty">{canDrop ? "Drop here to move" : "No items on this page."}</p> : null}
            {canDrop && cards.length > 0 ? <p className="kanban-dropzone">Drop here to move</p> : null}
          </section>
        );
      })}
    </section>
  );
}

function BoardCard({ context, drag, item, onInspect, onMenuMove }: { context: Context; drag: DragState; item: BoardItem; onInspect: (item: BoardItem) => void; onMenuMove?: MenuMove }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const signal = dueSignal(item.dueOn);
  const packageItem = context.packages?.find((value) => value.id === item.id);
  const iteration = packageItem?.iterationId ? context.iterations?.find((value) => value.id === packageItem.iterationId) : undefined;
  const reserved = packageItem?.reservations.filter((value) => value.status === "ACTIVE").reduce((total, value) => total + value.minutes, 0) ?? 0;
  const draggable = item.itemType === "WORK_PACKAGE" && item.availableColumns.length > 0;
  const movable = draggable && Boolean(onMenuMove);
  const stale = stateAgeDays(item.changedAt) >= STALE_AFTER_DAYS && !archiveBoardColumns.includes(item.column);
  const signals = [
    item.itemType === "SERVICE_REQUEST" && item.column === "BLOCKED" ? "Waiting for customer" : null,
    !item.ownerUserId ? "Unassigned" : null,
    reserved ? `${Math.round(reserved / 60 * 10) / 10}h reserved` : null,
    iteration ? iteration.name : null,
  ].filter((value): value is string => Boolean(value));
  const isDragging = drag.dragging?.id === item.id && drag.dragging.itemType === item.itemType;
  return (
    <article
      className={`board-card board-card--${signal.tone}${draggable ? " board-card--draggable" : ""}${movable ? " board-card--actions" : ""}${isDragging ? " board-card--dragging" : ""}`}
      draggable={draggable}
      onDragEnd={draggable ? drag.onDragEnd : undefined}
      onDragStart={draggable ? (event) => { if (event.dataTransfer) event.dataTransfer.effectAllowed = "move"; drag.onDragStart(item); } : undefined}
    >
      {draggable ? <span aria-hidden="true" className="board-card__grip">⠿</span> : null}
      {movable ? (
        <div
          className="board-card__menu"
          onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setMenuOpen(false); }}
          onKeyDown={(event) => { if (event.key === "Escape") setMenuOpen(false); }}
        >
          <button aria-expanded={menuOpen} aria-label={`Move ${item.title}`} className="board-card__menu-toggle" onClick={() => setMenuOpen((value) => !value)} type="button">⋯</button>
          {menuOpen ? (
            <div aria-label={`Move ${item.title} to`} className="board-card__menu-list">
              {item.availableColumns.map((column) => (
                <button key={column} onClick={() => { setMenuOpen(false); onMenuMove?.(item, column); }} type="button">Move to {boardLabel(column)}</button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
      <button className="board-card__open" onClick={() => onInspect(item)} type="button">
        <span>{item.itemType === "SERVICE_REQUEST" ? "Service request" : "Work package"} · {item.reference}</span>
        <h4>{item.title}</h4>
        <div className="board-card__meta"><strong className={`board-card__priority board-card__priority--${item.priority.toLowerCase()}`}>{boardLabel(item.priority)}</strong><span>{signal.label}</span></div>
        <dl><div><dt>Owner</dt><dd>{item.ownerDisplayName ?? "Unassigned"}</dd></div><div><dt>Due</dt><dd>{formatDate(item.dueOn)}</dd></div></dl>
        <small className={stale ? "board-card__age board-card__age--stale" : "board-card__age"}>{daysInState(item.changedAt)}</small>
        {packageItem?.contributors.length ? <p>With {packageItem.contributors.map((value) => value.displayName).join(", ")}</p> : null}
        {signals.length ? <ul className="board-card__signals">{signals.map((value) => <li key={value}>{value}</li>)}</ul> : null}
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

function BoardTable({ ariaLabel, items, onInspect, totalCount }: { ariaLabel: string; items: BoardItem[]; onInspect: (item: BoardItem) => void; totalCount: number }) {
  return <div className="team-table-wrap"><table className="team-table"><caption>{ariaLabel}, showing {items.length} of {totalCount}</caption><thead><tr><th>Reference</th><th>Title</th><th>Type</th><th>Status</th><th>Owner</th><th>Due</th><th>Age</th></tr></thead><tbody>{items.map((item) => <tr key={`${item.itemType}-${item.id}`}><th>{item.reference}</th><td><button className="table-link" onClick={() => onInspect(item)} type="button">{item.title}</button></td><td>{boardLabel(item.itemType)}</td><td>{boardLabel(item.column)}</td><td>{item.ownerDisplayName ?? "Unassigned"}</td><td>{item.dueOn}</td><td>{daysInState(item.changedAt)}</td></tr>)}</tbody></table></div>;
}
