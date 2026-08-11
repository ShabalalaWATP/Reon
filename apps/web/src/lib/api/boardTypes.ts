export type BoardColumn =
  | "AWAITING_ASSIGNMENT" | "BACKLOG" | "READY" | "IN_PROGRESS"
  | "BLOCKED" | "MANAGER_REVIEW" | "QUALITY_REVIEW" | "REWORK"
  | "ON_HOLD" | "COMPLETED" | "CANCELLED";
export type BoardItemType = "SERVICE_REQUEST" | "WORK_PACKAGE";
export type WorkPackageStatus = "BACKLOG" | "READY" | "IN_PROGRESS" | "BLOCKED" | "DONE" | "CANCELLED";
export type WorkPackagePriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

export interface BoardFilters {
  search: string;
  columns: BoardColumn[];
  priorities: string[];
  ownerUserId: string | null;
  itemTypes: BoardItemType[];
  dueBefore: string | null;
}

export interface BoardItem {
  id: string;
  itemType: BoardItemType;
  reference: string;
  title: string;
  column: BoardColumn;
  priority: string;
  dueOn: string;
  ownerUserId: string | null;
  ownerDisplayName: string | null;
  version: number;
  linkedRequestId: string | null;
  availableColumns: BoardColumn[];
  changedAt: string;
}

export interface SavedBoardView {
  id: string;
  name: string;
  filters: BoardFilters;
  version: number;
}

export interface BoardResult {
  items: BoardItem[];
  nextCursor: string | null;
  columnCounts: Record<BoardColumn, number>;
  totalCount: number;
  wipLimits: Record<string, number>;
  configurationVersion: number;
  savedViews: SavedBoardView[];
  generatedAt: string;
}

export interface WorkPackageInput {
  grantId: string | null;
  title: string;
  description: string;
  ownerUserId: string;
  contributorIds: string[];
  estimatePoints: number;
  remainingEffortMinutes: number;
  dueOn: string;
  priority: WorkPackagePriority;
  blockers: string;
  acceptanceCriteria: string;
  linkedRequestId: string | null;
  dependencyIds: string[];
  iterationId: string | null;
}

export interface WorkPackageActivity {
  id: string;
  type: string;
  summary: string;
  actorDisplayName: string;
  createdAt: string;
}

export interface CapacityReservation {
  id: string;
  userId: string;
  userDisplayName: string;
  startsAt: string;
  endsAt: string;
  minutes: number;
  status: "ACTIVE" | "CANCELLED";
  reason: string;
  version: number;
}

export interface WorkPackage {
  id: string;
  teamId: string;
  linkedRequestId: string | null;
  iterationId: string | null;
  title: string;
  description: string;
  ownerUserId: string;
  ownerDisplayName: string;
  contributors: Array<{ userId: string; displayName: string }>;
  estimatePoints: number;
  remainingEffortMinutes: number;
  dueOn: string;
  priority: WorkPackagePriority;
  status: WorkPackageStatus;
  blockers: string;
  acceptanceCriteria: string;
  dependencyIds: string[];
  version: number;
  activities: WorkPackageActivity[];
  reservations: CapacityReservation[];
}

export interface Iteration {
  id: string;
  name: string;
  goal: string;
  startsOn: string;
  endsOn: string;
  status: "PLANNED" | "ACTIVE" | "CLOSED";
  completionSummary: string | null;
  version: number;
}

export type BoardMoveInput = {
  grantId: string | null;
  itemType: BoardItemType;
  itemId: string;
  target: BoardColumn;
  expectedVersion: number;
  reason: string;
};

export type ReservationInput = {
  grantId: string | null;
  userId: string;
  startsAt: string;
  endsAt: string;
  reason: string;
};

export type TaskHastenerInput = {
  audience: "ONE_ASSIGNED" | "ALL_ASSIGNED";
  recipientUserId?: string;
  message: string;
};

export type TaskHastenerResult = {
  eventId: string;
  requestId: string;
  message: string;
  senderDisplayName: string;
  recipients: Array<{
    userId: string;
    displayName: string;
    assignmentRole: "LEAD" | "CONTRIBUTOR";
  }>;
  createdAt: string;
};
