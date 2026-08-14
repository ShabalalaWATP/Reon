import { useState } from "react";

import type { BoardColumn, BoardItem, Iteration, WorkPackage } from "../../lib/api/boardTypes";
import { formatDate } from "../../lib/status";
import {
  archiveBoardColumns,
  boardLabel,
  daysInState,
  dueSignal,
  stateAgeDays,
} from "./boardPresentation";

const STALE_AFTER_DAYS = 5;

export type BoardCardContext = {
  packages?: WorkPackage[];
  iterations?: Iteration[];
};

export type BoardCardDrag = {
  dragging: BoardItem | null;
  onDragStart: (item: BoardItem) => void;
  onDragEnd: () => void;
};

export type BoardMenuMove = (item: BoardItem, target: BoardColumn) => void;

export function BoardCard({
  context,
  drag,
  item,
  onInspect,
  onMenuMove,
}: {
  context: BoardCardContext;
  drag: BoardCardDrag;
  item: BoardItem;
  onInspect: (item: BoardItem) => void;
  onMenuMove?: BoardMenuMove;
}) {
  const details = boardCardDetails(context, item, Boolean(onMenuMove));
  const dragging = isDraggedItem(drag.dragging, item);
  return (
    <article
      className={boardCardClasses(details, dragging)}
      {...boardCardDragProps(details.draggable, drag, item)}
    >
      <BoardCardControls details={details} item={item} onMenuMove={onMenuMove} />
      <BoardCardBody details={details} item={item} onInspect={onInspect} />
    </article>
  );
}

function BoardCardControls({
  details,
  item,
  onMenuMove,
}: {
  details: ReturnType<typeof boardCardDetails>;
  item: BoardItem;
  onMenuMove?: BoardMenuMove;
}) {
  return (
    <>
      {details.draggable ? (
        <span aria-hidden="true" className="board-card__grip">
          ⠿
        </span>
      ) : null}
      {details.movable && onMenuMove ? <BoardCardMoveMenu item={item} onMove={onMenuMove} /> : null}
    </>
  );
}

function BoardCardBody({
  details,
  item,
  onInspect,
}: {
  details: ReturnType<typeof boardCardDetails>;
  item: BoardItem;
  onInspect: (item: BoardItem) => void;
}) {
  return (
    <button className="board-card__open" onClick={() => onInspect(item)} type="button">
      <span>
        {item.itemType === "SERVICE_REQUEST" ? "Service request" : "Work package"} ·{" "}
        {item.reference}
      </span>
      <h4>{item.title}</h4>
      <div className="board-card__meta">
        <strong
          className={`board-card__priority board-card__priority--${item.priority.toLowerCase()}`}
        >
          {boardLabel(item.priority)}
        </strong>
        <span>{details.signal.label}</span>
      </div>
      <dl>
        <div>
          <dt>Owner</dt>
          <dd>{item.ownerDisplayName ?? "Unassigned"}</dd>
        </div>
        <div>
          <dt>Due</dt>
          <dd>{formatDate(item.dueOn)}</dd>
        </div>
      </dl>
      <small
        className={details.stale ? "board-card__age board-card__age--stale" : "board-card__age"}
      >
        {daysInState(item.changedAt)}
      </small>
      <BoardCardPackageDetails details={details} />
    </button>
  );
}

function BoardCardPackageDetails({ details }: { details: ReturnType<typeof boardCardDetails> }) {
  return (
    <>
      {details.packageItem?.contributors.length ? (
        <p>With {details.packageItem.contributors.map((value) => value.displayName).join(", ")}</p>
      ) : null}
      {details.signals.length ? (
        <ul className="board-card__signals">
          {details.signals.map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

function BoardCardMoveMenu({ item, onMove }: { item: BoardItem; onMove: BoardMenuMove }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="board-card__menu"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") setOpen(false);
      }}
    >
      <button
        aria-expanded={open}
        aria-label={`Move ${item.title}`}
        className="board-card__menu-toggle"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        ⋯
      </button>
      {open ? (
        <div aria-label={`Move ${item.title} to`} className="board-card__menu-list">
          {item.availableColumns.map((column) => (
            <button
              key={column}
              onClick={() => {
                setOpen(false);
                onMove(item, column);
              }}
              type="button"
            >
              Move to {boardLabel(column)}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function boardCardDetails(context: BoardCardContext, item: BoardItem, hasMoveMenu: boolean) {
  const packageDetails = workPackageDetails(context, item);
  const draggable = item.itemType === "WORK_PACKAGE" && item.availableColumns.length > 0;
  return {
    draggable,
    movable: draggable && hasMoveMenu,
    packageItem: packageDetails.packageItem,
    signal: dueSignal(item.dueOn),
    signals: boardCardSignals(item, packageDetails),
    stale:
      stateAgeDays(item.changedAt) >= STALE_AFTER_DAYS &&
      !archiveBoardColumns.includes(item.column),
  };
}

function workPackageDetails(context: BoardCardContext, item: BoardItem) {
  const packageItem = context.packages?.find((value) => value.id === item.id);
  if (!packageItem) return { iterationName: null, packageItem, reserved: 0 };
  const iterationName = packageItem.iterationId
    ? (context.iterations?.find((value) => value.id === packageItem.iterationId)?.name ?? null)
    : null;
  const reserved = packageItem.reservations
    .filter((value) => value.status === "ACTIVE")
    .reduce((total, value) => total + value.minutes, 0);
  return { iterationName, packageItem, reserved };
}

function boardCardSignals(item: BoardItem, details: ReturnType<typeof workPackageDetails>) {
  return [
    item.itemType === "SERVICE_REQUEST" && item.column === "BLOCKED"
      ? "Waiting for customer"
      : null,
    item.ownerUserId ? null : "Unassigned",
    details.reserved ? `${Math.round((details.reserved / 60) * 10) / 10}h reserved` : null,
    details.iterationName,
  ].filter((value): value is string => Boolean(value));
}

function boardCardClasses(details: ReturnType<typeof boardCardDetails>, dragging: boolean) {
  return [
    `board-card board-card--${details.signal.tone}`,
    details.draggable ? "board-card--draggable" : "",
    details.movable ? "board-card--actions" : "",
    dragging ? "board-card--dragging" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function boardCardDragProps(draggable: boolean, drag: BoardCardDrag, item: BoardItem) {
  if (!draggable) return { draggable: false };
  return {
    draggable: true,
    onDragEnd: drag.onDragEnd,
    onDragStart: (event: React.DragEvent) => {
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
      drag.onDragStart(item);
    },
  };
}

function isDraggedItem(dragging: BoardItem | null, item: BoardItem) {
  return dragging?.id === item.id && dragging.itemType === item.itemType;
}
