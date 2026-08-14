import type { BoardFilters, BoardItem, WorkPackage } from "../../lib/api/boardTypes";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";

export const emptyBoardFilters: BoardFilters = {
  search: "",
  columns: [],
  priorities: [],
  ownerUserId: null,
  itemTypes: [],
  dueBefore: null,
};

export const access: TeamWorkspaceAccess = {
  teamId: "team-one",
  teamCode: "TEAM_ONE",
  teamName: "Team One",
  unitKind: "TEAM",
  workspacePosition: "MEMBER",
  grantId: null,
  permissions: [],
};

export const requestItem: BoardItem = {
  id: "request-blocked",
  itemType: "SERVICE_REQUEST",
  reference: "REQ-101",
  title: "Blocked customer request",
  column: "BLOCKED",
  priority: "URGENT",
  dueOn: "2020-01-01",
  ownerUserId: null,
  ownerDisplayName: null,
  version: 1,
  linkedRequestId: "request-blocked",
  availableColumns: [],
  changedAt: "2999-01-01T00:00:00Z",
};

export const packageItem: BoardItem = {
  ...requestItem,
  id: "package-rich",
  itemType: "WORK_PACKAGE",
  reference: "WP-101",
  title: "Rich work package",
  column: "READY",
  dueOn: new Date().toISOString().slice(0, 10),
  ownerUserId: "analyst-one",
  ownerDisplayName: "Analyst One",
  linkedRequestId: null,
  availableColumns: ["IN_PROGRESS", "BLOCKED"],
  changedAt: new Date(Date.now() - 86_400_000).toISOString(),
};

export const richPackage: WorkPackage = {
  id: packageItem.id,
  teamId: "team-one",
  linkedRequestId: "request-one",
  iterationId: "iteration-one",
  title: packageItem.title,
  description: "A complete synthetic package description.",
  ownerUserId: "analyst-one",
  ownerDisplayName: "Analyst One",
  contributors: [{ userId: "analyst-two", displayName: "Analyst Two" }],
  estimatePoints: 5,
  remainingEffortMinutes: 120,
  dueOn: packageItem.dueOn,
  priority: "HIGH",
  status: "READY",
  blockers: "A synthetic dependency.",
  acceptanceCriteria: "All synthetic checks pass.",
  dependencyIds: ["dependency-known", "dependency-missing"],
  version: 1,
  activities: [
    {
      id: "activity-one",
      type: "CREATED",
      summary: "Package created",
      actorDisplayName: "Manager One",
      createdAt: "2026-08-01T09:00:00Z",
    },
  ],
  reservations: [
    {
      id: "reservation-one",
      userId: "analyst-one",
      userDisplayName: "Analyst One",
      startsAt: "2026-08-11T09:00:00Z",
      endsAt: "2026-08-11T11:00:00Z",
      minutes: 90,
      status: "ACTIVE",
      reason: "Synthetic delivery",
      version: 1,
    },
    {
      id: "reservation-old",
      userId: "analyst-one",
      userDisplayName: "Analyst One",
      startsAt: "2026-08-01T09:00:00Z",
      endsAt: "2026-08-01T10:00:00Z",
      minutes: 60,
      status: "CANCELLED",
      reason: "Superseded",
      version: 2,
    },
  ],
};

export const dependencyPackage: WorkPackage = {
  ...richPackage,
  id: "dependency-known",
  title: "Known dependency",
  dependencyIds: [],
  activities: [],
  reservations: [],
};
