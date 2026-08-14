import { useState } from "react";

import type { BoardColumn, BoardItem } from "../../lib/api/boardTypes";
import {
  activeBoardColumns,
  archiveBoardColumns,
  exceptionBoardColumns,
} from "./boardPresentation";
import { type BoardCardContext as Context, type BoardMenuMove as MenuMove } from "./BoardCard";
import { BoardColumns, type BoardDragState as DragState } from "./BoardColumns";
import { BoardTable, PackageMoveDialog, SecondaryBoardLanes } from "./BoardSurfaceParts";

type BoardSurfaceProps = {
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
};

export function BoardSurface(props: BoardSurfaceProps) {
  if (props.mode === "table") {
    return (
      <BoardTable
        ariaLabel={props.ariaLabel ?? "Team Kanban board"}
        items={props.items}
        onInspect={props.onInspect}
        totalCount={props.totalCount}
      />
    );
  }
  return <BoardKanban {...props} />;
}

function BoardKanban(props: BoardSurfaceProps) {
  const {
    activeColumns,
    archiveColumns,
    ariaLabel,
    columnCounts,
    columnDescriptions,
    columnFilterActive,
    context,
    exceptionColumns,
    filteredColumns,
    items,
    moving,
    onInspect,
    onMove,
    onShowArchive,
    onShowExceptions,
    resultNote,
    showArchive,
    showExceptions,
    totalCount,
    wipLimits,
  } = boardSurfaceDefaults(props);
  const [dragging, setDragging] = useState<BoardItem | null>(null);
  const [pending, setPending] = useState<{ item: BoardItem; target: BoardColumn } | null>(null);
  const customSelection = columnFilterActive || filteredColumns.length > 0;
  const selected = customSelection ? filteredColumns : activeColumns;
  const drag: DragState = {
    dragging,
    onDragStart: (item) => setDragging(item),
    onDragEnd: () => setDragging(null),
    onDropColumn: (column) => {
      if (
        dragging &&
        onMove &&
        dragging.column !== column &&
        dragging.availableColumns.includes(column)
      ) {
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
      <SecondaryBoardLanes
        archiveColumns={archiveColumns}
        ariaLabel={ariaLabel}
        columnCounts={columnCounts}
        columnDescriptions={columnDescriptions}
        context={context}
        customSelection={customSelection}
        drag={drag}
        exceptionColumns={exceptionColumns}
        items={items}
        onInspect={onInspect}
        onMenuMove={menuMove}
        onShowArchive={onShowArchive}
        onShowExceptions={onShowExceptions}
        showArchive={showArchive}
        showExceptions={showExceptions}
        wipLimits={wipLimits}
      />
      <p className="board-result-note">
        Showing {items.length} of {totalCount} matching work items. Column totals cover the complete
        filtered result. {resultNote}
      </p>
      {pending ? (
        <PackageMoveDialog
          item={pending.item}
          moving={moving}
          onCancel={() => setPending(null)}
          onConfirm={async (reason) => {
            await onMove?.(pending.item, pending.target, reason);
            setPending(null);
          }}
          target={pending.target}
        />
      ) : null}
    </div>
  );
}

function boardSurfaceDefaults(props: BoardSurfaceProps) {
  return {
    ...props,
    activeColumns: props.activeColumns ?? activeBoardColumns,
    archiveColumns: props.archiveColumns ?? archiveBoardColumns,
    ariaLabel: props.ariaLabel ?? "Team Kanban board",
    columnCounts: props.columnCounts ?? {},
    columnDescriptions: props.columnDescriptions ?? {},
    columnFilterActive: props.columnFilterActive ?? false,
    exceptionColumns: props.exceptionColumns ?? exceptionBoardColumns,
    moving: props.moving ?? false,
    resultNote:
      props.resultNote ??
      "Drag a work-package card to move it; service requests change stage through their named workflow action.",
  };
}
