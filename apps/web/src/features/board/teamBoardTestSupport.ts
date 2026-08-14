import type { BoardItem, BoardResult, WorkPackage } from "../../lib/api/boardTypes";
import type { RequestDetail, Session } from "../../lib/api/types";
import type { TeamMember, TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import { requestDetail, requesterSession } from "../../test/fixtures";
import { json, mockFetch } from "../../test/render";

export const managerSession: Session = {
  ...requesterSession,
  user: {
    ...requesterSession.user,
    id: "manager-ssg",
    username: "admin8",
    displayName: "Grant Hanley",
    role: "DELIVERY_TEAM_LEAD",
    scope: "SSG Team",
  },
};
export const analystSession: Session = {
  ...managerSession,
  user: {
    ...managerSession.user,
    id: "analyst-ssg",
    username: "admin11",
    displayName: "Lewis Ferguson",
    role: "DELIVERY_SPECIALIST",
  },
};
export const managerAccess: TeamWorkspaceAccess = {
  teamId: "team-ssg",
  teamCode: "SSG_TEAM",
  teamName: "SSG Team",
  unitKind: "TEAM",
  workspacePosition: "MANAGER",
  grantId: "grant-ssg",
  permissions: ["BOARD", "CALENDAR", "CAPACITY", "ROSTER", "STATISTICS"],
};
export const analystAccess: TeamWorkspaceAccess = {
  ...managerAccess,
  workspacePosition: "MEMBER",
  grantId: null,
  permissions: [],
};
export const people: TeamMember[] = [
  {
    membershipId: "manager-membership",
    accountId: "manager-ssg",
    displayName: "Grant Hanley",
    role: "DELIVERY_TEAM_LEAD",
    state: "CURRENT",
    effectiveFrom: "2026-01-01T09:00:00Z",
    effectiveUntil: null,
    version: 1,
    activeWorkCount: 0,
    skills: ["Delivery leadership"],
    startReason: null,
    endReason: null,
  },
  {
    membershipId: "analyst-membership",
    accountId: "analyst-ssg",
    displayName: "Lewis Ferguson",
    role: "DELIVERY_SPECIALIST",
    state: "CURRENT",
    effectiveFrom: "2026-01-01T09:00:00Z",
    effectiveUntil: null,
    version: 1,
    activeWorkCount: 1,
    skills: ["Research"],
    startReason: null,
    endReason: null,
  },
  {
    membershipId: "ended-membership",
    accountId: "former",
    displayName: "Former Analyst",
    role: "DELIVERY_SPECIALIST",
    state: "ENDED",
    effectiveFrom: "2025-01-01T09:00:00Z",
    effectiveUntil: "2026-01-01T09:00:00Z",
    version: 2,
    activeWorkCount: 0,
    skills: [],
    startReason: null,
    endReason: null,
  },
];
export const packageItem: WorkPackage = {
  id: "package-one",
  teamId: "team-ssg",
  linkedRequestId: null,
  iterationId: "iteration-active",
  title: "Prepare synthetic product",
  description: "Complete fictional planning detail.",
  ownerUserId: "analyst-ssg",
  ownerDisplayName: "Lewis Ferguson",
  contributors: [{ userId: "analyst-ssg", displayName: "Lewis Ferguson" }],
  estimatePoints: 5,
  remainingEffortMinutes: 120,
  dueOn: "2026-08-21",
  priority: "HIGH",
  status: "READY",
  blockers: "No known blockers.",
  acceptanceCriteria: "The fictional output is complete.",
  dependencyIds: [],
  version: 2,
  activities: [
    {
      id: "activity-one",
      type: "CREATED",
      summary: "Work package created.",
      actorDisplayName: "Grant Hanley",
      createdAt: "2026-08-07T10:00:00Z",
    },
  ],
  reservations: [],
};
export const iterations = [
  {
    id: "iteration-active",
    name: "Pilot iteration",
    goal: "Deliver the complete product.",
    startsOn: "2026-08-01",
    endsOn: "2026-08-14",
    status: "ACTIVE" as const,
    completionSummary: null,
    version: 1,
  },
  {
    id: "iteration-closed",
    name: "Closed iteration",
    goal: "Retain the delivery history.",
    startsOn: "2026-07-01",
    endsOn: "2026-07-14",
    status: "CLOSED" as const,
    completionSummary: "Complete.",
    version: 2,
  },
];
export const board: BoardResult = {
  items: [
    {
      id: "request-one",
      itemType: "SERVICE_REQUEST",
      reference: "SR-000001",
      title: "Customer request projection",
      column: "IN_PROGRESS",
      priority: "HIGH",
      dueOn: "2026-08-20",
      ownerUserId: null,
      ownerDisplayName: null,
      version: 3,
      linkedRequestId: "request-one",
      availableColumns: [],
      changedAt: "2026-08-07T10:00:00Z",
    },
    {
      id: packageItem.id,
      itemType: "WORK_PACKAGE",
      reference: "WP-PACKAGE",
      title: packageItem.title,
      column: "READY",
      priority: "HIGH",
      dueOn: packageItem.dueOn,
      ownerUserId: "analyst-ssg",
      ownerDisplayName: "Lewis Ferguson",
      version: 2,
      linkedRequestId: null,
      availableColumns: ["IN_PROGRESS", "BLOCKED"],
      changedAt: "2026-08-06T10:00:00Z",
    },
  ],
  nextCursor: "cursor-next",
  columnCounts: {
    AWAITING_ASSIGNMENT: 0,
    BACKLOG: 0,
    READY: 1,
    IN_PROGRESS: 1,
    BLOCKED: 0,
    MANAGER_REVIEW: 0,
    QUALITY_REVIEW: 0,
    REWORK: 0,
    ON_HOLD: 0,
    COMPLETED: 0,
    CANCELLED: 0,
  },
  totalCount: 2,
  wipLimits: { READY: 4, IN_PROGRESS: 3 },
  configurationVersion: 2,
  savedViews: [
    {
      id: "view-one",
      name: "My delivery",
      filters: {
        search: "product",
        columns: [],
        priorities: ["HIGH"],
        ownerUserId: "analyst-ssg",
        itemTypes: ["WORK_PACKAGE"],
        dueBefore: null,
      },
      version: 1,
    },
  ],
  generatedAt: "2026-08-07T12:00:00Z",
};

export function mockBoard(
  session: Session,
  access: TeamWorkspaceAccess,
  calls: Array<{ path: string; method: string; body: Record<string, unknown> }>,
  value: BoardResult = board,
  failMutations = false,
  initialRequest: RequestDetail = {
    ...requestDetail,
    id: "request-one",
    title: "Customer request projection",
  },
  deepLinkedItem: BoardItem | null = { ...board.items[0], column: "REWORK" },
) {
  const state = { requestValue: initialRequest };
  return mockFetch(
    async (url, init) => {
      const method = init.method ?? "GET";
      const body = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : {};
      if (method !== "GET") calls.push({ path: url.pathname, method, body });
      return method === "GET"
        ? boardGetResponse(url.pathname, session, access, value, deepLinkedItem, state)
        : boardMutationResponse(url.pathname, method, body, session, value, failMutations, state);
    },
    true,
    true,
    false,
  );
}

type MockBoardState = { requestValue: RequestDetail };

function boardGetResponse(
  path: string,
  session: Session,
  access: TeamWorkspaceAccess,
  value: BoardResult,
  deepLinkedItem: BoardItem | null,
  state: MockBoardState,
) {
  if (path.endsWith("/auth/me")) return json(session);
  if (path.endsWith("/team-workspaces")) return json({ items: [access] });
  if (path.endsWith("/people")) return json({ items: people });
  if (path.endsWith("/iterations")) return json({ items: iterations });
  if (path.endsWith("/board")) return json(value);
  if (path.endsWith("/board/requests/request-one"))
    return deepLinkedItem ? json(deepLinkedItem) : json({ detail: "Not found" }, 404);
  if (path.endsWith("/packages")) return json({ items: [packageItem] });
  if (path.endsWith("/requests/request-one")) return json(state.requestValue);
  throw new Error(`Unexpected ${path}`);
}

function boardMutationResponse(
  path: string,
  method: string,
  body: Record<string, unknown>,
  session: Session,
  value: BoardResult,
  failMutations: boolean,
  state: MockBoardState,
) {
  if (path.endsWith("/hasteners") && method === "POST")
    return hastenerResponse(body, session, state);
  if (failMutations) return json({ detail: "Planning conflict" }, 409);
  if (path.includes("saved-views") && method === "DELETE")
    return new Response(null, { status: 204 });
  if (path.includes("saved-views")) return savedViewResponse(value);
  if (path.endsWith("/board/configuration")) return json({ wipLimits: body.wipLimits, version: 3 });
  if (path.endsWith("/board/moves") || path.endsWith("/packages")) return json(packageItem);
  throw new Error(`Unexpected ${path}`);
}

function hastenerResponse(body: Record<string, unknown>, session: Session, state: MockBoardState) {
  const recipientNames =
    body.audience === "ALL_ASSIGNED" ? "Lewis Ferguson, Nathan Patterson" : "Nathan Patterson";
  state.requestValue = {
    ...state.requestValue,
    events: [
      ...state.requestValue.events,
      {
        id: `hastener-${state.requestValue.events.length}`,
        type: "task_hastener",
        message: `Hastener sent to ${recipientNames}: ${body.message}`,
        actorDisplayName: session.user.displayName,
        createdAt: "2026-08-11T10:00:00Z",
      },
    ],
  };
  return json({
    eventId: "event-hastener",
    requestId: "request-one",
    message: body.message,
    senderDisplayName: session.user.displayName,
    recipients: [],
    createdAt: "2026-08-11T10:00:00Z",
  });
}

function savedViewResponse(value: BoardResult) {
  return json(
    value.savedViews[0] ?? {
      id: "new-view",
      name: "Urgent work",
      filters: {
        search: "",
        columns: [],
        priorities: [],
        ownerUserId: null,
        itemTypes: [],
        dueBefore: null,
      },
      version: 1,
    },
  );
}
