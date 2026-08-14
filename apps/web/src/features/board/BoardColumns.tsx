import { useState } from "react";

import type { BoardColumn, BoardItem } from "../../lib/api/boardTypes";
import { BoardCard, type BoardCardContext, type BoardMenuMove } from "./BoardCard";
import { boardLabel } from "./boardPresentation";

export type BoardDragState = {
  dragging: BoardItem | null;
  onDragStart: (item: BoardItem) => void;
  onDragEnd: () => void;
  onDropColumn: (column: BoardColumn) => void;
};

export function BoardColumns({
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
  context: BoardCardContext;
  drag: BoardDragState;
  items: BoardItem[];
  onInspect: (item: BoardItem) => void;
  onMenuMove?: BoardMenuMove;
  wipLimits: Record<string, number>;
}) {
  const [over, setOver] = useState<BoardColumn | null>(null);
  const droppable = (column: BoardColumn) =>
    Boolean(
      drag.dragging &&
      drag.dragging.column !== column &&
      drag.dragging.availableColumns.includes(column),
    );
  return (
    <section aria-label={ariaLabel} className="kanban">
      {columns.map((column) => (
        <BoardColumnLane
          canDrop={droppable(column)}
          column={column}
          columnCount={columnCounts[column] ?? 0}
          context={context}
          description={columnDescriptions[column]}
          drag={drag}
          items={items}
          key={column}
          limit={wipLimits[column]}
          onInspect={onInspect}
          onMenuMove={onMenuMove}
          onOverChange={setOver}
          over={over === column}
        />
      ))}
    </section>
  );
}

function BoardColumnLane({
  canDrop,
  column,
  columnCount,
  context,
  description,
  drag,
  items,
  limit,
  onInspect,
  onMenuMove,
  onOverChange,
  over,
}: {
  canDrop: boolean;
  column: BoardColumn;
  columnCount: number;
  context: BoardCardContext;
  description?: string;
  drag: BoardDragState;
  items: BoardItem[];
  limit?: number;
  onInspect: (item: BoardItem) => void;
  onMenuMove?: BoardMenuMove;
  onOverChange: (column: BoardColumn | null) => void;
  over: boolean;
}) {
  const lane = boardColumnLaneModel({ canDrop, column, columnCount, drag, items, limit, over });
  return (
    <section
      className={lane.classes}
      {...boardColumnDragProps(canDrop, column, drag, onOverChange)}
    >
      <BoardColumnHeader
        column={column}
        columnCount={columnCount}
        description={description}
        lane={lane}
        limit={limit}
      />
      <BoardColumnCards
        canDrop={canDrop}
        cards={lane.cards}
        context={context}
        drag={drag}
        onInspect={onInspect}
        onMenuMove={onMenuMove}
      />
    </section>
  );
}

function BoardColumnHeader({
  column,
  columnCount,
  description,
  lane,
  limit,
}: {
  column: BoardColumn;
  columnCount: number;
  description?: string;
  lane: ReturnType<typeof boardColumnLaneModel>;
  limit?: number;
}) {
  return (
    <>
      <header>
        <div>
          <h3>{boardLabel(column)}</h3>
          {description ? <p className="kanban-column__meaning">({description})</p> : null}
          {limit ? <small>Limit {limit}</small> : null}
        </div>
        <span aria-label={`${columnCount} total`}>{columnCount}</span>
      </header>
      {limit ? (
        <span aria-hidden="true" className="kanban-column__meter">
          <i style={{ width: `${lane.limitPercentage}%` }} />
        </span>
      ) : null}
      {lane.breached && limit ? (
        <p className="kanban-warning" role="status">
          WIP limit exceeded by {columnCount - limit}
        </p>
      ) : null}
    </>
  );
}

function BoardColumnCards({
  canDrop,
  cards,
  context,
  drag,
  onInspect,
  onMenuMove,
}: {
  canDrop: boolean;
  cards: BoardItem[];
  context: BoardCardContext;
  drag: BoardDragState;
  onInspect: (item: BoardItem) => void;
  onMenuMove?: BoardMenuMove;
}) {
  return (
    <>
      {cards.map((item) => (
        <BoardCard
          context={context}
          drag={drag}
          item={item}
          key={`${item.itemType}-${item.id}`}
          onInspect={onInspect}
          onMenuMove={onMenuMove}
        />
      ))}
      {cards.length === 0 ? (
        <p className="kanban-empty">{canDrop ? "Drop here to move" : "No items on this page."}</p>
      ) : null}
      {canDrop && cards.length > 0 ? <p className="kanban-dropzone">Drop here to move</p> : null}
    </>
  );
}

function boardColumnLaneModel({
  canDrop,
  column,
  columnCount,
  drag,
  items,
  limit,
  over,
}: {
  canDrop: boolean;
  column: BoardColumn;
  columnCount: number;
  drag: BoardDragState;
  items: BoardItem[];
  limit?: number;
  over: boolean;
}) {
  const breached = Boolean(limit && columnCount > limit);
  return {
    breached,
    cards: items.filter((item) => item.column === column),
    classes: boardColumnClasses({
      breached,
      canDrop,
      dimmed: Boolean(drag.dragging && !canDrop && drag.dragging.column !== column),
      over: over && canDrop,
    }),
    limitPercentage: limit ? Math.min(100, Math.round((columnCount / limit) * 100)) : 0,
  };
}

function boardColumnDragProps(
  canDrop: boolean,
  column: BoardColumn,
  drag: BoardDragState,
  onOverChange: (column: BoardColumn | null) => void,
) {
  return {
    onDragLeave: (event: React.DragEvent<HTMLElement>) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) onOverChange(null);
    },
    onDragOver: (event: React.DragEvent<HTMLElement>) => {
      if (!canDrop) return;
      event.preventDefault();
      onOverChange(column);
    },
    onDrop: (event: React.DragEvent<HTMLElement>) => {
      if (canDrop) {
        event.preventDefault();
        drag.onDropColumn(column);
      }
      onOverChange(null);
    },
  };
}

function boardColumnClasses({
  breached,
  canDrop,
  dimmed,
  over,
}: {
  breached: boolean;
  canDrop: boolean;
  dimmed: boolean;
  over: boolean;
}) {
  return [
    "kanban-column",
    breached ? "kanban-column--breached" : "",
    canDrop ? "kanban-column--droppable" : "",
    over ? "kanban-column--over" : "",
    dimmed ? "kanban-column--dimmed" : "",
  ]
    .filter(Boolean)
    .join(" ");
}
