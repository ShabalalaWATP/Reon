import { useState } from "react";

import type { BoardColumn, BoardItem } from "../../lib/api/boardTypes";
import { type BoardCardContext, type BoardMenuMove } from "./BoardCard";
import { BoardColumns, type BoardDragState } from "./BoardColumns";
import { boardLabel, daysInState } from "./boardPresentation";

export function SecondaryBoardLanes({
  archiveColumns,
  ariaLabel,
  columnCounts,
  columnDescriptions,
  context,
  customSelection,
  drag,
  exceptionColumns,
  items,
  onInspect,
  onMenuMove,
  onShowArchive,
  onShowExceptions,
  showArchive,
  showExceptions,
  wipLimits,
}: {
  archiveColumns: BoardColumn[];
  ariaLabel: string;
  columnCounts: Partial<Record<BoardColumn, number>>;
  columnDescriptions: Partial<Record<BoardColumn, string>>;
  context: BoardCardContext;
  customSelection: boolean;
  drag: BoardDragState;
  exceptionColumns: BoardColumn[];
  items: BoardItem[];
  onInspect: (item: BoardItem) => void;
  onMenuMove?: BoardMenuMove;
  onShowArchive: () => void;
  onShowExceptions: () => void;
  showArchive: boolean;
  showExceptions: boolean;
  wipLimits: Record<string, number>;
}) {
  if (customSelection) return null;
  return (
    <>
      <div className="board-secondary-groups">
        {exceptionColumns.length ? (
          <BoardGroupToggle
            columns={exceptionColumns}
            columnCounts={columnCounts}
            label="Exceptions and downstream"
            onClick={onShowExceptions}
            open={showExceptions}
          />
        ) : null}
        {archiveColumns.length ? (
          <BoardGroupToggle
            columns={archiveColumns}
            columnCounts={columnCounts}
            label="Completed and cancelled"
            onClick={onShowArchive}
            open={showArchive}
          />
        ) : null}
      </div>
      {showExceptions && exceptionColumns.length ? (
        <BoardColumns
          ariaLabel={`${ariaLabel}, exceptions`}
          columnCounts={columnCounts}
          columnDescriptions={columnDescriptions}
          columns={exceptionColumns}
          context={context}
          drag={drag}
          items={items}
          onInspect={onInspect}
          onMenuMove={onMenuMove}
          wipLimits={wipLimits}
        />
      ) : null}
      {showArchive && archiveColumns.length ? (
        <BoardColumns
          ariaLabel={`${ariaLabel}, archive`}
          columnCounts={columnCounts}
          columnDescriptions={columnDescriptions}
          columns={archiveColumns}
          context={context}
          drag={drag}
          items={items}
          onInspect={onInspect}
          onMenuMove={onMenuMove}
          wipLimits={wipLimits}
        />
      ) : null}
    </>
  );
}

export function PackageMoveDialog({
  item,
  moving,
  onCancel,
  onConfirm,
  target,
}: {
  item: BoardItem;
  moving: boolean;
  onCancel: () => void;
  onConfirm: (reason: string) => Promise<void>;
  target: BoardColumn;
}) {
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
        <p>
          Move to <strong>{boardLabel(target)}</strong>. Every package move is recorded with your
          reason.
        </p>
        <label className="form-field">
          Reason<span className="field-hint">Required, at least 10 characters</span>
          <textarea
            autoFocus
            maxLength={500}
            minLength={10}
            onChange={(event) => setReason(event.target.value)}
            required
            rows={3}
            value={reason}
          />
        </label>
        {failed ? (
          <p className="form-banner form-banner--error" role="alert">
            The move could not be saved. Your reason is kept; try again.
          </p>
        ) : null}
        <div className="board-move-dialog__actions">
          <button className="button button--quiet" onClick={onCancel} type="button">
            Cancel
          </button>
          <button
            className="button button--primary"
            disabled={moving || reason.trim().length < 10}
            type="submit"
          >
            {moving ? "Moving…" : `Move to ${boardLabel(target)}`}
          </button>
        </div>
      </form>
    </div>
  );
}

function BoardGroupToggle({
  columns,
  columnCounts,
  label,
  onClick,
  open,
}: {
  columns: BoardColumn[];
  columnCounts: Partial<Record<BoardColumn, number>>;
  label: string;
  onClick: () => void;
  open: boolean;
}) {
  const count = columns.reduce((total, column) => total + (columnCounts[column] ?? 0), 0);
  return (
    <button aria-expanded={open} onClick={onClick} type="button">
      <span>{label}</span>
      <strong>{count}</strong>
      <small>{open ? "Collapse" : "Show lanes"}</small>
    </button>
  );
}

export function BoardTable({
  ariaLabel,
  items,
  onInspect,
  totalCount,
}: {
  ariaLabel: string;
  items: BoardItem[];
  onInspect: (item: BoardItem) => void;
  totalCount: number;
}) {
  return (
    <div className="team-table-wrap">
      <table className="team-table">
        <caption>
          {ariaLabel}, showing {items.length} of {totalCount}
        </caption>
        <thead>
          <tr>
            <th>Reference</th>
            <th>Title</th>
            <th>Type</th>
            <th>Status</th>
            <th>Owner</th>
            <th>Due</th>
            <th>Age</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={`${item.itemType}-${item.id}`}>
              <th>{item.reference}</th>
              <td>
                <button className="table-link" onClick={() => onInspect(item)} type="button">
                  {item.title}
                </button>
              </td>
              <td>{boardLabel(item.itemType)}</td>
              <td>{boardLabel(item.column)}</td>
              <td>{item.ownerDisplayName ?? "Unassigned"}</td>
              <td>{item.dueOn}</td>
              <td>{daysInState(item.changedAt)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
