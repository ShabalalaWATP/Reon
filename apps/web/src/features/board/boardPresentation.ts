import type { BoardColumn, BoardFilters } from "../../lib/api/boardTypes";
import { addLocalDays, localDateInputValue } from "../../lib/dateInputs";

export const activeBoardColumns: BoardColumn[] = [
  "AWAITING_ASSIGNMENT",
  "BACKLOG",
  "READY",
  "IN_PROGRESS",
  "BLOCKED",
  "MANAGER_REVIEW",
];

export const exceptionBoardColumns: BoardColumn[] = [
  "QUALITY_REVIEW",
  "REWORK",
  "ON_HOLD",
];

export const archiveBoardColumns: BoardColumn[] = ["COMPLETED", "CANCELLED"];

export const serviceRequestBoardColumns: BoardColumn[] = [
  "AWAITING_ASSIGNMENT",
  "IN_PROGRESS",
  "BLOCKED",
  "MANAGER_REVIEW",
];

export const serviceRequestExceptionColumns: BoardColumn[] = [
  "QUALITY_REVIEW",
  "REWORK",
  "ON_HOLD",
];

export const workPackageBoardColumns: BoardColumn[] = [
  "BACKLOG",
  "READY",
  "IN_PROGRESS",
  "BLOCKED",
];

export const serviceRequestColumnMeanings: Partial<Record<BoardColumn, string>> = {
  AWAITING_ASSIGNMENT: "A Manager needs to assign the Analyst team",
  IN_PROGRESS: "Assigned Analysts are producing the response",
  BLOCKED: "The team is waiting for the Customer to answer a question",
  MANAGER_REVIEW: "The response is with the Team Manager for review",
  QUALITY_REVIEW: "The response is with QC for review and dissemination",
  REWORK: "A Manager or QC has requested changes from the Analysts",
  ON_HOLD: "The request is paused with a recorded reason",
  COMPLETED: "QC has disseminated the response to the Customer",
  CANCELLED: "The request has been withdrawn or cancelled",
};

export const allBoardColumns = [
  ...activeBoardColumns,
  ...exceptionBoardColumns,
  ...archiveBoardColumns,
];

const emptyBoardFilters: BoardFilters = {
  search: "",
  columns: [],
  priorities: [],
  ownerUserId: null,
  itemTypes: [],
  dueBefore: null,
};

export function boardLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/(^| )\w/g, (letter) => letter.toUpperCase());
}

export function stateAgeDays(changedAt: string, now = new Date()) {
  const changed = new Date(changedAt);
  const elapsed = Math.max(0, now.getTime() - changed.getTime());
  return Math.floor(elapsed / 86_400_000);
}

export function daysInState(changedAt: string, now = new Date()) {
  const days = stateAgeDays(changedAt, now);
  return days === 0 ? "Changed today" : `${days} day${days === 1 ? "" : "s"} in state`;
}

export function dueSignal(dueOn: string, now = new Date()) {
  const today = localDateInputValue(now);
  const soon = localDateInputValue(addLocalDays(now, 7));
  if (dueOn < today) return { label: "Overdue", tone: "danger" as const };
  if (dueOn === today) return { label: "Due today", tone: "warning" as const };
  if (dueOn <= soon) return { label: "Due soon", tone: "warning" as const };
  return { label: "Scheduled", tone: "neutral" as const };
}

export function builtInBoardViews(userId: string, now = new Date()) {
  return [
    {
      key: "needs-assignment",
      name: "Needs assignment",
      filters: { ...emptyBoardFilters, columns: ["AWAITING_ASSIGNMENT"] as BoardColumn[] },
    },
    {
      key: "overdue",
      name: "Overdue",
      filters: { ...emptyBoardFilters, dueBefore: localDateInputValue(addLocalDays(now, -1)) },
    },
    {
      key: "due-week",
      name: "Due this week",
      filters: { ...emptyBoardFilters, dueBefore: localDateInputValue(addLocalDays(now, 7)) },
    },
    {
      key: "blocked",
      name: "Blocked",
      filters: { ...emptyBoardFilters, columns: ["BLOCKED"] as BoardColumn[] },
    },
    {
      key: "manager-review",
      name: "Manager review",
      filters: { ...emptyBoardFilters, columns: ["MANAGER_REVIEW"] as BoardColumn[] },
    },
    {
      key: "my-work",
      name: "My work",
      filters: { ...emptyBoardFilters, ownerUserId: userId },
    },
  ];
}

export function boardPresetFilters(preset: string | null, userId: string) {
  return builtInBoardViews(userId).find((view) => view.key === preset)?.filters
    ?? emptyBoardFilters;
}

export function filtersActive(filters: BoardFilters) {
  return Boolean(
    filters.search || filters.columns.length || filters.priorities.length
      || filters.ownerUserId || filters.itemTypes.length || filters.dueBefore,
  );
}
